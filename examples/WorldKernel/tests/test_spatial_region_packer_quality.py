import importlib.util
import math
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


for mod_name in [
    "worldkernel",
    "worldkernel.architect",
    "worldkernel.architect.spatial",
]:
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))


def _load(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


ga = _load(
    "worldkernel.architect.spatial.graph_algorithms",
    "src/worldkernel/architect/spatial/graph_algorithms.py",
)
models = _load(
    "worldkernel.architect.spatial.models",
    "src/worldkernel/architect/spatial/models.py",
)
config_mod = _load(
    "worldkernel.architect.spatial.config",
    "src/worldkernel/architect/spatial/config.py",
)
tl = _load(
    "worldkernel.architect.spatial.topology_layout",
    "src/worldkernel/architect/spatial/topology_layout.py",
)
rp = _load(
    "worldkernel.architect.spatial.region_packer",
    "src/worldkernel/architect/spatial/region_packer.py",
)


LOCATION_DEFS = [
    ("L01", "Great Hall", "core", ["core", "public", "indoor"]),
    ("L02", "Library", "core", ["core", "indoor"]),
    ("L03", "Administration", "core", ["core", "indoor"]),
    ("L04", "Central Plaza", "core", ["core", "public", "outdoor"]),
    ("L05", "Teaching A", "major", ["major", "indoor"]),
    ("L06", "Teaching B", "major", ["major", "indoor"]),
    ("L07", "Gym", "major", ["major", "indoor"]),
    ("L08", "Dining Hall", "major", ["major", "public", "indoor"]),
    ("L09", "Boys Dorm", "major", ["major", "indoor"]),
    ("L10", "Girls Dorm", "major", ["major", "indoor"]),
    ("L11", "Garden", "minor", ["minor", "outdoor"]),
    ("L12", "Hill", "minor", ["minor", "outdoor"]),
    ("L13", "Field", "minor", ["minor", "outdoor", "public"]),
    ("L14", "Clinic", "minor", ["minor", "indoor"]),
    ("L15", "Storage", "minor", ["minor", "indoor"]),
    ("L16", "Gatehouse", "minor", ["minor", "indoor", "public"]),
    ("L17", "Observatory", "", ["outdoor"]),
    ("L18", "Lab", "", ["indoor"]),
    ("L19", "Secret Entry", "", ["secret", "indoor"]),
    ("L20", "Hidden Room", "", ["secret", "indoor"]),
]


PATH_DEFS = [
    ("P01", "L01", "L02"),
    ("P02", "L01", "L03"),
    ("P03", "L01", "L04"),
    ("P04", "L04", "L05"),
    ("P05", "L04", "L06"),
    ("P06", "L05", "L06"),
    ("P07", "L04", "L08"),
    ("P08", "L08", "L09"),
    ("P09", "L08", "L10"),
    ("P10", "L04", "L07"),
    ("P11", "L07", "L13"),
    ("P12", "L02", "L11"),
    ("P13", "L11", "L12"),
    ("P14", "L03", "L14"),
    ("P15", "L03", "L15"),
    ("P16", "L01", "L16"),
    ("P17", "L03", "L18"),
    ("P18", "L12", "L17"),
    ("P19", "L15", "L19"),
    ("P20", "L19", "L20"),
]


def _build_input():
    locations = [
        models.LocationSpatialFact(location_id=lid, name=name, importance=imp, tags=tags)
        for lid, name, imp, tags in LOCATION_DEFS
    ]
    paths = [
        models.PathSpatialFact(
            path_id=pid,
            from_location_id=src,
            to_location_id=dst,
            is_secret=pid in {"P19", "P20"},
            tags=["secret"] if pid in {"P19", "P20"} else [],
        )
        for pid, src, dst in PATH_DEFS
    ]
    return models.SpatialBuildInput(
        world_id="test_quality",
        source_root="/tmp",
        locations=locations,
        paths=paths,
    )


def _rect(region):
    return region.x, region.y, region.width, region.height


def _rect_gap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(bx - (ax + aw), ax - (bx + bw), 0)
    dy = max(by - (ay + ah), ay - (by + bh), 0)
    return math.hypot(dx, dy)


def _approach_point(region):
    if region.entrance_y == region.y:
        return region.entrance_x, region.entrance_y - 1
    if region.entrance_y == region.y + region.height - 1:
        return region.entrance_x, region.entrance_y + 1
    if region.entrance_x == region.x:
        return region.entrance_x - 1, region.entrance_y
    if region.entrance_x == region.x + region.width - 1:
        return region.entrance_x + 1, region.entrance_y
    raise AssertionError(f"entrance is not on edge: {region.location_id}")


def _point_too_close_to_rect(px, py, rect, gap):
    x, y, w, h = rect
    return x - gap <= px <= x + w - 1 + gap and y - gap <= py <= y + h - 1 + gap


def test_region_packer_balances_edge_and_spacing_quality():
    cfg = config_mod.SpatialGenerationConfig()
    build_input = _build_input()
    layout = tl.TopologyLayoutGenerator().generate(build_input, cfg)
    result = rp.RegionPacker().pack(layout, build_input, cfg)

    assert len(result.regions) == len(LOCATION_DEFS)
    assert not [w for w in result.warnings if w.code == "region_placement_failed"]

    min_gap = max(cfg.layout.min_region_gap, cfg.canvas.corridor_width + 1)
    preferred_gap = max(min_gap, cfg.layout.preferred_region_gap)
    rects = [_rect(region) for region in result.regions]

    nearest_gaps = []
    for i, rect in enumerate(rects):
        gaps = [_rect_gap(rect, other) for j, other in enumerate(rects) if i != j]
        nearest_gaps.append(min(gaps))
        assert min(gaps) >= min_gap

    assert sum(nearest_gaps) / len(nearest_gaps) >= preferred_gap * 0.6

    edge_margin = cfg.layout.edge_comfort_margin
    near_edge_count = 0
    for region in result.regions:
        edge_gap = min(
            region.x,
            region.y,
            cfg.canvas.grid_width - (region.x + region.width),
            cfg.canvas.grid_height - (region.y + region.height),
        )
        if edge_gap < edge_margin:
            near_edge_count += 1
    assert near_edge_count <= len(result.regions) * 0.35

    center_x = cfg.canvas.grid_width / 2
    center_y = cfg.canvas.grid_height / 2
    core_distances = []
    noncore_distances = []
    for region in result.regions:
        cx = region.x + region.width / 2
        cy = region.y + region.height / 2
        distance = abs(cx - center_x) + abs(cy - center_y)
        if "core" in region.tags:
            core_distances.append(distance)
        else:
            noncore_distances.append(distance)
    assert sum(core_distances) / len(core_distances) < sum(noncore_distances) / len(noncore_distances)

    for region in result.regions:
        ax, ay = _approach_point(region)
        assert cfg.canvas.margin_tiles <= ax < cfg.canvas.grid_width - cfg.canvas.margin_tiles
        assert cfg.canvas.margin_tiles <= ay < cfg.canvas.grid_height - cfg.canvas.margin_tiles
        for other in result.regions:
            if other.location_id == region.location_id:
                continue
            assert not _point_too_close_to_rect(ax, ay, _rect(other), min_gap)
