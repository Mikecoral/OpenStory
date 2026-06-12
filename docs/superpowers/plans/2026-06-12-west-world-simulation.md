# 西部世界正式仿真实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `examples/west_world_test` 从 Recorder MVE 扩展为完整的西部世界多智能体仿真：地图真值数据 + 每地点 LocationRecorder（文本 LLM）+ 从红楼梦迁移的运行骨架。

**Architecture:** 三层推进——M0 用脚本从 TMX 提取 zones 生成 `locations.yaml` 真值并配 loader/校验；M1 纯 Python TDD 实现 `LocationRecorder`（5 个状态块、4 个被动接口，FakeLLM 可测）；M2/M3 复用红楼梦的 Builder/Pod/Controller 管线，新建 `configs_sim/` + `registry_sim.py` + 新 agent 插件，先无 LLM 跑通骨架，再接入 Recorder 与自由 plan。

**Tech Stack:** Python 3.11、agentkernel_distributed（Ray + Redis）、pytest、PyYAML、OpenAI 兼容 LLM（复用 `adapters/model_clients.py`）。

**Spec:** `docs/superpowers/specs/2026-06-12-west-world-simulation-design.md`

---

## 前置事实（执行者必读）

- 运行测试前 `export PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed`（在仓库根 `OpenStory/` 下执行）。测试命令统一为 `python -m pytest examples/west_world_test/tests/... -v`。
- `Builder.load_config(project_path)` 硬编码读 `<project_path>/configs/simulation_config.yaml`（`packages/agentkernel-distributed/agentkernel_distributed/mas/builder.py:23-43`）。MVE（`run_test.py`）已占用 `configs/`，所以正式仿真用 `configs_sim/`，需要给 Builder 加可选参数（Task 10）。
- 数据文件路径相对 project_path 解析，支持 `.yaml/.jsonl/.json`（builder.py:60-77）。YAML 数据可注入插件配置：插件 config 中的字符串值若等于某 data key，会被替换成数据内容（参考 sots `relations: "agents_relation"`）。
- agent 插件经 `self._component.agent.controller` 拿 controller；`controller.run_environment(component_name, method_name, *args)` 可调用环境组件方法（`mas/controller/base.py:138`）；`controller.run_agent_method(...)` 可跨 agent 调方法（sots BasicInvokePlugin:226 有用例）。
- 环境组件用 `get_or_create_component_class(name)` 动态创建；插件继承 `GenericPlugin` 并设 `COMPONENT_TYPE`。每地点一个组件，组件名约定 `scene_<location_id>`。
- sots 的 `BasicPerceivePlugin`/`BasicMovePlugin`/`BasicOtherActionPlugin` 是空壳；真实逻辑在 `BasicPlanPlugin`（644 行）/`BasicInvokePlugin`（652 行）/`BasicReflectPlugin`。迁移时**不要**照搬空壳幻觉出的功能。
- MVE 的 `core/`、`scene/SceneRecorderPlugin.py`、`run_test.py`、`registry.py`、`configs/` 一律**不改不删**（`registry.py` 除外的增改也不允许；正式仿真用新文件 `registry_sim.py`）。

## 文件结构（全量）

```
examples/west_world_test/
├── map_total/extract_zones.py            # [M0新增] 一次性 TMX→骨架脚本（可重跑）
├── data/
│   ├── map/locations.yaml                # [M0新增] 地图真值（~30 地点）
│   ├── agents/profiles_sim.jsonl         # [M2新增] 6 个 host 的人设（含 narrative loop）
│   ├── agents/states_sim.jsonl           # [M2新增] 初始状态（location/known_map）
│   └── relations/relations_sim.jsonl     # [M2新增] 人物关系
├── worldmap/
│   ├── __init__.py                       # [M0新增]
│   └── loader.py                         # [M0新增] 加载/校验/邻接查询
├── recorder/
│   ├── __init__.py                       # [M1新增]
│   ├── location_recorder.py              # [M1新增] 核心类
│   ├── prompts.py                        # [M1新增] 裁决/更新 prompt
│   └── factory.py                        # [M1新增] 真实 LLM 工厂
├── plugins/
│   ├── environment/scene/LocationRecorderPlugin.py   # [M3新增] 内核接入壳
│   └── agent/
│       ├── perceive/WestWorldPerceivePlugin.py       # [M2占位/M3接Recorder]
│       ├── plan/RandomWalkPlanPlugin.py              # [M2新增] 无LLM随机游走
│       ├── plan/WestWorldPlanPlugin.py               # [M3新增] LLM自由决策+软引导
│       └── invoke/WestWorldInvokePlugin.py           # [M2移动/M3提交动作]
├── configs_sim/                          # [M2新增] 正式仿真全套配置
├── registry_sim.py                       # [M2新增]
├── run_simulation.py                     # [M2新增] 正式仿真入口
└── tests/
    ├── test_worldmap.py                  # [M0]
    ├── test_location_recorder.py         # [M1]
    └── test_sim_skeleton.py              # [M2/M3 集成，需 Redis 时跳过]
packages/agentkernel-distributed/agentkernel_distributed/mas/builder.py   # [M2修改] 加 configs_dirname
docs/  CLAUDE.md                          # [收尾更新 §7]
```

---

# M0 地图建模

### Task 1: TMX zones 提取脚本

**Files:**
- Create: `examples/west_world_test/map_total/extract_zones.py`

- [ ] **Step 1: 写脚本**

```python
"""一次性脚本：从西部世界 TMX 的 zones 对象层提取地点骨架。

用法（仓库根目录）：
    python examples/west_world_test/map_total/extract_zones.py > /tmp/zones_skeleton.yaml
产出骨架 YAML，供人工补全为 data/map/locations.yaml。可重跑。
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

TMX_PATH = Path(__file__).parent / "西部世界游戏地图.tmx"
# zones 层已知数据问题的修正表：object id -> 正确名称（None 表示忽略该对象）
NAME_FIXES = {
    959: None,            # 无名点对象，非地点
    969: None, 970: None, 971: None, 972: None, 974: None, 977: None,  # 甜水镇内无名点
    1015: None,           # 无名点对象
    982: "甜水镇医院",     # 属性名 typo：区域mingc
    1000: None,           # "后方控制区"重复点，保留 998
}


def extract() -> list[dict]:
    root = ET.parse(TMX_PATH).getroot()
    zones = next(og for og in root.findall("objectgroup") if og.get("name") == "zones")
    rows = []
    for obj in zones.findall("object"):
        oid = int(obj.get("id"))
        props = {p.get("name"): p.get("value") for p in obj.findall("./properties/property")}
        name = props.get("区域名称") or props.get("区域mingc")
        if oid in NAME_FIXES:
            name = NAME_FIXES[oid]
        if not name:
            print(f"# 跳过无名对象 id={oid}", file=sys.stderr)
            continue
        rows.append({
            "tmx_object_id": oid,
            "name": name,
            "bbox": [round(float(obj.get("x")), 1), round(float(obj.get("y")), 1),
                     round(float(obj.get("width") or 0), 1), round(float(obj.get("height") or 0), 1)],
        })
    return rows


if __name__ == "__main__":
    print(yaml.safe_dump(extract(), allow_unicode=True, sort_keys=False))
```

- [ ] **Step 2: 运行验证**

Run: `python examples/west_world_test/map_total/extract_zones.py | head -30`
Expected: 输出 YAML 列表，约 30 条记录，每条含 `tmx_object_id/name/bbox`；stderr 列出被跳过的无名对象。若实际跳过/修正集合与 `NAME_FIXES` 不符（以脚本运行结果为准），更新 `NAME_FIXES` 后重跑。

- [ ] **Step 3: Commit**

```bash
git add examples/west_world_test/map_total/extract_zones.py
git commit -m "feat(west-world): add TMX zones extraction script"
```

### Task 2: 编写地图真值 locations.yaml

**Files:**
- Create: `examples/west_world_test/data/map/locations.yaml`

- [ ] **Step 1: 用 Task 1 输出做骨架，按下表补全全部地点**

结构性真值如下表（id/region/type/active/adjacency 必须照此实现；`description`/`objects`/`default_occupants` 为创作内容，按 Step 2 的完整示例风格、结合西部世界原作知识撰写，每地点 description 2-4 句、objects 3-6 件）：

| id | name | region | type | active | adjacency |
|---|---|---|---|---|---|
| sweetwater | 甜水镇 | sweetwater | town | true | plaza、9 个室内地点、abernathy_ranch、wilderness、train（经火车站） |
| sweetwater_plaza | 甜水镇广场 | sweetwater | interior | true | sweetwater, sweetwater_saloon |
| sweetwater_saloon | 甜水镇酒馆 | sweetwater | interior | true | sweetwater, sweetwater_plaza |
| sweetwater_sheriff | 甜水镇警察局 | sweetwater | interior | true | sweetwater |
| sweetwater_post_office | 甜水镇邮局 | sweetwater | interior | true | sweetwater |
| sweetwater_train_station | 甜水镇火车站 | sweetwater | interior | true | sweetwater, train |
| sweetwater_hotel | 甜水镇旅店 | sweetwater | interior | true | sweetwater |
| sweetwater_hospital | 甜水镇医院 | sweetwater | interior | true | sweetwater |
| sweetwater_gunsmith | 甜水镇武器铺 | sweetwater | interior | true | sweetwater |
| sweetwater_tailor | 甜水镇裁缝铺 | sweetwater | interior | true | sweetwater |
| sweetwater_general_store | 甜水镇杂货铺 | sweetwater | interior | true | sweetwater |
| abernathy_ranch | 艾伯纳西农场 | sweetwater | interior | true | sweetwater |
| wilderness | 荒野 | wilderness | wilderness | false | sweetwater, pariah, frontier_town, mine, church, river, desert_bandit_hideout |
| train | 火车 | wilderness | interior | false | sweetwater_train_station |
| river | 河流 | wilderness | wilderness | false | wilderness |
| mine | 矿洞 | wilderness | wilderness | false | wilderness |
| church | 教堂 | frontier | interior | false | wilderness, frontier_town |
| desert_bandit_hideout | 沙漠土匪家 | wilderness | interior | false | wilderness |
| pariah | 帕里亚 | pariah | town | false | wilderness, pariah_casino, pariah_fight_pit |
| pariah_casino | 赌场 | pariah | interior | false | pariah |
| pariah_fight_pit | 格斗场 | pariah | interior | false | pariah |
| frontier_town | 边境小镇 | frontier | town | false | wilderness, frontier_outpost, church, host_room_1, host_home_2, ranch_farm |
| frontier_outpost | 边境驿站 | frontier | interior | false | frontier_town |
| host_room_1 | 接待员房间1 | frontier | interior | false | frontier_town |
| host_home_2 | 接待员家2 | frontier | interior | false | frontier_town |
| ranch_farm | 养殖场 | frontier | interior | false | frontier_town |
| surface_maintenance_station | 地表维修站 | backstage | backstage | false | backstage_control |
| backstage_control | 后方控制区 | backstage | backstage | false | surface_maintenance_station, cold_storage, staff_dormitory, programmer_workspace |
| cold_storage | 冷库存放区 | backstage | backstage | false | backstage_control |
| staff_dormitory | 员工宿舍 | backstage | backstage | false | backstage_control |
| programmer_workspace | 程序员工作区 | backstage | backstage | false | backstage_control |

