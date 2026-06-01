"""Phase E1: StructuralValidator — assembles canonical artifact and validates structure."""

from __future__ import annotations

import logging

from worldkernel.architect.spatial.config import SpatialGenerationConfig
from worldkernel.architect.spatial.graph_algorithms import bfs_components
from worldkernel.architect.spatial.models import (
    CanonicalSpatialArtifact,
    E1ValidationResult,
    LayoutPlan,
    RegionPackingResult,
    RouteRasterizationResult,
    SpatialBuildInput,
    SpatialIndexes,
    SpatialRegion,
    SpatialRoute,
    ValidationIssue,
    ValidationReport,
)

logger = logging.getLogger(__name__)


class StructuralValidator:
    """Assembles canonical spatial artifact and validates structural integrity."""

    def validate(
        self,
        build_input: SpatialBuildInput,
        layout_plan: LayoutPlan,
        packing_result: RegionPackingResult,
        rasterization_result: RouteRasterizationResult,
        config: SpatialGenerationConfig,
    ) -> E1ValidationResult:
        issues: list[ValidationIssue] = []

        # 1. Assemble canonical artifact
        artifact = self._assemble(build_input, packing_result, rasterization_result, config)

        # 2. Run validation checks
        self._check_region_coverage(build_input, artifact, issues)
        self._check_entrance_on_boundary(artifact, issues)
        self._check_entrance_walkable(artifact, issues)
        self._check_collision_grid(config, artifact, issues)
        self._check_route_tiles_walkable(artifact, issues)
        self._check_route_endpoint_match(artifact, issues)
        self._check_semantic_path_coverage(build_input, artifact, issues)
        self._check_connectivity(artifact, issues)
        self._check_no_reference_breaks(artifact, issues)

        passed = not any(i.severity == "error" for i in issues)

        report = ValidationReport(
            passed=passed,
            issues=issues,
            provenance={
                "checks_run": 9,
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
            },
        )

        return E1ValidationResult(artifact=artifact, report=report)

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def _assemble(
        self,
        build_input: SpatialBuildInput,
        packing_result: RegionPackingResult,
        rasterization_result: RouteRasterizationResult,
        config: SpatialGenerationConfig,
    ) -> CanonicalSpatialArtifact:
        # Build indexes
        loc_to_region: dict[str, SpatialRegion] = {
            r.location_id: r for r in packing_result.regions
        }
        path_to_route: dict[str, SpatialRoute] = {
            r.path_edge_id: r for r in rasterization_result.routes
        }
        loc_to_routes: dict[str, list[str]] = {}
        for route in rasterization_result.routes:
            loc_to_routes.setdefault(route.from_location_id, []).append(route.path_edge_id)
            loc_to_routes.setdefault(route.to_location_id, []).append(route.path_edge_id)

        indexes = SpatialIndexes(
            location_id_to_region=loc_to_region,
            path_edge_id_to_route=path_to_route,
            location_id_to_routes=loc_to_routes,
        )

        # Aggregate warnings from all phases
        all_warnings = (
            build_input.warnings
            + packing_result.warnings
            + rasterization_result.warnings
        )

        return CanonicalSpatialArtifact(
            world_id=build_input.world_id,
            grid_width=config.canvas.grid_width,
            grid_height=config.canvas.grid_height,
            tile_size=config.canvas.tile_size,
            regions=packing_result.regions,
            routes=rasterization_result.routes,
            road_tiles=rasterization_result.road_tiles,
            collision_grid=rasterization_result.collision_grid,
            indexes=indexes,
            provenance={
                "assembled_from": ["build_input", "packing_result", "rasterization_result"],
                "upstream_warnings": len(all_warnings),
                "canvas": {
                    "grid_width": config.canvas.grid_width,
                    "grid_height": config.canvas.grid_height,
                    "tile_size": config.canvas.tile_size,
                    "corridor_width": config.canvas.corridor_width,
                },
            },
        )

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------

    def _check_region_coverage(
        self,
        build_input: SpatialBuildInput,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        region_ids = {r.location_id for r in artifact.regions}
        for loc in build_input.locations:
            if loc.location_id not in region_ids:
                issues.append(ValidationIssue(
                    code="missing_region",
                    severity="error",
                    message=f"location {loc.location_id!r} has no region",
                    affected_id=loc.location_id,
                ))

    def _check_entrance_on_boundary(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        for region in artifact.regions:
            ex, ey = region.entrance_x, region.entrance_y
            on_x_boundary = (ex == region.x or ex == region.x + region.width - 1) and \
                            region.y <= ey <= region.y + region.height - 1
            on_y_boundary = (ey == region.y or ey == region.y + region.height - 1) and \
                            region.x <= ex <= region.x + region.width - 1
            if not (on_x_boundary or on_y_boundary):
                issues.append(ValidationIssue(
                    code="entrance_not_on_boundary",
                    severity="warning",
                    message=(
                        f"region {region.location_id!r} entrance ({ex},{ey}) "
                        f"is not on boundary of rect ({region.x},{region.y},"
                        f"{region.width},{region.height})"
                    ),
                    affected_id=region.location_id,
                ))

    def _check_entrance_walkable(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        grid = artifact.collision_grid
        if not grid or not grid[0]:
            return
        for region in artifact.regions:
            ex, ey = region.entrance_x, region.entrance_y
            if 0 <= ey < len(grid) and 0 <= ex < len(grid[0]):
                if grid[ey][ex] == 0:
                    issues.append(ValidationIssue(
                        code="entrance_not_walkable",
                        severity="error",
                        message=(
                            f"region {region.location_id!r} entrance ({ex},{ey}) "
                            f"is blocked (0) in collision_grid"
                        ),
                        affected_id=region.location_id,
                    ))

    def _check_collision_grid(
        self,
        config: SpatialGenerationConfig,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        grid = artifact.collision_grid
        expected_h = config.canvas.grid_height
        expected_w = config.canvas.grid_width

        if len(grid) != expected_h:
            issues.append(ValidationIssue(
                code="grid_height_mismatch",
                severity="error",
                message=f"collision_grid has {len(grid)} rows, expected {expected_h}",
            ))
            return

        for y, row in enumerate(grid):
            if len(row) != expected_w:
                issues.append(ValidationIssue(
                    code="grid_width_mismatch",
                    severity="error",
                    message=f"collision_grid row {y} has {len(row)} cols, expected {expected_w}",
                ))
                return

        bad_tiles = 0
        for row in grid:
            for val in row:
                if val not in (0, 1):
                    bad_tiles += 1
        if bad_tiles > 0:
            issues.append(ValidationIssue(
                code="grid_invalid_values",
                severity="warning",
                message=f"collision_grid has {bad_tiles} tiles with values other than 0/1",
            ))

    def _check_route_tiles_walkable(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        grid = artifact.collision_grid
        if not grid or not grid[0]:
            return
        for route in artifact.routes:
            for tile in route.route_tiles:
                if 0 <= tile.y < len(grid) and 0 <= tile.x < len(grid[0]):
                    if grid[tile.y][tile.x] == 0:
                        issues.append(ValidationIssue(
                            code="route_tile_blocked",
                            severity="error",
                            message=(
                                f"route {route.path_edge_id!r} tile ({tile.x},{tile.y}) "
                                f"is blocked in collision_grid"
                            ),
                            affected_id=route.path_edge_id,
                        ))
                        break  # one per route is enough

    def _check_route_endpoint_match(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        region_map = artifact.indexes.location_id_to_region
        for route in artifact.routes:
            from_region = region_map.get(route.from_location_id)
            to_region = region_map.get(route.to_location_id)
            if from_region is None or to_region is None:
                continue  # caught by missing_region check

            if not route.route_tiles:
                issues.append(ValidationIssue(
                    code="route_empty",
                    severity="error",
                    message=f"route {route.path_edge_id!r} has no tiles",
                    affected_id=route.path_edge_id,
                ))
                continue

            start = route.route_tiles[0]
            end = route.route_tiles[-1]

            if start.x != from_region.entrance_x or start.y != from_region.entrance_y:
                issues.append(ValidationIssue(
                    code="route_start_mismatch",
                    severity="error",
                    message=(
                        f"route {route.path_edge_id!r} starts at ({start.x},{start.y}), "
                        f"expected from entrance ({from_region.entrance_x},{from_region.entrance_y})"
                    ),
                    affected_id=route.path_edge_id,
                ))

            if end.x != to_region.entrance_x or end.y != to_region.entrance_y:
                issues.append(ValidationIssue(
                    code="route_end_mismatch",
                    severity="error",
                    message=(
                        f"route {route.path_edge_id!r} ends at ({end.x},{end.y}), "
                        f"expected to entrance ({to_region.entrance_x},{to_region.entrance_y})"
                    ),
                    affected_id=route.path_edge_id,
                ))

    def _check_semantic_path_coverage(
        self,
        build_input: SpatialBuildInput,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        routed_ids = {r.path_edge_id for r in artifact.routes}
        for path in build_input.paths:
            if path.path_id not in routed_ids:
                issues.append(ValidationIssue(
                    code="path_not_routed",
                    severity="warning",
                    message=f"semantic path {path.path_id!r} has no corresponding route",
                    affected_id=path.path_id,
                ))

    def _check_connectivity(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        # Build adjacency from routes
        adj: dict[str, set[str]] = {}
        for route in artifact.routes:
            adj.setdefault(route.from_location_id, set()).add(route.to_location_id)
            if route.bidirectional:
                adj.setdefault(route.to_location_id, set()).add(route.from_location_id)

        region_ids = {r.location_id for r in artifact.regions}
        components = bfs_components(adj)

        # Check if all non-hidden regions are in the same component
        non_hidden = {
            r.location_id for r in artifact.regions
            if "hidden" not in r.tags
        }
        if non_hidden and len(components) > 1:
            # Find which component each non-hidden location is in
            comp_map: dict[str, int] = {}
            for idx, comp in enumerate(components):
                for nid in comp:
                    comp_map[nid] = idx
            reachable_comps = {comp_map[nid] for nid in non_hidden if nid in comp_map}
            if len(reachable_comps) > 1:
                issues.append(ValidationIssue(
                    code="disconnected_non_hidden",
                    severity="warning",
                    message=(
                        f"non-hidden locations span {len(reachable_comps)} disconnected components"
                    ),
                ))

        # Check for regions with no routes at all
        routed_locs = set(adj.keys())
        for region in artifact.regions:
            if region.location_id not in routed_locs and "hidden" not in region.tags:
                issues.append(ValidationIssue(
                    code="isolated_region",
                    severity="warning",
                    message=f"region {region.location_id!r} has no routes",
                    affected_id=region.location_id,
                ))

    def _check_no_reference_breaks(
        self,
        artifact: CanonicalSpatialArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        region_ids = {r.location_id for r in artifact.regions}
        for route in artifact.routes:
            if route.from_location_id not in region_ids:
                issues.append(ValidationIssue(
                    code="broken_reference",
                    severity="error",
                    message=(
                        f"route {route.path_edge_id!r} references "
                        f"from_location_id {route.from_location_id!r} which has no region"
                    ),
                    affected_id=route.path_edge_id,
                ))
            if route.to_location_id not in region_ids:
                issues.append(ValidationIssue(
                    code="broken_reference",
                    severity="error",
                    message=(
                        f"route {route.path_edge_id!r} references "
                        f"to_location_id {route.to_location_id!r} which has no region"
                    ),
                    affected_id=route.path_edge_id,
                ))