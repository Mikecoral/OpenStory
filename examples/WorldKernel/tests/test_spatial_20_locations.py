"""测试 20 个地点的空间布局和矩形放置。"""

import sys
import importlib.util
import types

# ---- 隔离导入，避免触发 architect.__init__ 的全量依赖 ----
for mod_name in [
    "worldkernel", "worldkernel.architect", "worldkernel.architect.spatial",
    "worldkernel.architect.semantic", "worldkernel.architect.semantic.repository",
]:
    sys.modules[mod_name] = types.ModuleType(mod_name)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ga = _load("worldkernel.architect.spatial.graph_algorithms", "src/worldkernel/architect/spatial/graph_algorithms.py")
models = _load("worldkernel.architect.spatial.models", "src/worldkernel/architect/spatial/models.py")
config_mod = _load("worldkernel.architect.spatial.config", "src/worldkernel/architect/spatial/config.py")
sys.modules["worldkernel.architect.spatial.graph_algorithms"] = ga
sys.modules["worldkernel.architect.spatial.models"] = models
sys.modules["worldkernel.architect.spatial.config"] = config_mod
tl = _load("worldkernel.architect.spatial.topology_layout", "src/worldkernel/architect/spatial/topology_layout.py")
sys.modules["worldkernel.architect.spatial.topology_layout"] = tl
rp = _load("worldkernel.architect.spatial.region_packer", "src/worldkernel/architect/spatial/region_packer.py")

# ---- 构建 20 个地点 ----
# 4 个 core, 6 个 major, 6 个 minor, 2 个 secret, 2 个普通
LOCATION_DEFS = [
    # (id, name, importance, tags)
    ("L01", "大礼堂",   "core",   ["core", "public", "indoor"]),
    ("L02", "图书馆",   "core",   ["core", "indoor"]),
    ("L03", "行政楼",   "core",   ["core", "indoor"]),
    ("L04", "中央广场", "core",   ["core", "public", "outdoor"]),
    ("L05", "教学楼A",  "major",  ["major", "indoor"]),
    ("L06", "教学楼B",  "major",  ["major", "indoor"]),
    ("L07", "体育馆",   "major",  ["major", "indoor"]),
    ("L08", "食堂",     "major",  ["major", "public", "indoor"]),
    ("L09", "男生宿舍", "major",  ["major", "indoor"]),
    ("L10", "女生宿舍", "major",  ["major", "indoor"]),
    ("L11", "花园",     "minor",  ["minor", "outdoor"]),
    ("L12", "后山",     "minor",  ["minor", "outdoor"]),
    ("L13", "操场",     "minor",  ["minor", "outdoor", "public"]),
    ("L14", "医务室",   "minor",  ["minor", "indoor"]),
    ("L15", "仓库",     "minor",  ["minor", "indoor"]),
    ("L16", "门卫室",   "minor",  ["minor", "indoor", "public"]),
    ("L17", "天文台",   "",       ["outdoor"]),
    ("L18", "实验楼",   "",       ["indoor"]),
    ("L19", "密道入口", "",       ["secret", "indoor"]),
    ("L20", "地下密室", "",       ["secret", "indoor"]),
]

# 路径：构建连通图（树 + 额外边）
PATH_DEFS = [
    # 主干：大礼堂为中心
    ("P01", "L01", "L02"),  # 大礼堂 - 图书馆
    ("P02", "L01", "L03"),  # 大礼堂 - 行政楼
    ("P03", "L01", "L04"),  # 大礼堂 - 中央广场
    # 教学区
    ("P04", "L04", "L05"),  # 广场 - 教学楼A
    ("P05", "L04", "L06"),  # 广场 - 教学楼B
    ("P06", "L05", "L06"),  # 教学楼A - 教学楼B
    # 生活区
    ("P07", "L04", "L08"),  # 广场 - 食堂
    ("P08", "L08", "L09"),  # 食堂 - 男生宿舍
    ("P09", "L08", "L10"),  # 食堂 - 女生宿舍
    # 体育区
    ("P10", "L04", "L07"),  # 广场 - 体育馆
    ("P11", "L07", "L13"),  # 体育馆 - 操场
    # 休闲区
    ("P12", "L02", "L11"),  # 图书馆 - 花园
    ("P13", "L11", "L12"),  # 花园 - 后山
    # 服务设施
    ("P14", "L03", "L14"),  # 行政楼 - 医务室
    ("P15", "L03", "L15"),  # 行政楼 - 仓库
    ("P16", "L01", "L16"),  # 大礼堂 - 门卫室
    ("P17", "L03", "L18"),  # 行政楼 - 实验楼
    ("P18", "L12", "L17"),  # 后山 - 天文台
    # 秘密路径
    ("P19", "L15", "L19"),  # 仓库 - 密道入口 (secret)
    ("P20", "L19", "L20"),  # 密道入口 - 地下密室 (secret)
]

# ---- 组装输入 ----
locations = [
    models.LocationSpatialFact(location_id=lid, name=name, importance=imp, tags=tags)
    for lid, name, imp, tags in LOCATION_DEFS
]

# 标记秘密路径
paths = []
for pid, fid, tid in PATH_DEFS:
    is_secret = pid in ("P19", "P20")
    paths.append(models.PathSpatialFact(
        path_id=pid, from_location_id=fid, to_location_id=tid,
        is_secret=is_secret,
        tags=["secret"] if is_secret else [],
    ))