补充规则：`bbox` 取 Task 1 输出（无对应 zone 的合成地点如 wilderness 用 `[0,0,0,0]`）；adjacency 写成无向（A 含 B 则 B 必含 A）；至少 2 个地点要有 `hidden: true` 物件（酒馆旧照片、农场地窖里的某物），格式见示例。

- [ ] **Step 2: 完整示例条目（前两条按此原样收录，风格基准）**

```yaml
- id: sweetwater_saloon
  name: 甜水镇酒馆
  region: sweetwater
  type: interior
  active: true
  bbox: [531.0, 428.0, 0, 0]
  adjacency: [sweetwater, sweetwater_plaza]
  description: >
    马里波萨酒馆是甜水镇的社交中心。昏黄的油灯下摆着一排吧台和几张牌桌，
    自动演奏钢琴循环放着走调的老歌，空气里混着威士忌、汗味和雪茄烟。
    二楼是招待客人的房间，楼梯口常年站着招呼客人的姑娘。
  objects:
    - {name: 自动演奏钢琴, note: 无人弹奏也会自行演奏，曲目固定循环}
    - {name: 吧台和成排酒瓶, note: 威士忌为主，酒保从不离开吧台太久}
    - {name: 几张牌桌, note: 常有客人玩扑克，偶尔起争执}
    - {name: 墙上的通缉令, note: 三名劫匪的悬赏告示，赏金五百美元}
    - {name: 旧照片, hidden: true, secret: 一张掉在角落的照片，上面是一个站在现代都市夜景中的女人——与这个时代格格不入}
  default_occupants: [maeve, clementine]

- id: abernathy_ranch
  name: 艾伯纳西农场
  region: sweetwater
  type: interior
  active: true
  bbox: [425.0, 901.0, 893.0, 265.0]
  adjacency: [sweetwater]
  description: >
    镇外的家庭农场，木屋、谷仓和一圈牧栏。清晨有牛群的铃铛声，
    门廊上摆着两把摇椅，画架立在能看见日落的位置。
  objects:
    - {name: 门廊摇椅, note: 彼得·艾伯纳西傍晚常坐在这里}
    - {name: 画架与颜料, note: 德洛丽丝用来写生}
    - {name: 谷仓, note: 存放饲料和马具}
    - {name: 牧栏里的牛群, note: 十几头长角牛}
  default_occupants: [dolores, peter_abernathy]
```

- [ ] **Step 3: 人工核对 bbox 与 Task 1 输出一致后提交**

```bash
git add examples/west_world_test/data/map/locations.yaml
git commit -m "feat(west-world): add map ground-truth locations.yaml"
```

### Task 3: worldmap 加载与校验模块（TDD）

**Files:**
- Create: `examples/west_world_test/worldmap/__init__.py`、`examples/west_world_test/worldmap/loader.py`
- Test: `examples/west_world_test/tests/test_worldmap.py`

- [ ] **Step 1: 写失败测试**

```python
"""Tests for the worldmap loader and validators."""
from pathlib import Path

import pytest

from examples.west_world_test.worldmap.loader import Location, WorldMap, load_world_map

LOCATIONS_PATH = str(Path(__file__).parents[1] / "data" / "map" / "locations.yaml")


@pytest.fixture()
def world() -> WorldMap:
    return load_world_map(LOCATIONS_PATH)


def test_loads_all_locations(world):
    assert len(world.locations) >= 25
    saloon = world.get("sweetwater_saloon")
    assert isinstance(saloon, Location)
    assert saloon.name == "甜水镇酒馆"
    assert saloon.active is True


def test_ids_unique_and_adjacency_symmetric(world):
    ids = [loc.id for loc in world.locations.values()]
    assert len(ids) == len(set(ids))
    for loc in world.locations.values():
        for nb in loc.adjacency:
            assert nb in world.locations, f"{loc.id} 邻接未知地点 {nb}"
            assert loc.id in world.get(nb).adjacency, f"{loc.id}->{nb} 非双向"


def test_active_subgraph_connected(world):
    active = world.active_ids()
    assert "sweetwater_saloon" in active and "abernathy_ranch" in active
    # 从任一激活地点 BFS 必须覆盖全部激活地点
    start = next(iter(active))
    seen, frontier = {start}, [start]
    while frontier:
        cur = frontier.pop()
        for nb in world.get(cur).adjacency:
            if nb in active and nb not in seen:
                seen.add(nb)
                frontier.append(nb)
    assert seen == active


def test_can_move_rules(world):
    assert world.can_move("sweetwater_saloon", "sweetwater_plaza") == (True, "")
    ok, reason = world.can_move("sweetwater_saloon", "abernathy_ranch")
    assert ok is False and "相邻" in reason          # 不邻接
    ok, reason = world.can_move("sweetwater", "wilderness")
    assert ok is False and reason                    # 邻接但目标未激活


def test_hidden_objects_and_visible_objects(world):
    saloon = world.get("sweetwater_saloon")
    visible = saloon.visible_objects()
    assert all(not o.get("hidden") for o in visible)
    assert any(o.get("hidden") for o in saloon.objects)  # 数据里确实存在 hidden 物件
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_worldmap.py -v`
Expected: FAIL（`ModuleNotFoundError: examples.west_world_test.worldmap`）

- [ ] **Step 3: 实现 loader.py**

`worldmap/__init__.py`：

```python
from .loader import Location, WorldMap, load_world_map

__all__ = ["Location", "WorldMap", "load_world_map"]
```

`worldmap/loader.py`：

```python
"""地图真值的加载、校验与查询。locations.yaml 是唯一真值源。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import yaml


@dataclass
class Location:
    id: str
    name: str
    region: str
    type: str                       # town | interior | wilderness | backstage
    active: bool
    bbox: List[float]
    adjacency: List[str]
    description: str = ""
    objects: List[Dict[str, Any]] = field(default_factory=list)
    default_occupants: List[str] = field(default_factory=list)

    def visible_objects(self) -> List[Dict[str, Any]]:
        return [o for o in self.objects if not o.get("hidden")]

    def hidden_objects(self) -> List[Dict[str, Any]]:
        return [o for o in self.objects if o.get("hidden")]


class WorldMap:
    def __init__(self, locations: List[Location]) -> None:
        self.locations: Dict[str, Location] = {loc.id: loc for loc in locations}
        self._validate(locations)

    def _validate(self, locations: List[Location]) -> None:
        if len(locations) != len(self.locations):
            raise ValueError("location id 重复")
        for loc in locations:
            for nb in loc.adjacency:
                if nb not in self.locations:
                    raise ValueError(f"{loc.id} 邻接未知地点 {nb}")
                if loc.id not in self.locations[nb].adjacency:
                    raise ValueError(f"邻接不对称: {loc.id} -> {nb}")

    def get(self, location_id: str) -> Location:
        return self.locations[location_id]

    def active_ids(self) -> set[str]:
        return {loc.id for loc in self.locations.values() if loc.active}

    def neighbors(self, location_id: str, active_only: bool = True) -> List[str]:
        nbs = self.get(location_id).adjacency
        if active_only:
            nbs = [n for n in nbs if self.get(n).active]
        return list(nbs)

    def can_move(self, src: str, dst: str) -> Tuple[bool, str]:
        if dst not in self.locations:
            return False, f"不存在名为 {dst} 的地方"
        if dst not in self.get(src).adjacency:
            return False, f"{self.get(dst).name} 与当前位置不相邻"
        if not self.get(dst).active:
            return False, f"通往{self.get(dst).name}的路被封锁了"
        return True, ""


def load_world_map(path: str) -> WorldMap:
    with open(path, "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)
    return WorldMap([Location(**row) for row in rows])
```

同时建空文件 `examples/west_world_test/tests/__init__.py` 若不存在（已存在则跳过）。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest examples/west_world_test/tests/test_worldmap.py -v`
Expected: 5 passed。若失败原因是 locations.yaml 数据问题（非对称邻接等），修数据不修校验。

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/worldmap examples/west_world_test/tests/test_worldmap.py
git commit -m "feat(west-world): add worldmap loader with validation"
```

### Task 4: 修正 TMX typo + ⛔ 用户审核关卡

**Files:**
- Modify: `examples/west_world_test/map_total/西部世界游戏地图.tmx`（仅 zones 层属性）

