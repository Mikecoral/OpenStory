"""Phase G: SpatialBlueprintExporter — exports spatial blueprint for the visual layer."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from worldkernel.architect.spatial.models import (
    BlueprintGrid,
    BlueprintRegion,
    BlueprintRoute,
    BlueprintSpawnPoint,
    CanonicalSpatialArtifact,
    GridPoint,
    SpatialBlueprint,
    SpatialBuildInput,
)

logger = logging.getLogger(__name__)


class SpatialBlueprintExporter:
    """Converts a CanonicalSpatialArtifact into a SpatialBlueprint for the visual layer."""

    def export(
        self,
        artifact: CanonicalSpatialArtifact,
        build_input: SpatialBuildInput,
        spawn_seed: int = 42,
    ) -> SpatialBlueprint:
        grid = BlueprintGrid(
            width=artifact.grid_width,
            height=artifact.grid_height,
            tile_size=artifact.tile_size,
        )

        regions = [
            BlueprintRegion(
                location_id=r.location_id,
                name=r.name,
                bounds={"x": r.x, "y": r.y, "w": r.width, "h": r.height},
                entrance={"x": r.entrance_x, "y": r.entrance_y},
                tags=list(r.tags),
            )
            for r in artifact.regions
        ]

        routes = [
            BlueprintRoute(
                path_edge_id=r.path_edge_id,
                from_location_id=r.from_location_id,
                to_location_id=r.to_location_id,
                centerline=[GridPoint(x=t.x, y=t.y) for t in r.route_tiles],
                corridor_width=artifact.provenance.get("canvas", {}).get("corridor_width", 3),
                movement_cost=r.movement_cost,
                access_tags=list(r.access_tags),
            )
            for r in artifact.routes
        ]

        spawn_points = self._assign_spawns(artifact, build_input, spawn_seed)

        return SpatialBlueprint(
            world_id=artifact.world_id,
            grid=grid,
            collision=artifact.collision_grid,
            regions=regions,
            routes=routes,
            road_tiles=list(artifact.road_tiles),
            spawn_points=spawn_points,
            provenance={
                "source": "canonical_spatial_artifact",
                "region_count": len(regions),
                "route_count": len(routes),
                "spawn_count": len(spawn_points),
                "road_tile_count": len(artifact.road_tiles),
            },
        )

    def export_to_file(
        self,
        blueprint: SpatialBlueprint,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(blueprint.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Spatial blueprint written to %s", path)
        return path

    # ------------------------------------------------------------------
    # Spawn assignment
    # ------------------------------------------------------------------

    def _assign_spawns(
        self,
        artifact: CanonicalSpatialArtifact,
        build_input: SpatialBuildInput,
        seed: int,
    ) -> list[BlueprintSpawnPoint]:
        rng = random.Random(seed)
        region_map = artifact.indexes.location_id_to_region
        spawn_points: list[BlueprintSpawnPoint] = []

        # Collect all region entrance positions for fallback
        all_entrances = [
            (r.location_id, r.entrance_x, r.entrance_y)
            for r in artifact.regions
        ]
        if not all_entrances:
            return []

        for char in build_input.characters:
            # Determine target location
            target_loc = (
                char.home_location_id
                or char.current_location_id
                or char.preferred_location_id
                or ""
            )

            # Validate target has a region
            if target_loc and target_loc not in region_map:
                target_loc = ""

            # Fallback: random region entrance
            if not target_loc:
                target_loc = rng.choice(all_entrances)[0]

            region = region_map.get(target_loc)
            if region is None:
                continue

            # 在地点区域内随机选一个位置（不强制在入口）
            sx = rng.randint(region.x, region.x + region.width - 1)
            sy = rng.randint(region.y, region.y + region.height - 1)
            spawn_points.append(BlueprintSpawnPoint(
                character_id=char.character_id,
                character_name=char.name,
                location_id=target_loc,
                position=[sx, sy],
            ))

        return spawn_points