"""Phase B: TopologyLayoutGenerator — assigns grid center points to locations."""

from __future__ import annotations

import logging
import math
from collections import deque

from worldkernel.architect.spatial.config import SpatialGenerationConfig
from worldkernel.architect.spatial.graph_algorithms import (
    bfs_components,
    bfs_distances,
    fruchterman_reingold,
)
from worldkernel.architect.spatial.models import (
    LocationLayout,
    LocationSpatialFact,
    LayoutPlan,
    SpatialBuildInput,
    SpatialInputWarning,
)

logger = logging.getLogger(__name__)

# Importance → center-pull weight
_IMPORTANCE_WEIGHT: dict[str, float] = {
    "core": 1.0,
    "major": 0.5,
    "minor": 0.2,
}


class TopologyLayoutGenerator:
    """Generates a LayoutPlan with grid center points for each location."""

    def generate(
        self,
        build_input: SpatialBuildInput,
        config: SpatialGenerationConfig,
    ) -> LayoutPlan:
        warnings: list[SpatialInputWarning] = []
        canvas = config.canvas
        layout_cfg = config.layout

        # 1. Index locations
        loc_map: dict[str, LocationSpatialFact] = {
            loc.location_id: loc for loc in build_input.locations
        }
        node_ids = sorted(loc_map.keys())

        if not node_ids:
            warnings.append(SpatialInputWarning(
                code="no_locations",
                message="No locations to layout",
                source="topology_layout",
            ))
            return self._empty_plan(build_input, config, warnings)

        # 2. Build adjacency from paths
        adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
        for path in build_input.paths:
            adj[path.from_location_id].add(path.to_location_id)
            if path.bidirectional:
                adj[path.to_location_id].add(path.from_location_id)

        # 3. Detect components and bridge if disconnected
        components = bfs_components(adj)
        synthetic_edges: list[tuple[str, str]] = []

        if len(components) > 1:
            synthetic_edges = self._bridge_components(components, adj, loc_map)
            for a, b in synthetic_edges:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            warnings.append(SpatialInputWarning(
                code="disconnected_graph",
                message=(
                    f"Semantic graph has {len(components)} disconnected components; "
                    f"added {len(synthetic_edges)} synthetic bridge(s) for layout"
                ),
                source="topology_layout",
            ))

        # 4. Build edge list for FR
        edge_list: list[tuple[str, str]] = []
        seen_edges: set[tuple[str, str]] = set()
        for a in node_ids:
            for b in adj.get(a, set()):
                key = tuple(sorted([a, b]))
                if key not in seen_edges:
                    seen_edges.add(key)
                    edge_list.append(key)

        # 5. Run Fruchterman-Reingold
        margin = float(max(
            canvas.margin_tiles,
            layout_cfg.edge_comfort_margin + layout_cfg.preferred_region_gap,
        ))
        continuous_pos = fruchterman_reingold(
            nodes=node_ids,
            edges=edge_list,
            iterations=layout_cfg.fr_iterations,
            seed=layout_cfg.random_seed,
            width=float(canvas.grid_width),
            height=float(canvas.grid_height),
            margin=margin,
        )

        # 6. Apply importance bias (pull toward center)
        center_x = canvas.grid_width / 2.0
        center_y = canvas.grid_height / 2.0
        biased_pos: dict[str, tuple[float, float]] = {}
        for nid in node_ids:
            cx, cy = continuous_pos[nid]
            importance = loc_map[nid].importance
            weight = _IMPORTANCE_WEIGHT.get(importance, 0.3)
            pull = 0.28 * weight
            tags = set(loc_map[nid].tags)
            if "public" in tags or "communal" in tags:
                pull = max(pull, 0.12)
            bx = cx * (1.0 - pull) + center_x * pull
            by = cy * (1.0 - pull) + center_y * pull
            biased_pos[nid] = (bx, by)

        # 7. Apply secret/hidden edge bias (push toward edges)
        secret_push = 0.12
        for nid in node_ids:
            tags = loc_map[nid].tags
            if "secret" in tags:
                bx, by = biased_pos[nid]
                # Push toward nearest canvas edge
                edge_x = margin if bx < center_x else canvas.grid_width - margin
                edge_y = margin if by < center_y else canvas.grid_height - margin
                # Push toward the closer edge
                if abs(bx - center_x) > abs(by - center_y):
                    ex, ey = edge_x, by
                else:
                    ex, ey = bx, edge_y
                bx = bx * (1.0 - secret_push) + ex * secret_push
                by = by * (1.0 - secret_push) + ey * secret_push
                biased_pos[nid] = (bx, by)

        # 8. Normalize to grid and snap to integers
        grid_positions = self._snap_to_grid(
            biased_pos, node_ids, loc_map, canvas, margin,
        )

        # 9. Build output
        locations = [
            LocationLayout(
                location_id=nid,
                center_x=grid_positions[nid][0],
                center_y=grid_positions[nid][1],
                layer_id=layout_cfg.default_layer_id,
            )
            for nid in node_ids
        ]

        return LayoutPlan(
            world_id=build_input.world_id,
            grid_width=canvas.grid_width,
            grid_height=canvas.grid_height,
            tile_size=canvas.tile_size,
            locations=locations,
            synthetic_edges=synthetic_edges,
            warnings=warnings,
            provenance={
                "algorithm": "fruchterman_reingold",
                "fr_iterations": layout_cfg.fr_iterations,
                "random_seed": layout_cfg.random_seed,
                "component_count": len(components),
                "synthetic_edge_count": len(synthetic_edges),
            },
        )

    # ------------------------------------------------------------------
    # Component bridging
    # ------------------------------------------------------------------

    def _bridge_components(
        self,
        components: list[list[str]],
        adj: dict[str, set[str]],
        loc_map: dict[str, LocationSpatialFact],
    ) -> list[tuple[str, str]]:
        """Connect disconnected components by bridging their highest-degree nodes."""
        if len(components) <= 1:
            return []

        # Pick representative node from each component (highest degree, then highest importance)
        def _pick_representative(component: list[str]) -> str:
            def _score(nid: str) -> tuple[int, str]:
                degree = len(adj.get(nid, set()))
                importance_order = {"core": 3, "major": 2, "minor": 1}.get(
                    loc_map[nid].importance, 0
                )
                return (degree + importance_order, nid)

            return max(component, key=_score)

        reps = [_pick_representative(c) for c in components]

        # Connect each component to the next one (chain)
        synthetic: list[tuple[str, str]] = []
        for i in range(len(reps) - 1):
            synthetic.append((reps[i], reps[i + 1]))

        return synthetic

    # ------------------------------------------------------------------
    # Grid snapping
    # ------------------------------------------------------------------

    def _snap_to_grid(
        self,
        continuous_pos: dict[str, tuple[float, float]],
        node_ids: list[str],
        loc_map: dict[str, LocationSpatialFact],
        canvas: object,
        margin: float,
    ) -> dict[str, tuple[int, int]]:
        """Convert continuous positions to integer grid coordinates, resolving collisions."""
        grid_w = canvas.grid_width
        grid_h = canvas.grid_height
        max_w, max_h = canvas.default_region_max_size
        safe_left = int(margin) + max_w // 2
        safe_right = grid_w - int(margin) - max_w // 2
        safe_top = int(margin) + max_h // 2
        safe_bottom = grid_h - int(margin) - max_h // 2
        if safe_left > safe_right:
            safe_left, safe_right = int(margin), grid_w - int(margin) - 1
        if safe_top > safe_bottom:
            safe_top, safe_bottom = int(margin), grid_h - int(margin) - 1

        # Sort by importance (core first gets best positions)
        importance_order = {"core": 0, "major": 1, "minor": 2}
        sorted_ids = sorted(
            node_ids,
            key=lambda nid: (importance_order.get(loc_map[nid].importance, 3), nid),
        )

        occupied: set[tuple[int, int]] = set()
        result: dict[str, tuple[int, int]] = {}

        for nid in sorted_ids:
            cx, cy = continuous_pos[nid]
            gx = max(safe_left, min(safe_right, round(cx)))
            gy = max(safe_top, min(safe_bottom, round(cy)))

            if (gx, gy) in occupied:
                gx, gy = self._find_nearest_free(
                    gx, gy, occupied, grid_w, grid_h, safe_left, safe_right, safe_top, safe_bottom,
                )

            occupied.add((gx, gy))
            result[nid] = (gx, gy)

        return result

    @staticmethod
    def _find_nearest_free(
        x: int,
        y: int,
        occupied: set[tuple[int, int]],
        grid_w: int,
        grid_h: int,
        safe_left: int,
        safe_right: int,
        safe_top: int,
        safe_bottom: int,
    ) -> tuple[int, int]:
        """Spiral search for the nearest unoccupied grid cell."""
        for radius in range(1, max(grid_w, grid_h)):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    nx, ny = x + dx, y + dy
                    if safe_left <= nx <= safe_right and safe_top <= ny <= safe_bottom:
                        if (nx, ny) not in occupied:
                            return nx, ny
        # Fallback (should not happen with reasonable canvas)
        return x, y

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_plan(
        self,
        build_input: SpatialBuildInput,
        config: SpatialGenerationConfig,
        warnings: list[SpatialInputWarning],
    ) -> LayoutPlan:
        return LayoutPlan(
            world_id=build_input.world_id,
            grid_width=config.canvas.grid_width,
            grid_height=config.canvas.grid_height,
            tile_size=config.canvas.tile_size,
            warnings=warnings,
        )