- [ ] **Step 1: 修 TMX**：object 982 的属性名 `区域mingc` → `区域名称`（用 Edit 工具改 XML 文本，不动其他内容）。
- [ ] **Step 2: 验证**：重跑 `python examples/west_world_test/map_total/extract_zones.py >/dev/null`，Expected: 正常输出无异常（脚本兼容修正前后两种属性名）。
- [ ] **Step 3: Commit**

```bash
git add examples/west_world_test/map_total/西部世界游戏地图.tmx
git commit -m "fix(west-world): correct zone property typo in TMX"
```

- [ ] **Step 4: ⛔ 停下来请用户审核 `data/map/locations.yaml`**（描述、物件、邻接、hidden 设定）。用户确认前不进入 M1。审核意见落实后重跑 Task 3 测试并提交修订。

---

# M1 LocationRecorder（纯 Python，TDD，不依赖 Ray/Redis）

### Task 5: prompts.py（裁决与更新 prompt）

**Files:**
- Create: `examples/west_world_test/recorder/__init__.py`、`examples/west_world_test/recorder/prompts.py`

- [ ] **Step 1: 写 prompts.py**

```python
"""LocationRecorder 的两类 LLM prompt：动作裁决、tick 状态合并更新。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

JUDGE_PROMPT = """你是西部世界主题乐园中地点「{location_name}」的场景记录员（Recorder）。
你掌握该地点的全部状态，包括只有你知道的秘密信息。现在一名角色提交了一个动作，请你裁决。

## 地点当前状态
[固定设施] {static_facilities}
[可变物品] {dynamic_objects}
[在场角色] {present_agents}
[近期事件] {recent_events}
[秘密信息（仅你可见，严禁直接照抄给角色，只在动作确实触及时按需透露相应内容）]
{hidden_notes}

## 提交的动作
角色: {agent_id}
动作: {action_text}

## 裁决要求
1. permission: 该动作在此场景下是否可行（物理上、常识上）。不可行要给出世界观内的理由。
2. private_feedback: 仅返回给行动者本人的结果描述。若动作触及秘密信息（如查看 hidden 物品），在这里透露其内容；与秘密无关则描述动作的直接结果。
3. broadcast_level: 该动作是否会被同地点其他人注意到。"none"=隐蔽（如悄悄捡起小物件），"location"=公开（如打碎杯子、大声争吵）。
4. event_summary: 若 broadcast_level 为 "location"，给一句话的旁观者视角事件描述；否则给空字符串。

只输出 JSON，不要输出其他内容：
{{"permission": true, "reason": "", "private_feedback": "...", "broadcast_level": "none", "event_summary": ""}}
"""

UPDATE_PROMPT = """你是西部世界主题乐园中地点「{location_name}」的场景记录员。一个时间刻（tick {tick}）刚结束，
请根据本 tick 发生的动作，更新场景的三个状态块。要求：忠实于已发生的裁决结果，不要发明未发生的事；
保持简洁的客观描述；没有变化的内容原样保留。

## 更新前状态
[可变物品] {dynamic_objects}
[在场角色] {present_agents}
[近期事件] {recent_events}

## 本 tick 已裁决的动作（含裁决结果，视为既定事实）
{actions_log}

只输出 JSON，不要输出其他内容：
{{"dynamic_objects": "...", "present_agents": "...", "recent_events": ["最新事件一句话", "..."]}}
"""


def render_judge(location_name: str, chunks: Dict[str, Any], agent_id: str, action_text: str) -> str:
    return JUDGE_PROMPT.format(
        location_name=location_name, agent_id=agent_id, action_text=action_text,
        static_facilities=chunks["static_facilities"], dynamic_objects=chunks["dynamic_objects"],
        present_agents=chunks["present_agents"], recent_events="\n".join(chunks["recent_events"]),
        hidden_notes=chunks["hidden_notes"],
    )


def render_update(location_name: str, tick: int, chunks: Dict[str, Any], actions_log: List[Dict[str, Any]]) -> str:
    return UPDATE_PROMPT.format(
        location_name=location_name, tick=tick,
        dynamic_objects=chunks["dynamic_objects"], present_agents=chunks["present_agents"],
        recent_events="\n".join(chunks["recent_events"]),
        actions_log=json.dumps(actions_log, ensure_ascii=False, indent=1),
    )
```

`recorder/__init__.py`：

```python
from .location_recorder import LocationRecorder

__all__ = ["LocationRecorder"]
```

（此时 import 会失败，下一个 task 实现后才生效——先不提交，与 Task 6 一起提交。）

### Task 6: LocationRecorder 初始化 / read / enter / leave（无 LLM 路径）

**Files:**
- Create: `examples/west_world_test/recorder/location_recorder.py`
- Test: `examples/west_world_test/tests/test_location_recorder.py`

- [ ] **Step 1: 写失败测试**