bi = models.SpatialBuildInput(
    world_id="test_20_locations",
    source_root="/tmp",
    locations=locations,
    paths=paths,
)

cfg = config_mod.SpatialGenerationConfig()

# ---- Phase B: 布局 ----
print("=" * 60)
print("Phase B: 图布局")
print("=" * 60)

gen = tl.TopologyLayoutGenerator()
layout = gen.generate(bi, cfg)

print(f"Grid: {layout.grid_width}x{layout.grid_height}")
print(f"Locations: {len(layout.locations)}")
print(f"Synthetic edges: {len(layout.synthetic_edges)}")
print(f"Warnings: {[w.code for w in layout.warnings]}")
print()
print(f"{'ID':<5} {'Name':<10} {'Center':<12} {'Layer'}")
print("-" * 35)
for loc in layout.locations:
    print(f"{loc.location_id:<5} {'':10} ({loc.center_x:3d}, {loc.center_y:3d})  {loc.layer_id}")

# ---- Phase C: 矩形放置 ----
print()
print("=" * 60)
print("Phase C: 约束矩形放置")
print("=" * 60)

packer = rp.RegionPacker()
result = packer.pack(layout, bi, cfg)

print(f"Placed: {len(result.regions)}/20")
print(f"Warnings: {len(result.warnings)}")
for w in result.warnings:
    print(f"  [{w.code}] {w.message}")

print()
print(f"{'ID':<5} {'Name':<10} {'Rect':<20} {'Entrance':<12} {'Tags'}")
print("-" * 70)
for r in result.regions:
    rect = f"({r.x:3d},{r.y:3d},{r.width:2d},{r.height:2d})"
    ent = f"({r.entrance_x:3d},{r.entrance_y:3d})"
    tags_str = ",".join(r.tags) if r.tags else ""
    print(f"{r.location_id:<5} {r.name:<10} {rect:<20} {ent:<12} {tags_str}")

# ---- 验证 ----
print()
print("=" * 60)
print("验证")
print("=" * 60)

# 无重叠检查
overlap_count = 0
for i, r1 in enumerate(result.regions):
    for r2 in result.regions[i + 1:]:
        if not (r1.x + r1.width <= r2.x or r2.x + r2.width <= r1.x or
                r1.y + r1.height <= r2.y or r2.y + r2.height <= r1.y):
            overlap_count += 1
            print(f"  OVERLAP: {r1.location_id} and {r2.location_id}")
if overlap_count == 0:
    print("无重叠: OK")

# 入口在边界上
entrance_ok = True
for r in result.regions:
    on_edge = (r.entrance_x == r.x or r.entrance_x == r.x + r.width - 1 or
               r.entrance_y == r.y or r.entrance_y == r.y + r.height - 1)
    if not on_edge:
        print(f"  ENTRANCE NOT ON EDGE: {r.location_id}")
        entrance_ok = False
if entrance_ok:
    print("所有入口在边界上: OK")

# 画布边界检查
bounds_ok = True
margin = cfg.canvas.margin_tiles
for r in result.regions:
    if r.x < margin or r.y < margin:
        print(f"  OUT OF BOUNDS: {r.location_id} ({r.x},{r.y})")
        bounds_ok = False
    if r.x + r.width > cfg.canvas.grid_width - margin:
        print(f"  OUT OF BOUNDS: {r.location_id} right edge")
        bounds_ok = False
    if r.y + r.height > cfg.canvas.grid_height - margin:
        print(f"  OUT OF BOUNDS: {r.location_id} bottom edge")
        bounds_ok = False
if bounds_ok:
    print("所有区域在画布边界内: OK")

# 核心地点靠近中心
center_x = cfg.canvas.grid_width // 2
center_y = cfg.canvas.grid_height // 2
core_regions = [r for r in result.regions if "core" in r.tags]
if core_regions:
    core_dists = []
    for r in core_regions:
        cx = r.x + r.width // 2
        cy = r.y + r.height // 2
        dist = abs(cx - center_x) + abs(cy - center_y)
        core_dists.append((r.location_id, dist))
    avg_core_dist = sum(d for _, d in core_dists) / len(core_dists)
    print(f"Core 平均距中心距离: {avg_core_dist:.1f}")

# Secret 地点靠边缘
secret_regions = [r for r in result.regions if "secret" in r.tags]
if secret_regions:
    secret_dists = []
    for r in secret_regions:
        edge = min(r.x, cfg.canvas.grid_width - r.x - r.width,
                   r.y, cfg.canvas.grid_height - r.y - r.height)
        secret_dists.append((r.location_id, edge))
    avg_secret_edge = sum(d for _, d in secret_dists) / len(secret_dists)
    print(f"Secret 平均距边缘距离: {avg_secret_edge:.1f}")

# 确定性检查
result2 = rp.RegionPacker().pack(layout, bi, cfg)
det_ok = all(
    r1.x == r2.x and r1.y == r2.y and r1.width == r2.width and r1.height == r2.height
    for r1, r2 in zip(result.regions, result2.regions)
)
print(f"确定性: {'OK' if det_ok else 'FAIL'}")

placed_ids = {r.location_id for r in result.regions}
missing = [lid for lid, _, _, _ in LOCATION_DEFS if lid not in placed_ids]
if missing:
    print(f"未放置的地点: {missing}")
else:
    print("所有 20 个地点均已放置: OK")

print()
print("=" * 60)
print("测试完成")
print("=" * 60)
