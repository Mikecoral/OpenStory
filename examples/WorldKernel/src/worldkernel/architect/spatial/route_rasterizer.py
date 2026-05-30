"""Phase D: RouteRasterizer — converts semantic path edges into walkable tile routes."""

from __future__ import annotations

import logging
from typing import Any

from worldkernel.architect.spatial.config import SpatialGenerationConfig
from worldkernel.architect.spatial.graph_algorithms import astar_orthogonal, bfs_components
from worldkernel.architect.spatial.models import (
    GridPoint,
    LayoutPlan,
    PathSpatialFact,
    RegionPackingResult,
    RouteRasterizationResult,
    SpatialBuildInput,
    SpatialInputWarning,
    SpatialRegion,
    SpatialRoute,
)

logger = logging.getLogger(__name__)


class RouteRasterizer:
    """Converts semantic path edges into tile-level routes on a collision grid."""

    def rasterize(
        self,
        build_input: SpatialBuildInput,
        layout_plan: LayoutPlan,
        packing_result: RegionPackingResult,
        config: SpatialGenerationConfig,
    ) -> RouteRasterizationResult:
        warnings: list[SpatialInputWarning] = []
        grid_w = config.canvas.grid_width
        grid_h = config.canvas.grid_height
        corridor_w = config.canvas.corridor_width
        blocked = config.grid_values.blocked
        walkable = config.grid_values.walkable

        # 1. Initialize collision grid
        grid = [[blocked] * grid_w for _ in range(grid_h)]

        # 2. Index regions by location_id
        region_map: dict[str, SpatialRegion] = {
            r.location_id: r for r in packing_result.regions
        }

        # 3. Mark region interiors as walkable
        for region in packing_result.regions:
            self._fill_region(grid, region, walkable)

        # 4. Mark entrances as walkable
        for region in packing_result.regions:
            if self._in_bounds(region.entrance_x, region.entrance_y, grid_w, grid_h):
                grid[region.entrance_y][region.entrance_x] = walkable

        # 5. Build adjacency for connectivity check
        adj: dict[str, set[str]] = {}
        path_map: dict[tuple[str, str], PathSpatialFact] = {}
        for path in build_input.paths:
            adj.setdefault(path.from_location_id, set()).add(path.to_location_id)
            if path.bidirectional:
                adj.setdefault(path.to_location_id, set()).add(path.from_location_id)
            edge_key = self._edge_key(path.from_location_id, path.to_location_id)
            path_map[edge_key] = path

        # 6. Route each semantic path edge
        routes: list[SpatialRoute] = []
        routed_edges: set[tuple[str, str]] = set()

        for path in sorted(build_input.paths, key=lambda p: p.path_id):
            edge_key = self._edge_key(path.from_location_id, path.to_location_id)
            if edge_key in routed_edges:
                continue

            from_region = region_map.get(path.from_location_id)
            to_region = region_map.get(path.to_location_id)

            if from_region is None or to_region is None:
                warnings.append(SpatialInputWarning(
                    code="route_missing_region",
                    message=(
                        f"path {path.path_id!r}: region not found for "
                        f"{path.from_location_id!r} or {path.to_location_id!r}; skipped"
                    ),
                    source="route_rasterizer",
                    item_id=path.path_id,
                ))
                continue

            route = self._route_single(
                path.path_id,
                path.from_location_id,
                path.to_location_id,
                from_region,
                to_region,
                grid, grid_w, grid_h, corridor_w, walkable, blocked,
                path.bidirectional,
                path.is_secret,
                config.routing.secret_path_cost_multiplier,
            )

            if route is None:
                warnings.append(SpatialInputWarning(
                    code="route_generation_failed",
                    message=(
                        f"path {path.path_id!r}: A* failed between "
                        f"{path.from_location_id!r} and {path.to_location_id!r}"
                    ),
                    source="route_rasterizer",
                    item_id=path.path_id,
                ))
                continue

            routes.append(route)
            routed_edges.add(edge_key)

        # 7. Check for disconnected components and add synthetic routes
        components = bfs_components(adj)
        if len(components) > 1:
            synth_routes, synth_warnings = self._add_synthetic_routes(
                components, region_map, grid, grid_w, grid_h, corridor_w,
                walkable, blocked, build_input,
            )
            routes.extend(synth_routes)
            warnings.extend(synth_warnings)

        return RouteRasterizationResult(
            routes=routes,
            collision_grid=grid,
            warnings=warnings,
            provenance={
                "algorithm": "orthogonal_astar",
                "corridor_width": corridor_w,
                "routes_generated": len(routes),
                "synthetic_routes": sum(1 for r in routes if r.route_type == "synthetic"),
                "component_count": len(components),
            },
        )

    # ------------------------------------------------------------------
    # Single route
    # ------------------------------------------------------------------

    def _route_single(
        self,
        path_edge_id: str,
        from_id: str,
        to_id: str,
        from_region: SpatialRegion,
        to_region: SpatialRegion,
        grid: list[list[int]],
        grid_w: int, grid_h: int,
        corridor_w: int,
        walkable: int, blocked: int,
        bidirectional: bool,
        is_secret: bool,
        secret_cost_mult: float,
    ) -> SpatialRoute | None:
        """Route a single path edge from entrance to entrance."""
        start = (from_region.entrance_x, from_region.entrance_y)
        goal = (to_region.entrance_x, to_region.entrance_y)

        # Try walkable-only path first
        tile_path = astar_orthogonal(grid, start, goal, blocked_value=blocked)
        # Fallback: allow routing through blocked tiles (creates new corridors)
        if tile_path is None:
            tile_path = astar_orthogonal(
                grid, start, goal, blocked_value=blocked,
                allow_through_blocked=True, blocked_cost=5,
            )
        if tile_path is None:
            return None

        # Widen corridor and mark grid
        self._widen_and_mark(tile_path, corridor_w, grid, grid_w, grid_h, walkable)

        # Determine access tags
        access_tags: list[str] = []
        if is_secret:
            access_tags.append("secret")

        cost = 1.0 * (secret_cost_mult if is_secret else 1.0)

        return SpatialRoute(
            path_edge_id=path_edge_id,
            from_location_id=from_id,
            to_location_id=to_id,
            route_tiles=[GridPoint(x=x, y=y) for x, y in tile_path],
            route_type="corridor",
            bidirectional=bidirectional,
            movement_cost=cost,
            access_tags=access_tags,
        )

    # ------------------------------------------------------------------
    # Synthetic routes for disconnected components
    # ------------------------------------------------------------------

    def _add_synthetic_routes(
        self,
        components: list[list[str]],
        region_map: dict[str, SpatialRegion],
        grid: list[list[int]],
        grid_w: int, grid_h: int,
        corridor_w: int,
        walkable: int, blocked: int,
        build_input: SpatialBuildInput,
    ) -> tuple[list[SpatialRoute], list[SpatialInputWarning]]:
        """Add synthetic routes between disconnected components."""
        routes: list[SpatialRoute] = []
        warnings: list[SpatialInputWarning] = []

        # Build component representatives (highest degree node)
        adj: dict[str, set[str]] = {}
        for path in build_input.paths:
            adj.setdefault(path.from_location_id, set()).add(path.to_location_id)
            adj.setdefault(path.to_location_id, set()).add(path.from_location_id)

        def _pick_rep(comp: list[str]) -> str:
            return max(comp, key=lambda nid: len(adj.get(nid, set())))

        reps = [_pick_rep(c) for c in components]

        # Connect each component to the next
        for i in range(len(reps) - 1):
            from_id = reps[i]
            to_id = reps[i + 1]
            from_region = region_map.get(from_id)
            to_region = region_map.get(to_id)

            if from_region is None or to_region is None:
                continue

            route = self._route_single(
                f"synthetic_{from_id}_{to_id}",
                from_id, to_id,
                from_region, to_region,
                grid, grid_w, grid_h, corridor_w, walkable, blocked,
                bidirectional=True,
                is_secret=False,
                secret_cost_mult=1.0,
            )

            if route is not None:
                route.route_type = "synthetic"
                routes.append(route)
                warnings.append(SpatialInputWarning(
                    code="synthetic_route_added",
                    message=(
                        f"Added synthetic route between disconnected components: "
                        f"{from_id!r} -> {to_id!r}"
                    ),
                    source="route_rasterizer",
                    item_id=route.path_edge_id,
                ))
            else:
                warnings.append(SpatialInputWarning(
                    code="synthetic_route_failed",
                    message=(
                        f"Could not create synthetic route between "
                        f"{from_id!r} and {to_id!r}"
                    ),
                    source="route_rasterizer",
                ))

        return routes, warnings

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fill_region(
        grid: list[list[int]],
        region: SpatialRegion,
        walkable: int,
    ) -> None:
        for dy in range(region.height):
            for dx in range(region.width):
                gx = region.x + dx
                gy = region.y + dy
                if 0 <= gy < len(grid) and 0 <= gx < len(grid[0]):
                    grid[gy][gx] = walkable

    @staticmethod
    def _widen_and_mark(
        path: list[tuple[int, int]],
        corridor_w: int,
        grid: list[list[int]],
        grid_w: int, grid_h: int,
        walkable: int,
    ) -> None:
        """Mark path tiles and surrounding corridor as walkable."""
        half = corridor_w // 2
        for px, py in path:
            for dx in range(-half, half + 1):
                for dy in range(-half, half + 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= ny < grid_h and 0 <= nx < grid_w:
                        grid[ny][nx] = walkable

    @staticmethod
    def _in_bounds(x: int, y: int, w: int, h: int) -> bool:
        return 0 <= x < w and 0 <= y < h

    @staticmethod
    def _edge_key(a: str, b: str) -> tuple[str, str]:
        return tuple(sorted([a, b]))