```python
"""Tests for LocationRecorder（FakeLLM，无需 Ray/Redis）。"""
import json

from examples.west_world_test.adapters.model_clients import FakeLLM
from examples.west_world_test.recorder.location_recorder import LocationRecorder
from examples.west_world_test.worldmap.loader import Location

SALOON = Location(
    id="sweetwater_saloon", name="甜水镇酒馆", region="sweetwater", type="interior",
    active=True, bbox=[0, 0, 0, 0], adjacency=["sweetwater"],
    description="昏黄的灯光下摆着吧台和几张牌桌。",
    objects=[
        {"name": "自动演奏钢琴", "note": "循环播放老歌"},
        {"name": "旧照片", "hidden": True, "secret": "照片上是现代都市夜景"},
    ],
    default_occupants=["maeve"],
)


def make_recorder(replies=None):
    return LocationRecorder(location=SALOON, llm=FakeLLM(replies or []))


def test_init_builds_chunks_from_location():
    rec = make_recorder()
    assert "吧台" in rec.chunks["static_facilities"]
    assert "钢琴" in rec.chunks["static_facilities"]
    assert "旧照片" not in rec.chunks["static_facilities"]      # hidden 不进可见块
    assert "现代都市" in rec.chunks["hidden_notes"]
    assert "maeve" in rec.chunks["present_agents"]


def test_read_returns_requested_chunks_and_never_hidden():
    rec = make_recorder()
    out = rec.read("dolores", ["present_agents", "recent_events", "hidden_notes"])
    assert set(out) == {"present_agents", "recent_events"}      # hidden_notes 被剥除
    out2 = rec.read("dolores", ["static_facilities"])
    assert "吧台" in out2["static_facilities"]


def test_enter_and_leave_update_presence():
    rec = make_recorder()
    desc = rec.agent_enter("dolores")
    assert "吧台" in desc and "钢琴" in desc                    # 初见描述含可见物件
    assert "dolores" in rec.chunks["present_agents"]
    rec.agent_leave("dolores")
    assert "dolores" not in rec.chunks["present_agents"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: FAIL（`location_recorder` 模块不存在）

- [ ] **Step 3: 实现**

```python
"""每地点一个的场景记录员：分块状态 + 被动调用接口。

LLM 只在 submit_action（裁决）和 tick_update（合并更新）两处被调用；
read/enter/leave 是纯文本操作。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from examples.west_world_test.worldmap.loader import Location
from . import prompts

logger = logging.getLogger(__name__)

RECENT_EVENTS_WINDOW = 10
READABLE_CHUNKS = {"static_facilities", "dynamic_objects", "present_agents", "recent_events"}
FALLBACK_JUDGEMENT = {
    "permission": True, "reason": "", "private_feedback": "",
    "broadcast_level": "none", "event_summary": "",
}


class LocationRecorder:
    def __init__(self, location: Location, llm: Any) -> None:
        self.location = location
        self.llm = llm
        visible = "；".join(f"{o['name']}（{o.get('note', '')}）" for o in location.visible_objects())
        self.chunks: Dict[str, Any] = {
            "static_facilities": f"{location.description.strip()} 设施与陈设：{visible}",
            "dynamic_objects": "暂无特别状态。",
            "present_agents": "、".join(location.default_occupants) or "（无人）",
            "recent_events": [],
            "hidden_notes": "\n".join(f"{o['name']}: {o.get('secret', '')}" for o in location.hidden_objects()) or "（无）",
        }
        self._pending_actions: List[Dict[str, Any]] = []

    # ---- 被动读取（无 LLM） ----
    def read(self, agent_id: str, chunk_names: List[str]) -> Dict[str, Any]:
        wanted = [c for c in chunk_names if c in READABLE_CHUNKS]
        return {c: self.chunks[c] for c in wanted}

    def agent_enter(self, agent_id: str) -> str:
        present = self._present_set()
        present.add(agent_id)
        self.chunks["present_agents"] = "、".join(sorted(present))
        return self.chunks["static_facilities"]

    def agent_leave(self, agent_id: str) -> None:
        present = self._present_set()
        present.discard(agent_id)
        self.chunks["present_agents"] = "、".join(sorted(present)) or "（无人）"

    def _present_set(self) -> set:
        raw = self.chunks["present_agents"]
        return set() if raw == "（无人）" else {x for x in raw.split("、") if x}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder examples/west_world_test/tests/test_location_recorder.py
git commit -m "feat(west-world): LocationRecorder chunks, read, enter/leave"
```

### Task 7: submit_action（LLM 裁决 + 降级）

**Files:**
- Modify: `examples/west_world_test/recorder/location_recorder.py`
- Test: `examples/west_world_test/tests/test_location_recorder.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
JUDGE_PICK_PHOTO = json.dumps({
    "permission": True, "reason": "",
    "private_feedback": "你捡起照片：照片上是现代都市夜景。",
    "broadcast_level": "none", "event_summary": "",
}, ensure_ascii=False)

JUDGE_BREAK_GLASS = json.dumps({
    "permission": True, "reason": "",
    "private_feedback": "杯子在你手里碎了。",
    "broadcast_level": "location", "event_summary": "有人打碎了一只酒杯。",
}, ensure_ascii=False)


def test_submit_action_secret_leaks_only_via_private_feedback():
    rec = make_recorder([JUDGE_PICK_PHOTO])
    result = rec.submit_action("dolores", "偷偷捡起角落里的旧照片")
    assert result["permission"] is True
    assert "现代都市" in result["private_feedback"]
    assert rec._pending_actions[0]["broadcast_level"] == "none"
    # 公开块此刻仍无泄露
    assert "现代都市" not in json.dumps(rec.read("teddy", list(rec.chunks)), ensure_ascii=False)


def test_submit_action_broadcast_queues_event():
    rec = make_recorder([JUDGE_BREAK_GLASS])
    result = rec.submit_action("maeve", "把酒杯摔在地上")
    assert result["broadcast_level"] == "location"
    assert rec._pending_actions[0]["event_summary"]


def test_submit_action_invalid_json_retries_then_degrades():
    rec = make_recorder(["不是JSON", "还不是JSON"])
    result = rec.submit_action("teddy", "推开后门")
    assert result["permission"] is True          # 降级：允许
    assert result["private_feedback"] == ""      # 降级：无反馈
    assert result["broadcast_level"] == "none"   # 降级：不广播
    assert len(rec.llm.calls) == 2               # 重试了一次
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: 新增 3 个 FAIL（`submit_action` 不存在），旧 3 个 PASS

- [ ] **Step 3: 实现（追加到 LocationRecorder 类）**

```python
    # ---- 动作裁决（每动作一次 LLM） ----
    def submit_action(self, agent_id: str, action_text: str) -> Dict[str, Any]:
        prompt = prompts.render_judge(self.location.name, self.chunks, agent_id, action_text)
        judgement = self._chat_json(prompt, retries=1)
        if judgement is None:
            logger.warning("[%s] 裁决 JSON 解析失败，降级为允许/无反馈/不广播: %s", self.location.id, action_text)
            judgement = dict(FALLBACK_JUDGEMENT)
        record = {"agent_id": agent_id, "action": action_text, **judgement}
        self._pending_actions.append(record)
        return judgement

    def _chat_json(self, prompt: str, retries: int) -> Optional[Dict[str, Any]]:
        for _ in range(retries + 1):
            raw = self.llm.chat(prompt)
            try:
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("```")[1].lstrip("json").strip()
                return json.loads(text)
            except (json.JSONDecodeError, IndexError):
                continue
        return None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/location_recorder.py examples/west_world_test/tests/test_location_recorder.py
git commit -m "feat(west-world): LocationRecorder action judgement with fallback"
```

### Task 8: tick_update（合并更新 + 滚动窗口 + 失败保留旧状态）

**Files:**
- Modify: `examples/west_world_test/recorder/location_recorder.py`
- Test: `examples/west_world_test/tests/test_location_recorder.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
UPDATE_OK = json.dumps({
    "dynamic_objects": "地上有酒杯碎片。",
    "present_agents": "maeve、teddy",
    "recent_events": ["有人打碎了一只酒杯。"],
}, ensure_ascii=False)


def test_tick_update_merges_pending_and_clears_queue():
    rec = make_recorder([JUDGE_BREAK_GLASS, UPDATE_OK])
    rec.submit_action("maeve", "把酒杯摔在地上")
    rec.tick_update(tick=3)
    assert "碎片" in rec.chunks["dynamic_objects"]
    assert rec.chunks["recent_events"] == ["有人打碎了一只酒杯。"]
    assert rec._pending_actions == []
    assert len(rec.llm.calls) == 2          # 裁决 1 次 + 更新 1 次


def test_tick_update_no_pending_skips_llm():
    rec = make_recorder()
    rec.tick_update(tick=1)
    assert rec.llm.calls == []


def test_tick_update_failure_keeps_old_state():
    rec = make_recorder([JUDGE_BREAK_GLASS, "坏输出", "又坏"])
    rec.submit_action("maeve", "把酒杯摔在地上")
    before = dict(rec.chunks)
    rec.tick_update(tick=3)
    assert rec.chunks["dynamic_objects"] == before["dynamic_objects"]   # 保留旧状态
    assert rec._pending_actions == []                                   # 队列仍清空


def test_recent_events_rolling_window():
    rec = make_recorder()
    rec.chunks["recent_events"] = [f"事件{i}" for i in range(10)]
    update = json.dumps({"dynamic_objects": "x", "present_agents": "y",
                         "recent_events": [f"事件{i}" for i in range(10)] + ["新事件"]}, ensure_ascii=False)
    rec.llm = type(rec.llm)([JUDGE_BREAK_GLASS, update])
    rec.submit_action("maeve", "把酒杯摔在地上")
    rec.tick_update(tick=4)
    assert len(rec.chunks["recent_events"]) == 10
    assert rec.chunks["recent_events"][-1] == "新事件"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: 新增 4 个 FAIL（`tick_update` 不存在）

- [ ] **Step 3: 实现（追加到类）**

```python
    # ---- tick 末结算（每地点每 tick 至多一次 LLM） ----
    def tick_update(self, tick: int) -> None:
        if not self._pending_actions:
            return
        actions_log = self._pending_actions
        self._pending_actions = []
        prompt = prompts.render_update(self.location.name, tick, self.chunks, actions_log)
        update = self._chat_json(prompt, retries=1)
        if update is None:
            logger.error("[%s] tick %s 更新失败，保留旧状态块", self.location.id, tick)
            return
        for key in ("dynamic_objects", "present_agents"):
            if isinstance(update.get(key), str) and update[key].strip():
                self.chunks[key] = update[key]
        events = update.get("recent_events")
        if isinstance(events, list):
            self.chunks["recent_events"] = [str(e) for e in events][-RECENT_EVENTS_WINDOW:]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/location_recorder.py examples/west_world_test/tests/test_location_recorder.py
git commit -m "feat(west-world): LocationRecorder tick merge update"
```

### Task 9: 真实 LLM 工厂 + 手动冒烟脚本

**Files:**
- Create: `examples/west_world_test/recorder/factory.py`

- [ ] **Step 1: 写 factory.py**

```python
"""用 models_config.yaml 的 text 角色构建带真实 LLM 的 LocationRecorder。"""
from __future__ import annotations

from examples.west_world_test.adapters.model_clients import build_llm
from examples.west_world_test.worldmap.loader import Location, load_world_map
from .location_recorder import LocationRecorder


def build_recorder(location: Location, models_config_path: str) -> LocationRecorder:
    return LocationRecorder(location=location, llm=build_llm(models_config_path))


def build_active_recorders(locations_path: str, models_config_path: str) -> dict[str, LocationRecorder]:
    world = load_world_map(locations_path)
    llm = build_llm(models_config_path)
    return {lid: LocationRecorder(location=world.get(lid), llm=llm)
            for lid in sorted(world.active_ids())}
```

注意：先确认 `adapters/model_clients.py` 中真实构建函数名（`build_llm`），若签名不同按实际调整。

- [ ] **Step 2: 手动冒烟（有 models_config.yaml 时执行，否则跳过并记录）**

```bash
python - <<'EOF'
from examples.west_world_test.recorder.factory import build_active_recorders
recs = build_active_recorders(
    "examples/west_world_test/data/map/locations.yaml",
    "examples/west_world_test/configs/models_config.yaml")
saloon = recs["sweetwater_saloon"]
print(saloon.submit_action("dolores", "偷偷捡起角落里的旧照片"))
saloon.tick_update(1)
print(saloon.chunks["recent_events"], saloon.chunks["dynamic_objects"])
EOF
```

Expected: 真实模型返回合法 JSON 裁决；偷捡照片的 private_feedback 包含照片秘密、broadcast 为 none。若模型频繁输出非 JSON，调整 `prompts.py` 措辞（加重"只输出 JSON"约束）而非改解析逻辑。

- [ ] **Step 3: Commit**

```bash
git add examples/west_world_test/recorder/factory.py
git commit -m "feat(west-world): real-LLM recorder factory"
```

---

# M2 框架迁移骨架（无 Recorder、无 LLM，先跑通）

### Task 10: Builder 支持自定义 configs 目录名（内核小改，向后兼容）

**Files:**
- Modify: `packages/agentkernel-distributed/agentkernel_distributed/mas/builder.py`
- Test: `packages/agentkernel-distributed/tests/`（若该目录已有测试约定则随之，否则建 `test_builder_configs_dirname.py`）

- [ ] **Step 1: 写失败测试**

```python
"""load_config 应支持非默认 configs 目录名。"""
import os

import pytest
import yaml

from agentkernel_distributed.mas.builder import load_config


def _write_minimal_project(tmp_path, dirname):
    cfg_dir = tmp_path / dirname
    cfg_dir.mkdir()
    (cfg_dir / "simulation_config.yaml").write_text(yaml.safe_dump({
        "simulation": {"pod_size": 1, "init_batch_size": 1, "max_ticks": 1},
        "configs": {}, "data": {},
    }), encoding="utf-8")
    return str(tmp_path)


def test_default_dirname_unchanged(tmp_path):
    project = _write_minimal_project(tmp_path, "configs")
    config = load_config(project)
    assert config.simulation.pod_size == 1


def test_custom_dirname(tmp_path):
    project = _write_minimal_project(tmp_path, "configs_sim")
    config = load_config(project, configs_dirname="configs_sim")
    assert config.simulation.pod_size == 1
```

注意：若最小 config 不满足 `Config` pydantic 模型必填字段，按 `types/configs/` 的模型补齐必填键，保持测试最小。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest packages/agentkernel-distributed/tests/test_builder_configs_dirname.py -v`
Expected: `test_custom_dirname` FAIL（unexpected keyword `configs_dirname`）

- [ ] **Step 3: 实现**：`load_config(project_path: str, configs_dirname: str = "configs")`，函数体内 `configs_base_dir = os.path.join(project_path, configs_dirname)`；`Builder.__init__(self, project_path, resource_maps, configs_dirname="configs")` 透传给 `load_config`。其余不动。

- [ ] **Step 4: 跑测试确认通过 + 回归 MVE**

Run: `python -m pytest packages/agentkernel-distributed/tests/test_builder_configs_dirname.py examples/west_world_test/tests -v`
Expected: 全部 PASS（确认 MVE 测试未被破坏）

- [ ] **Step 5: Commit**

```bash
git add packages/agentkernel-distributed
git commit -m "feat(kernel): allow custom configs dirname in Builder (backwards compatible)"
```

### Task 11: 正式仿真全套配置 configs_sim/

**Files:**
- Create: `examples/west_world_test/configs_sim/{simulation_config,environment_config,actions_config,agents_config,system_config,db_config}.yaml`

- [ ] **Step 1: 写六个 yaml**

`simulation_config.yaml`：

```yaml
simulation:
  pod_size: 7
  init_batch_size: 7
  max_ticks: 40
configs:
  environment: "environment_config.yaml"
  actions: "actions_config.yaml"
  agent_templates: "agents_config.yaml"
  system: "system_config.yaml"
  database: "db_config.yaml"
  models: "../configs/models_config.yaml"   # 复用 MVE 的模型配置（相对 configs_sim/）
data:
  agent_profiles: "data/agents/profiles_sim.jsonl"
  agent_states: "data/agents/states_sim.jsonl"
  agents_relation: "data/relations/relations_sim.jsonl"
  map_locations: "data/map/locations.yaml"
```

`environment_config.yaml`（M2 只有 relation；M3 由 Task 16 改为含 scene_*）：

```yaml
name: WestWorldEnvironment
components:
  relation:
    plugin:
      BasicRelationPlugin:
        adapters: {}
        relations: "agents_relation"
```

`actions_config.yaml`（沿用 sots 三件套壳，保证内核装配路径不变）：

```yaml
name: WestWorldActions
components:
  communication:
    plugins:
      BasicCommunicationPlugin:
        adapters:
          adapter: RedisKVAdapter
          redis: RedisKVAdapter
  move:
    plugins:
      BasicMovePlugin:
        adapters:
          adapter: RedisKVAdapter
          redis: RedisKVAdapter
  otheractions:
    plugins:
      BasicOtherActionPlugin:
        adapters:
          adapter: RedisKVAdapter
          redis: RedisKVAdapter
```

`agents_config.yaml`：

```yaml
templates:
  - name: WestWorldHost
    component_order: ["perceive", "plan", "invoke", "state"]
    components:
      profile:
        plugin:
          BasicProfilePlugin:
            adapters:
              redis: "RedisKVAdapter"
            profile_data: "agent_profiles"
      state:
        plugin:
          BasicStatePlugin:
            adapters:
              adapter: "RedisKVAdapter"
            state_data: "agent_states"
      perceive:
        plugin:
          WestWorldPerceivePlugin:
            adapters: {}
            locations: "map_locations"
      plan:
        plugin:
          RandomWalkPlanPlugin:        # M3 的 Task 17 换成 WestWorldPlanPlugin
            adapters: {}
            locations: "map_locations"
      invoke:
        plugin:
          WestWorldInvokePlugin:
            adapters: {}
            locations: "map_locations"
```

`system_config.yaml` 与 `db_config.yaml`：从 `examples/west_world_test/configs/` 原样复制（system 含 messager/timer；recorder 系统组件即 Postgres 日志器，保持与 MVE 相同的关闭/开启状态）。

- [ ] **Step 2: 验证 yaml 可解析**

Run: `python -c "import yaml,glob; [yaml.safe_load(open(p)) for p in glob.glob('examples/west_world_test/configs_sim/*.yaml')]; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add examples/west_world_test/configs_sim
git commit -m "feat(west-world): simulation config set (configs_sim)"
```

### Task 12: Agent 数据（6 人阵容 + 关系）

**Files:**
- Create: `examples/west_world_test/data/agents/profiles_sim.jsonl`、`data/agents/states_sim.jsonl`、`data/relations/relations_sim.jsonl`

- [ ] **Step 1: profiles_sim.jsonl**（每行一个 agent；`narrative_loop` 即软引导文本，会进 plan prompt。下面 dolores 一条为完整基准，其余 5 条照此结构撰写，要点已给出）：

```jsonl
{"id": "dolores", "姓名": "德洛丽丝·艾伯纳西", "性别": "女", "身份": "农场主的女儿", "性格": "温柔、乐观、好奇，相信人们终会选择看到世界美好的一面", "语言风格": "柔和、诗意，偶尔出神", "narrative_loop": "清晨在艾伯纳西农场醒来，帮父亲料理家务；上午骑马去甜水镇，在杂货铺采购，常在广场掉落一只罐头；下午在镇上闲逛或与熟人交谈；傍晚回农场路上支起画架写生，晚上听父亲讲过去的事。", "背景经历": "在农场长大，母亲早逝，与父亲彼得相依为命。最近偶尔会做一些说不清的梦。"}
```

其余 5 条要点：
- `teddy`（泰迪·弗勒德，赏金猎人/牛仔）：loop=每天乘火车抵达甜水镇火车站→去酒馆喝一杯→在镇上寻找德洛丽丝→傍晚护送她回农场方向；性格忠诚、克制、身手好。
- `maeve`（梅芙·米莱，酒馆老板娘）：loop=整日在酒馆张罗生意，招呼客人、管教姑娘们、与酒保对账；性格精明、利落、嘴上不饶人。
- `clementine`（克莱门汀，酒馆侍女）：loop=在酒馆陪客、靠在二楼栏杆招呼路人；性格甜美、顺从。
- `peter_abernathy`（彼得·艾伯纳西，农场主）：loop=清晨放牛、白天修理牧栏、傍晚坐门廊摇椅看日落，等女儿回家；性格沉稳、慈爱、话少。
- `sheriff_pickett`（皮克特警长）：loop=上午在警察局处理文书、白天在镇内巡逻（广场—街道—酒馆门口）、有冲突时介入调停；性格严肃、公正。

- [ ] **Step 2: states_sim.jsonl**（`location` 用 locations.yaml 的 id；`known_map` 初始为各自 loop 涉及的地点）：

```jsonl
{"id": "dolores", "location": "abernathy_ranch", "health": "良好", "mood": "平静", "known_map": ["abernathy_ranch", "sweetwater", "sweetwater_plaza", "sweetwater_general_store"]}
{"id": "teddy", "location": "sweetwater_train_station", "health": "良好", "mood": "平静", "known_map": ["sweetwater_train_station", "sweetwater", "sweetwater_saloon", "sweetwater_plaza"]}
{"id": "maeve", "location": "sweetwater_saloon", "health": "良好", "mood": "平静", "known_map": ["sweetwater_saloon", "sweetwater", "sweetwater_plaza"]}
{"id": "clementine", "location": "sweetwater_saloon", "health": "良好", "mood": "平静", "known_map": ["sweetwater_saloon", "sweetwater"]}
{"id": "peter_abernathy", "location": "abernathy_ranch", "health": "良好", "mood": "平静", "known_map": ["abernathy_ranch", "sweetwater"]}
{"id": "sheriff_pickett", "location": "sweetwater_sheriff", "health": "良好", "mood": "平静", "known_map": ["sweetwater_sheriff", "sweetwater", "sweetwater_plaza", "sweetwater_saloon"]}
```

注意：先读 `examples/story_of_the_stone/data/agents/states.jsonl` 一行确认 BasicStatePlugin 期望的字段名（如 `id` 键名、必填字段），按实际 schema 对齐，再套上面内容。

- [ ] **Step 3: relations_sim.jsonl**（格式对齐 sots `data/relations/relations.jsonl`，先读其首行确认 schema）。关系内容：dolores—peter_abernathy（父女）、dolores—teddy（恋人/互相牵挂）、maeve—clementine（雇主与侍女）、teddy—maeve（熟客）、sheriff_pickett—全镇（治安官与镇民）。

- [ ] **Step 4: Commit**

```bash
git add examples/west_world_test/data/agents/profiles_sim.jsonl examples/west_world_test/data/agents/states_sim.jsonl examples/west_world_test/data/relations/relations_sim.jsonl
git commit -m "feat(west-world): six-host agent data with narrative loops"
```

### Task 13: M2 三个 agent 插件（perceive 占位 / 随机游走 plan / invoke 执行移动）

**Files:**
- Create: `examples/west_world_test/plugins/agent/perceive/WestWorldPerceivePlugin.py`
- Create: `examples/west_world_test/plugins/agent/plan/RandomWalkPlanPlugin.py`
- Create: `examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py`
- Create: 各目录 `__init__.py`（perceive/invoke 目录是新建的）
- Test: `examples/west_world_test/tests/test_sim_plugins.py`

插件间通过 agent 实例上的约定属性传递本 tick 数据：perceive 写 `agent._ww_percept`（dict），plan 写 `agent._ww_decision`（dict），invoke 消费并落实。状态读写复用 BasicStatePlugin 所在 state 组件（通过 `self._component.agent` 访问兄弟组件；先读 `examples/story_of_the_stone/plugins/agent/state/component.py` 确认 getter/setter 方法名，下面代码按 `get_state()/update_state(dict)` 写，名字不符则按实际调整）。

- [ ] **Step 1: 写失败测试**（用最小 stub agent 测三个插件的纯逻辑，不起 Ray）：

```python
"""M2 插件逻辑测试：占位感知、随机游走、移动落实（无 Ray/Redis）。"""
import asyncio
from pathlib import Path

from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import build_percept
from examples.west_world_test.plugins.agent.plan.RandomWalkPlanPlugin import decide
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import apply_move
from examples.west_world_test.worldmap.loader import load_world_map

WORLD = load_world_map(str(Path(__file__).parents[1] / "data" / "map" / "locations.yaml"))


def test_percept_contains_description_and_known_neighbors():
    state = {"location": "sweetwater_saloon", "known_map": ["sweetwater_saloon", "sweetwater"]}
    percept = build_percept(WORLD, "dolores", state)
    assert "酒馆" in percept["here_description"]
    assert percept["neighbors"] == ["sweetwater", "sweetwater_plaza"]   # 直接邻接全部可见（含未探索）
    assert "sweetwater_plaza" not in percept["known_map"]


def test_random_walk_only_picks_active_neighbors_or_stay():
    state = {"location": "sweetwater", "known_map": ["sweetwater"]}
    percept = build_percept(WORLD, "teddy", state)
    for seed in range(20):
        decision = decide(percept, seed=seed)
        assert decision["action"] in ("stay", "move")
        if decision["action"] == "move":
            assert decision["target"] in percept["neighbors"]


def test_apply_move_updates_state_and_known_map():
    state = {"location": "sweetwater_saloon", "known_map": ["sweetwater_saloon"]}
    new_state, ok, reason = apply_move(WORLD, state, "sweetwater_plaza")
    assert ok and new_state["location"] == "sweetwater_plaza"
    assert "sweetwater_plaza" in new_state["known_map"]
    new_state2, ok2, reason2 = apply_move(WORLD, state, "abernathy_ranch")   # 不邻接
    assert not ok2 and new_state2["location"] == "sweetwater_saloon" and reason2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_sim_plugins.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现三个插件**。每个文件分两层：**纯函数**（被上面测试覆盖）+ **Plugin 壳**（接内核钩子）。

`WestWorldPerceivePlugin.py`：

```python
"""感知插件：M2 用地图静态信息占位；M3 在 execute 中追加 Recorder read。"""
from __future__ import annotations

from typing import Any, Dict, List

from agentkernel_distributed.mas.agent.base.plugin_base import PerceivePlugin
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.worldmap.loader import Location, WorldMap

logger = get_logger(__name__)


def build_percept(world: WorldMap, agent_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    here = world.get(state["location"])
    return {
        "location": here.id,
        "here_description": here.description,
        "neighbors": world.neighbors(here.id, active_only=True),
        "known_map": list(state.get("known_map", [])),
    }


class WestWorldPerceivePlugin(PerceivePlugin):
    def __init__(self, locations: Any = None, **kwargs) -> None:
        super().__init__()
        # locations 经 Builder 数据注入，是 locations.yaml 解析后的 list[dict]
        self._world = WorldMap([Location(**row) for row in _rows(locations)])

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        state = await _read_state(agent)
        agent._ww_percept = build_percept(self._world, agent.agent_id, state)


def _rows(locations: Any) -> list:
    # Builder 对 jsonl 注入 {id: row}，对 yaml list 注入原样列表；两种都兼容
    if isinstance(locations, dict):
        return list(locations.values())
    return list(locations or [])


async def _read_state(agent) -> Dict[str, Any]:
    state_component = agent._components["state"]
    return await state_component.get_state()
```

注意两处接口名要现场核实并统一：`agent.agent_id` 与 `agent._components["state"].get_state()`——打开 `mas/agent/agent.py` 与 sots `plugins/agent/state/component.py` 确认真实属性/方法名，三个插件用同一套；`_rows` 的两种注入形态也要在 Task 15 集成时打印确认一次。

`RandomWalkPlanPlugin.py`：

```python
"""M2 占位决策：随机停留或移动到激活邻接地点，不调 LLM。"""
from __future__ import annotations

import random
from typing import Any, Dict

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin


def decide(percept: Dict[str, Any], seed: int | None = None) -> Dict[str, Any]:
    rng = random.Random(seed)
    neighbors = percept["neighbors"]
    if neighbors and rng.random() < 0.5:
        return {"action": "move", "target": rng.choice(neighbors)}
    return {"action": "stay", "target": ""}


class RandomWalkPlanPlugin(PlanPlugin):
    def __init__(self, locations: Any = None, **kwargs) -> None:
        super().__init__()

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        agent._ww_decision = decide(getattr(agent, "_ww_percept", {"neighbors": []}))
```

`WestWorldInvokePlugin.py`：

```python
"""执行插件：落实 plan 决策。M2 只处理 move/stay；M3 追加 submit_action 与 Recorder 联动。"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from agentkernel_distributed.mas.agent.base.plugin_base import InvokePlugin
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.worldmap.loader import Location, WorldMap
from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import _read_state, _rows

