from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldkernel.architect.spatial.config import SpatialGenerationConfig
from worldkernel.architect.spatial.models import (
    LayoutPlan,
    LocationLayout,
    LocationSpatialFact,
    PathSpatialFact,
    RegionPackingResult,
    SpatialBuildInput,
    SpatialRegion,
)
from worldkernel.architect.spatial.route_rasterizer import RouteRasterizer


def _build_dense_route_input():
    locations = [
        LocationSpatialFact(location_id="A", name="A", importance="core"),
        LocationSpatialFact(location_id="B", name="B", importance="core"),
        LocationSpatialFact(location_id="C", name="C", importance="major"),
        LocationSpatialFact(location_id="D", name="D", importance="major"),
        LocationSpatialFact(location_id="E", name="E", importance="minor"),
        LocationSpatialFact(location_id="F", name="F", importance="minor"),
    ]
    paths = [
        ("P01", "A", "B"),
        ("P02", "B", "C"),
        ("P03", "B", "D"),
        ("P04", "D", "E"),
        ("P05", "A", "F"),
        ("P06", "F", "D"),
        ("P07", "A", "C"),
        ("P08", "A", "D"),
        ("P09", "B", "E"),
        ("P10", "C", "E"),
        ("P11", "A", "E"),
    ]
    build_input = SpatialBuildInput(
        world_id="route_reuse",
        source_root="/tmp",
        locations=locations,
        paths=[
            PathSpatialFact(path_id=pid, from_location_id=src, to_location_id=dst)
            for pid, src, dst in paths
        ],
    )
    layout = LayoutPlan(
        world_id="route_reuse",
        grid_width=120,
        grid_height=80,
        tile_size=16,
        locations=[
            LocationLayout(location_id=loc.location_id, center_x=0, center_y=0)
            for loc in locations
        ],
    )
    regions = [
        SpatialRegion(location_id="A", name="A", x=12, y=28, width=8, height=6, entrance_x=19, entrance_y=31),
        SpatialRegion(location_id="B", name="B", x=50, y=28, width=8, height=6, entrance_x=50, entrance_y=31),
        SpatialRegion(location_id="C", name="C", x=88, y=28, width=8, height=6, entrance_x=88, entrance_y=31),
        SpatialRegion(location_id="D", name="D", x=50, y=55, width=8, height=6, entrance_x=54, entrance_y=55),
        SpatialRegion(location_id="E", name="E", x=88, y=55, width=8, height=6, entrance_x=92, entrance_y=55),
        SpatialRegion(location_id="F", name="F", x=12, y=55, width=8, height=6, entrance_x=16, entrance_y=55),
    ]
    return build_input, layout, RegionPackingResult(regions=regions), regions


def test_route_rasterizer_reuses_existing_roads_for_dense_semantic_edges():
    cfg = SpatialGenerationConfig()
    cfg.canvas.grid_width = 120
    cfg.canvas.grid_height = 80
    build_input, layout, packing, regions = _build_dense_route_input()

    result = RouteRasterizer().rasterize(build_input, layout, packing, cfg)

    assert len(result.routes) == len(build_input.paths)
    assert result.road_tiles
    assert {cell for row in result.collision_grid for cell in row} <= {0, 1}

    total_centerline_tiles = sum(len(route.route_tiles) for route in result.routes)
    unique_centerline_tiles = {
        (tile.x, tile.y)
        for route in result.routes
        for tile in route.route_tiles
    }
    assert len(unique_centerline_tiles) < total_centerline_tiles * 0.75

    entrances = {
        region.location_id: (region.entrance_x, region.entrance_y)
        for region in regions
    }
    for route in result.routes:
        assert (route.route_tiles[0].x, route.route_tiles[0].y) == entrances[route.from_location_id]
        assert (route.route_tiles[-1].x, route.route_tiles[-1].y) == entrances[route.to_location_id]