logger = get_logger(__name__)


def apply_move(world: WorldMap, state: Dict[str, Any], target: str) -> Tuple[Dict[str, Any], bool, str]:
    ok, reason = world.can_move(state["location"], target)
    if not ok:
        return dict(state), False, reason
    new_state = dict(state)
    new_state["location"] = target
    known = list(state.get("known_map", []))
    if target not in known:
        known.append(target)
    new_state["known_map"] = known
    return new_state, True, ""


class WestWorldInvokePlugin(InvokePlugin):
    def __init__(self, locations: Any = None, **kwargs) -> None:
        super().__init__()
        self._world = WorldMap([Location(**row) for row in _rows(locations)])

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        decision = getattr(agent, "_ww_decision", {"action": "stay"})
        if decision.get("action") != "move":
            return
        state = await _read_state(agent)
        new_state, ok, reason = apply_move(self._world, state, decision["target"])
        if not ok:
            logger.info("[%s] tick %s 移动被拒: %s", agent.agent_id, current_tick, reason)
            return
        await agent._components["state"].update_state(new_state)
        logger.info("[%s] tick %s 移动 %s -> %s", agent.agent_id, current_tick, state["location"], new_state["location"])
```

InvokePlugin/PerceivePlugin/PlanPlugin 的基类名以 `mas/agent/base/plugin_base.py` 实际导出为准。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest examples/west_world_test/tests/test_sim_plugins.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/plugins examples/west_world_test/tests/test_sim_plugins.py
git commit -m "feat(west-world): M2 perceive/plan/invoke plugins (no LLM)"
```

### Task 14: registry_sim.py + run_simulation.py 入口

**Files:**
- Create: `examples/west_world_test/registry_sim.py`
- Create: `examples/west_world_test/run_simulation.py`

- [ ] **Step 1: registry_sim.py**

```python
"""正式仿真的资源注册表（与 MVE 的 registry.py 并存）。"""
from agentkernel_distributed.mas.agent.components import (
    InvokeComponent, PerceiveComponent, PlanComponent, ProfileComponent,
)
from agentkernel_distributed.mas.environment.components import RelationComponent
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider
from agentkernel_distributed.toolkit.storages import RedisKVAdapter

from examples.story_of_the_stone.BasicController import BasicController
from examples.story_of_the_stone.plugins.action.communication.BasicCommunicationPlugin import BasicCommunicationPlugin
from examples.story_of_the_stone.plugins.action.move.BasicMovePlugin import BasicMovePlugin
from examples.story_of_the_stone.plugins.action.other.BasicOtherActionPlugin import BasicOtherActionPlugin
from examples.story_of_the_stone.plugins.agent.profile.BasicProfliePlugin import BasicProfilePlugin
from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.story_of_the_stone.plugins.agent.state.component import BasicStateComponent
from examples.story_of_the_stone.plugins.environment.relation.BasicRelationPlugin import BasicRelationPlugin
from examples.west_world_test.WestWorldPodManager import WestWorldPodManager
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import WestWorldInvokePlugin
from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import WestWorldPerceivePlugin
from examples.west_world_test.plugins.agent.plan.RandomWalkPlanPlugin import RandomWalkPlanPlugin

RESOURCES_MAPS = {
    "agent_components": {
        "profile": ProfileComponent, "perceive": PerceiveComponent,
        "plan": PlanComponent, "invoke": InvokeComponent, "state": BasicStateComponent,
    },
    "agent_plugins": {
        "BasicProfilePlugin": BasicProfilePlugin, "BasicStatePlugin": BasicStatePlugin,
        "WestWorldPerceivePlugin": WestWorldPerceivePlugin,
        "RandomWalkPlanPlugin": RandomWalkPlanPlugin,
        "WestWorldInvokePlugin": WestWorldInvokePlugin,
    },
    "action_components": {},     # 先按 sots 的 registry.py 对照：若它注册了 communication/move/otheractions 组件类，这里照搬
    "action_plugins": {
        "BasicCommunicationPlugin": BasicCommunicationPlugin,
        "BasicMovePlugin": BasicMovePlugin,
        "BasicOtherActionPlugin": BasicOtherActionPlugin,
    },
    "environment_components": {"relation": RelationComponent},
    "environment_plugins": {"BasicRelationPlugin": BasicRelationPlugin},
    "system_components": {"messager": Messager, "timer": Timer},
    "models": {"OpenAIProvider": OpenAIProvider},
    "adapters": {"RedisKVAdapter": RedisKVAdapter},
    "controller": BasicController,
    "pod_manager": WestWorldPodManager,
}
```

写之前对照 `examples/story_of_the_stone/registry.py` 把 import 路径与组件键名逐一核实（尤其 action_components 是否非空、ProfileComponent/InvokeComponent 真名），以 sots 为准修正上面代码。

- [ ] **Step 2: run_simulation.py**（精简主循环，不抄 sots 的前端信号/分支逻辑）：

```python
"""西部世界正式仿真入口（M2 骨架版）。

用法（仓库根目录，需 Redis 在线）：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed python -m examples.west_world_test.run_simulation
"""
from __future__ import annotations

import asyncio
import os

import ray

from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.registry_sim import RESOURCES_MAPS

logger = get_logger(__name__)
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))


async def main() -> None:
    ray.init(ignore_reinit_error=True)
    builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
    pod_manager, system = await builder.init()
    max_ticks = builder._config.simulation.max_ticks
    try:
        for tick in range(1, max_ticks + 1):
            logger.info("===== tick %s =====", tick)
            await pod_manager.step_agent.remote(tick)
    finally:
        ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

tick 推进调用要对照 `examples/west_world_test/run_test.py`（89 行，已验证可跑）的真实调用方式（`step_agent` 的签名、system timer 是否需要显式推进），以 run_test.py 为准修正。

- [ ] **Step 3: 冒烟运行（需本机 Redis）**

```bash
redis-cli ping && PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed python -m examples.west_world_test.run_simulation
```

Expected: 6 个 agent 装配成功，跑满 40 tick 无异常退出；日志中能看到多条 `移动 X -> Y` 且 X、Y 都是激活地点。常见故障排查顺序：① registry 键名与 yaml 插件名不一致 ② 数据注入形态（`_rows`）③ state 组件方法名。

- [ ] **Step 4: M2 验收检查**（对照 spec：≥10 tick 不崩 ✅、move 沿邻接图 ✅、known_map 增长——在日志或 Redis 里抽查一个 agent 的 known_map 长度随 tick 递增）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/registry_sim.py examples/west_world_test/run_simulation.py
git commit -m "feat(west-world): simulation skeleton entry (M2 milestone)"
```

---

# M3 接入 Recorder 与自由 plan

### Task 15: LocationRecorderPlugin（内核接入壳）+ environment_config 挂载

**Files:**
- Create: `examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py`（及 `__init__.py` 链）
- Modify: `examples/west_world_test/configs_sim/environment_config.yaml`
- Modify: `examples/west_world_test/registry_sim.py`
- Test: `examples/west_world_test/tests/test_location_recorder_plugin.py`

- [ ] **Step 1: 写失败测试**

```python
"""LocationRecorderPlugin 壳：动态组件类型 + 接口转发（FakeLLM）。"""
import asyncio

from examples.west_world_test.adapters.model_clients import FakeLLM
from examples.west_world_test.plugins.environment.scene.LocationRecorderPlugin import (
    LocationRecorderPlugin, make_scene_plugin_class,
)


def _make_plugin():
    cls = make_scene_plugin_class("sweetwater_saloon")
    assert cls.COMPONENT_TYPE == "scene_sweetwater_saloon"
    rows = [{
        "id": "sweetwater_saloon", "name": "甜水镇酒馆", "region": "sweetwater",
        "type": "interior", "active": True, "bbox": [0, 0, 0, 0], "adjacency": [],
        "description": "吧台与牌桌。", "objects": [], "default_occupants": [],
    }]
    return cls(location_id="sweetwater_saloon", locations=rows, llm_factory=lambda: FakeLLM([]))


def test_plugin_forwards_read_and_presence():
    plugin = _make_plugin()
    asyncio.run(plugin.init())
    desc = asyncio.run(plugin.agent_enter("dolores"))
    assert "吧台" in desc
    out = asyncio.run(plugin.read("dolores", ["present_agents"]))
    assert "dolores" in out["present_agents"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder_plugin.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""把 LocationRecorder 接入内核环境组件体系：每地点一个 scene_<id> 组件。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type

from agentkernel_distributed.mas.environment.base.plugin_base import GenericPlugin

from examples.west_world_test.recorder.location_recorder import LocationRecorder
from examples.west_world_test.worldmap.loader import Location


class LocationRecorderPlugin(GenericPlugin):
    COMPONENT_TYPE = "scene"          # 子类覆盖为 scene_<location_id>

    def __init__(self, location_id: str, locations: Any = None,
                 llm_factory: Optional[Callable[[], Any]] = None,
                 models_config_path: str = "", **_: Any) -> None:
        super().__init__()
        rows = list(locations.values()) if isinstance(locations, dict) else list(locations or [])
        self._location = Location(**next(r for r in rows if r["id"] == location_id))
        self._llm_factory = llm_factory
        self._models_config_path = models_config_path
        self.recorder: Optional[LocationRecorder] = None

    async def init(self) -> None:
        if self._llm_factory is None:
            from examples.west_world_test.adapters.model_clients import build_llm
            self._llm_factory = lambda: build_llm(self._models_config_path)
        self.recorder = LocationRecorder(location=self._location, llm=self._llm_factory())

    async def execute(self, current_tick: int) -> None:
        self.recorder.tick_update(current_tick)        # tick 末结算

    # ---- 转发接口（经 controller.run_environment 调用） ----
    async def read(self, agent_id: str, chunks: List[str]) -> Dict[str, Any]:
        return self.recorder.read(agent_id, chunks)

    async def submit_action(self, agent_id: str, action_text: str) -> Dict[str, Any]:
        return self.recorder.submit_action(agent_id, action_text)

    async def agent_enter(self, agent_id: str) -> str:
        return self.recorder.agent_enter(agent_id)

    async def agent_leave(self, agent_id: str) -> None:
        self.recorder.agent_leave(agent_id)


def make_scene_plugin_class(location_id: str) -> Type[LocationRecorderPlugin]:
    return type(f"Scene_{location_id}_Plugin", (LocationRecorderPlugin,),
                {"COMPONENT_TYPE": f"scene_{location_id}"})
```

前置确认：环境组件的 `execute(current_tick)` 在每 tick 被推进的调用链（查 `mas/environment/environment.py` 与 controller/pod 的 step 流程）；若环境组件不会被自动逐 tick 执行，则改由 run_simulation.py 在每 tick 末显式 `pod_manager.run_environment_method`（按 PodManager 实际 API）触发各 `scene_*` 的 `execute`，并在 Step 5 冒烟中验证确实每 tick 跑到。

- [ ] **Step 4: 挂载到配置与注册表**

`environment_config.yaml` 的 `components:` 下为 11 个激活地点逐一添加（节选两条，其余同构）：

```yaml
  scene_sweetwater_saloon:
    plugin:
      Scene_sweetwater_saloon_Plugin:
        adapters: {}
        location_id: sweetwater_saloon
        locations: "map_locations"
        models_config_path: "examples/west_world_test/configs/models_config.yaml"
  scene_abernathy_ranch:
    plugin:
      Scene_abernathy_ranch_Plugin:
        adapters: {}
        location_id: abernathy_ranch
        locations: "map_locations"
        models_config_path: "examples/west_world_test/configs/models_config.yaml"
```

`registry_sim.py` 追加（替换原 environment 两行）：

```python
from agentkernel_distributed.mas.environment.components import get_or_create_component_class
from examples.west_world_test.plugins.environment.scene.LocationRecorderPlugin import make_scene_plugin_class
from examples.west_world_test.worldmap.loader import load_world_map

_WORLD = load_world_map(os.path.join(os.path.dirname(__file__), "data/map/locations.yaml"))
_ACTIVE = sorted(_WORLD.active_ids())

RESOURCES_MAPS["environment_components"].update(
    {f"scene_{lid}": get_or_create_component_class(f"scene_{lid}") for lid in _ACTIVE})
RESOURCES_MAPS["environment_plugins"].update(
    {f"Scene_{lid}_Plugin": make_scene_plugin_class(lid) for lid in _ACTIVE})
```

（`import os` 补到文件头；environment_config 的 11 条可手写或由一段一次性脚本生成后粘贴。）

- [ ] **Step 5: 跑单测 + 冒烟**

Run: `python -m pytest examples/west_world_test/tests/test_location_recorder_plugin.py examples/west_world_test/tests -v`
Expected: 新测试 PASS 且全量回归 PASS。再跑一次 Task 14 Step 3 的冒烟命令，确认 11 个 scene 组件装配成功（此时尚无人调用它们，仅验证装配与 execute 空转）。

- [ ] **Step 6: Commit**

```bash
git add examples/west_world_test/plugins/environment examples/west_world_test/configs_sim/environment_config.yaml examples/west_world_test/registry_sim.py examples/west_world_test/tests/test_location_recorder_plugin.py
git commit -m "feat(west-world): per-location scene recorder components (M3 wiring)"
```

### Task 16: perceive/invoke 接通 Recorder

**Files:**
- Modify: `examples/west_world_test/plugins/agent/perceive/WestWorldPerceivePlugin.py`
- Modify: `examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py`

- [ ] **Step 1: perceive 的 `execute` 改为追加 Recorder 读取**（占位逻辑保留为 Recorder 不可用时的 fallback）：

```python
    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        state = await _read_state(agent)
        percept = build_percept(self._world, agent.agent_id, state)
        controller = agent.controller
        try:
            chunks = await controller.run_environment(
                f"scene_{state['location']}", "read",
                agent.agent_id, ["present_agents", "recent_events", "dynamic_objects"])
            percept["scene"] = chunks
        except Exception as exc:           # 地点无 recorder（未激活）或调用失败时降级为静态感知
            logger.warning("[%s] 读取 scene_%s 失败，使用静态感知: %s", agent.agent_id, state["location"], exc)
        agent._ww_percept = percept
```

M3 起 agent 自选 chunks：上面默认三块是 plan prompt 未指定时的缺省；Task 17 的 plan 输出里允许带 `"next_read": [...]`，perceive 在下一 tick 优先用 `agent._ww_next_read`（plan 写入）替代缺省列表。

- [ ] **Step 2: invoke 的 `execute` 扩展**：move 时联动 enter/leave；非 move 动作提交裁决：

```python
    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        decision = getattr(agent, "_ww_decision", {"action": "stay"})
        controller = agent.controller
        state = await _read_state(agent)
        here = state["location"]

        if decision.get("action") == "move":
            new_state, ok, reason = apply_move(self._world, state, decision["target"])
            if not ok:
                agent._ww_feedback = reason
                return
            await self._scene_call(controller, here, "agent_leave", agent.agent_id)
            first_sight = await self._scene_call(controller, new_state["location"], "agent_enter", agent.agent_id)
            await agent._components["state"].update_state(new_state)
            agent._ww_feedback = first_sight or ""
        elif decision.get("action") == "do":
            result = await self._scene_call(controller, here, "submit_action", agent.agent_id, decision.get("detail", ""))
            agent._ww_feedback = (result or {}).get("private_feedback", "") if isinstance(result, dict) else ""
        else:
            agent._ww_feedback = ""

    async def _scene_call(self, controller, location_id: str, method: str, *args):
        try:
            return await controller.run_environment(f"scene_{location_id}", method, *args)
        except Exception as exc:
            logger.warning("scene_%s.%s 调用失败: %s", location_id, method, exc)
            return None
```

`agent._ww_feedback`（私密反馈/初见描述）由 plan 在下一 tick 读取并拼进 prompt（Task 17），实现"私密反馈写回记忆"的最小闭环。

- [ ] **Step 3: 回归**

Run: `python -m pytest examples/west_world_test/tests -v`
Expected: 全部 PASS（test_sim_plugins.py 的纯函数测试不受影响）

- [ ] **Step 4: Commit**

```bash
git add examples/west_world_test/plugins/agent
git commit -m "feat(west-world): wire perceive/invoke to scene recorders"
```

### Task 17: WestWorldPlanPlugin（LLM 自由决策 + narrative loop 软引导）

**Files:**
- Create: `examples/west_world_test/plugins/agent/plan/WestWorldPlanPlugin.py`
- Modify: `examples/west_world_test/configs_sim/agents_config.yaml`（plan 插件换名）
- Test: `examples/west_world_test/tests/test_sim_plugins.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
def test_plan_prompt_contains_loop_percept_feedback_and_neighbors():
    from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import render_plan_prompt, parse_decision
    profile = {"姓名": "德洛丽丝", "性格": "温柔好奇", "narrative_loop": "清晨在农场醒来，上午去镇上采购。"}
    percept = {"location": "abernathy_ranch", "here_description": "农场。",
               "neighbors": ["sweetwater"], "known_map": ["abernathy_ranch"],
               "scene": {"present_agents": "peter_abernathy", "recent_events": []}}
    prompt = render_plan_prompt(profile, percept, feedback="你捡起了一支画笔。", tick=5)
    for needle in ("德洛丽丝", "清晨在农场醒来", "农场。", "sweetwater", "画笔"):
        assert needle in prompt
    decision = parse_decision('{"action": "move", "target": "sweetwater", "detail": "", "next_read": ["recent_events"]}')
    assert decision["action"] == "move" and decision["target"] == "sweetwater"
    assert parse_decision("乱七八糟")["action"] == "stay"     # 解析失败降级为 stay
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest examples/west_world_test/tests/test_sim_plugins.py -v`
Expected: 新增 1 FAIL

- [ ] **Step 3: 实现**

```python
"""LLM 自由决策 plan：profile 中的 narrative_loop 作为软引导（行为倾向，非脚本）。"""
from __future__ import annotations

import json
from typing import Any, Dict

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

PLAN_PROMPT = """你是西部世界中的角色「{name}」。
性格：{personality}
你的日常习惯（这是你的本能倾向，但你可以因为眼前发生的事偏离它）：{narrative_loop}

## 当前情况（tick {tick}）
你在：{location}。{here_description}
场景信息：{scene}
上一个动作的结果：{feedback}
可以前往的相邻地点：{neighbors}

## 决定你这一刻要做什么
- 继续待在这里做某件事：action 用 "do"，detail 写具体动作（一句话，第一人称行为描述）
- 移动到相邻地点：action 用 "move"，target 填地点 id
- 什么都不做：action 用 "stay"
- next_read 填你下一刻想了解的场景信息块，可选项: ["present_agents", "recent_events", "dynamic_objects", "static_facilities"]

只输出 JSON：{{"action": "do|move|stay", "target": "", "detail": "", "next_read": []}}
"""


def render_plan_prompt(profile: Dict[str, Any], percept: Dict[str, Any], feedback: str, tick: int) -> str:
    return PLAN_PROMPT.format(
        name=profile.get("姓名", ""), personality=profile.get("性格", ""),
        narrative_loop=profile.get("narrative_loop", ""), tick=tick,
        location=percept.get("location", ""), here_description=percept.get("here_description", ""),
        scene=json.dumps(percept.get("scene", {}), ensure_ascii=False),
        feedback=feedback or "（无）", neighbors=", ".join(percept.get("neighbors", [])),
    )


def parse_decision(raw: str) -> Dict[str, Any]:
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        decision = json.loads(text)
        if decision.get("action") in ("do", "move", "stay"):
            return decision
    except (json.JSONDecodeError, IndexError):
        pass
    return {"action": "stay", "target": "", "detail": "", "next_read": []}


class WestWorldPlanPlugin(PlanPlugin):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self._model = None

    async def init(self) -> None:
        pass

    async def post_init(self, model_router: Any = None, **kwargs) -> None:
        self._model = model_router      # 以 plugin_base 实际钩子签名为准

    async def execute(self, current_tick: int) -> None:
        agent = self._component.agent
        profile = await _read_profile(agent)
        percept = getattr(agent, "_ww_percept", {})
        feedback = getattr(agent, "_ww_feedback", "")
        prompt = render_plan_prompt(profile, percept, feedback, current_tick)
        raw = await _chat(self._model, prompt)
        decision = parse_decision(raw)
        agent._ww_decision = decision
        agent._ww_next_read = decision.get("next_read") or []
        logger.info("[%s] tick %s 决策: %s", agent.agent_id, current_tick, json.dumps(decision, ensure_ascii=False))
```

`_read_profile` 与 `_chat`（经 model_router 调 text 模型）的写法必须对照 sots `BasicPlanPlugin.py:112-177` 的真实用法（model_router 的调用方法名、profile 组件的读取方法）实现——这两处是本任务最大的接口风险点，先读再写。

- [ ] **Step 4: 跑测试 + 切换配置**

Run: `python -m pytest examples/west_world_test/tests/test_sim_plugins.py -v` → PASS。
`configs_sim/agents_config.yaml` 中 plan 插件 `RandomWalkPlanPlugin` 改为 `WestWorldPlanPlugin`；`registry_sim.py` 的 agent_plugins 增加 `"WestWorldPlanPlugin": WestWorldPlanPlugin`（保留 RandomWalkPlanPlugin 注册，便于回退调试）。

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/plugins/agent/plan examples/west_world_test/configs_sim/agents_config.yaml examples/west_world_test/registry_sim.py examples/west_world_test/tests/test_sim_plugins.py
git commit -m "feat(west-world): LLM plan with narrative-loop soft guidance"
```

### Task 18: M3 全链路联调（验收）

**Files:**
- Create: `examples/west_world_test/tests/test_sim_skeleton.py`（集成冒烟，无 Redis/模型时 skip）

- [ ] **Step 1: 写集成测试**

```python
"""全链路冒烟：需要 Redis 与 models_config.yaml，缺则跳过。"""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MODELS = os.path.join(ROOT, "examples/west_world_test/configs/models_config.yaml")


def _redis_alive() -> bool:
    return shutil.which("redis-cli") is not None and \
        subprocess.run(["redis-cli", "ping"], capture_output=True).returncode == 0


@pytest.mark.skipif(not (_redis_alive() and os.path.exists(MODELS)), reason="需要 Redis 与 models_config")
def test_full_pipeline_smoke():
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT}:{os.path.join(ROOT, 'packages/agentkernel-distributed')}"
    env["WW_MAX_TICKS"] = "5"      # run_simulation.py 支持该环境变量覆盖 max_ticks（本 task 顺手加上）
    result = subprocess.run(
        ["python", "-m", "examples.west_world_test.run_simulation"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    assert result.returncode == 0, result.stderr[-3000:]
```

并在 `run_simulation.py` 的 `main()` 中加入：`max_ticks = int(os.environ.get("WW_MAX_TICKS", builder._config.simulation.max_ticks))`。

- [ ] **Step 2: 跑 20 tick 人工验收**（对照 spec M3 标准）：

```bash
WW_MAX_TICKS=20 PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed python -m examples.west_world_test.run_simulation
```

逐项核对日志：① agent 决策 JSON 中出现非空 `next_read`（agent 在选择读什么）② 出现 `do` 动作且日志/状态中有 private_feedback 回流 ③ 制造一次公开事件（如有 agent 在酒馆 `do`），下一 tick 同地点他人的 percept["scene"]["recent_events"] 含该事件 ④ hidden 物件的 secret 从未出现在任何 `read` 返回里（grep 日志确认）。

- [ ] **Step 3: Commit**

```bash
git add examples/west_world_test/tests/test_sim_skeleton.py examples/west_world_test/run_simulation.py
git commit -m "feat(west-world): end-to-end pipeline smoke test (M3 milestone)"
```

### Task 19: 收尾——文档更新

**Files:**
- Modify: `CLAUDE.md`（§7）
- Modify: `examples/west_world_test/README.md`

- [ ] **Step 1:** CLAUDE.md §7 增补正式仿真的入口（`run_simulation.py` + `configs_sim/` + `registry_sim.py`）、worldmap/recorder 模块指针、与 MVE 并存关系；README 增加正式仿真运行说明（PYTHONPATH、Redis、WW_MAX_TICKS）。
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md examples/west_world_test/README.md
git commit -m "docs(west-world): document simulation entry and recorder modules"
```

---

## 风险与既定取舍（来自 spec，执行时不要重新发明）

- 裁决失败降级 = **允许/无反馈/不广播**（用户已确认）；tick_update 失败 = 保留旧状态。
- 同 tick 物品冲突按 submit 顺序先到先得，不做并发协商。
- tick_update 的 prompt 必须把裁决结果当既定事实（防"即时裁决 vs 合并更新"不一致）。
- spec §3.2 说 move 走动作组件；实现上 move 校验收敛在 `worldmap.can_move` + invoke 插件直接落实，actions 组件保留 sots 空壳仅为装配兼容——这是有意的简化，不算偏差。
- reflect/记忆压缩本期不做（component_order 不含 reflect）；觉醒/监管者/前端均为后续计划。
```
