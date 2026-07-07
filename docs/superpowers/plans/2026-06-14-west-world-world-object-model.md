# West World 世界对象模型（WorldObjectRegistry）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把正式仿真 Structured Recorder 的对象所有权从 location-anchored 重构为世界级 `WorldObjectRegistry`，解锁对象的自由创造/销毁、跨地点转移、held_by 跨 agent 传递与 ambient 环境态。

**Architecture:** 新增进程内单例 `WorldObjectRegistry` 作为所有地点所有对象的唯一真值源；`StructuredLocationRecorder` 退化为「查询本地点对象的视图」，所有写操作经 registry 的确定性方法并记 append-only ledger；持有物随持有者移动（`invoke.apply_move` 调 `relocate_holdings`）；legacy 文本 Recorder 与 MVE `core/` 不动。

**Tech Stack:** Python 3.11，pytest，agentkernel_distributed（Ray pod 环境组件），无新增第三方依赖。

设计 spec：`docs/superpowers/specs/2026-06-14-west-world-world-object-model-design.md`

---

## 关键约束（实现前必读）

- **进程边界**：`run_simulation.py` 是 Ray **driver**；registry 单例活在 **pod actor** 进程里。driver 不能直接 `get_object_registry()`，必须经 `pod_manager.run_environment.remote("scene_<id>", <method>)` 走环境方法（与 `_collect_scene_snapshots` 同款）。
- **现有测试会被改**：`tests/test_structured_location_recorder.py` 大量断言 `recorder.object_facts[...]`。重构后 `object_facts` 不再是 recorder 的属性，这些断言改为查 registry。Task 3/4/5/6 会逐步改写它们。
- **TDD + 频繁提交**：每个 Task 走「写失败测试 → 跑挂 → 最小实现 → 跑过 → commit」。
- **运行测试统一命令**：
  ```bash
  PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests -q
  ```
  （以下步骤为简洁省略前缀，实际执行须带 `PYTHONPATH`。）

## File Structure

- **Create** `examples/west_world_test/recorder/world_object_registry.py` — `ObjectRecord` 数据结构、`WorldObjectRegistry` 类、`get_object_registry()` 单例、`reset_object_registry()`（测试用）。唯一真值源。
- **Create** `examples/west_world_test/tests/test_world_object_registry.py` — registry 纯 Python 单测。
- **Modify** `examples/west_world_test/recorder/structured_location_recorder.py` — 退化为 registry 视图；新 schema（new_objects/destroy/ambient）；校验；移除 `object_facts` 自有存储与 `_release_holdings` 丢弃逻辑。
- **Modify** `examples/west_world_test/recorder/prompts.py` 或就地 `_PROPOSAL_PROMPT` — prompt 增加 new_objects/destroy/ambient/在场 agent。
- **Modify** `examples/west_world_test/tests/test_structured_location_recorder.py` — 断言改查 registry；新增 new_objects/destroy/ambient/held_by 传递/跨地点测试。
- **Modify** `examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py` — `apply_move` 成功后调 `relocate_holdings`。
- **Modify** `examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py` — 增加 `world_snapshot` 环境方法。
- **Modify** `examples/west_world_test/run_simulation.py` + `examples/west_world_test/simulation_logging.py` — 每 tick 落盘世界级对象快照。
- **Modify** `examples/west_world_test/DEVELOPMENT_NOTES.md` — 勾掉已解决缺口。

---

## Task 1: WorldObjectRegistry 核心（create / patch / destroy / objects_at）

**Files:**
- Create: `examples/west_world_test/recorder/world_object_registry.py`
- Test: `examples/west_world_test/tests/test_world_object_registry.py`

- [ ] **Step 1: 写失败测试**

```python
# examples/west_world_test/tests/test_world_object_registry.py
from examples.west_world_test.recorder.world_object_registry import WorldObjectRegistry

_META = {"object_id", "name", "hidden", "destroyed", "provenance"}


def test_create_assigns_global_monotonic_id_and_provenance():
    reg = WorldObjectRegistry()
    oid = reg.create(name="威士忌", location_id="saloon", by="maeve",
                     tick=2, action="倒一杯酒", fields={"state": "满杯"})
    assert oid == "obj_0"
    row = reg.get(oid)
    assert row["name"] == "威士忌"
    assert row["location_id"] == "saloon"
    assert row["held_by"] == ""
    assert row["destroyed"] is False
    assert row["provenance"] == {"created_by": "maeve", "created_tick": 2, "created_action": "倒一杯酒"}
    second = reg.create(name="第二杯", location_id="saloon", by="maeve", tick=3, action="再倒", fields={})
    assert second == "obj_1"


def test_apply_patch_updates_free_fields_and_protects_meta():
    reg = WorldObjectRegistry()
    oid = reg.create(name="酒杯", location_id="saloon", by="t", tick=1, action="a", fields={"state": "完整"})
    reg.apply_patch(oid, {"state": "破碎", "quantity": "一片"})
    row = reg.get(oid)
    assert row["state"] == "破碎"
    assert row["quantity"] == "一片"


def test_destroy_is_soft_delete_and_recorded():
    reg = WorldObjectRegistry()
    oid = reg.create(name="酒杯", location_id="saloon", by="t", tick=1, action="a", fields={})
    reg.destroy(oid, by="hector", tick=4)
    assert reg.get(oid)["destroyed"] is True
    assert reg.objects_at("saloon") == []          # destroyed 不在视图里
    assert any(e["op"] == "destroy" and e["object_id"] == oid for e in reg.ledger)


def test_objects_at_filters_by_location_and_hidden():
    reg = WorldObjectRegistry()
    reg.create(name="可见杯", location_id="saloon", by="t", tick=1, action="a", fields={})
    reg.create(name="密照", location_id="saloon", by="t", tick=1, action="a", fields={}, hidden=True)
    reg.create(name="别处物", location_id="ranch", by="t", tick=1, action="a", fields={})
    visible = reg.objects_at("saloon")
    assert [r["name"] for r in visible] == ["可见杯"]
    with_hidden = reg.objects_at("saloon", include_hidden=True)
    assert {r["name"] for r in with_hidden} == {"可见杯", "密照"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_world_object_registry.py -q`
Expected: FAIL（`ModuleNotFoundError: world_object_registry`）

- [ ] **Step 3: 最小实现**

```python
# examples/west_world_test/recorder/world_object_registry.py
"""World-level object registry: single source of truth for all objects across locations."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

# 不可被 patch 覆盖的保留字段
META_FIELDS = {"object_id", "name", "hidden", "destroyed", "provenance", "location_id"}


class WorldObjectRegistry:
    """所有地点所有对象的唯一真值源 + append-only ledger。"""

    def __init__(self) -> None:
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._next_id = 0
        self.ledger: List[Dict[str, Any]] = []
        self._seeded = False

    # ---- 写 ----
    def create(self, name: str, location_id: str, by: str, tick: Optional[int],
               action: str, fields: Dict[str, Any], hidden: bool = False,
               held_by: str = "") -> str:
        oid = f"obj_{self._next_id}"
        self._next_id += 1
        row: Dict[str, Any] = {
            "object_id": oid,
            "name": name,
            "location_id": location_id,
            "held_by": held_by,
            "state": "状态正常",
            "hidden": bool(hidden),
            "destroyed": False,
            "provenance": {"created_by": by, "created_tick": tick, "created_action": action},
        }
        for key, value in fields.items():
            if key not in META_FIELDS and key not in ("held_by",):
                row[key] = value
        self._objects[oid] = row
        self._log("create", oid, None, copy.deepcopy(row), by, tick)
        return oid

    def apply_patch(self, object_id: str, updates: Dict[str, Any]) -> None:
        row = self._objects[object_id]
        before = copy.deepcopy(row)
        for key, value in updates.items():
            if key in META_FIELDS:
                continue
            row[key] = value
        self._log("patch", object_id, before, copy.deepcopy(row), None, None)

    def destroy(self, object_id: str, by: str, tick: Optional[int]) -> None:
        row = self._objects[object_id]
        before = copy.deepcopy(row)
        row["destroyed"] = True
        self._log("destroy", object_id, before, copy.deepcopy(row), by, tick)

    # ---- 读 ----
    def get(self, object_id: str) -> Dict[str, Any]:
        return self._objects[object_id]

    def has(self, object_id: str) -> bool:
        return object_id in self._objects

    def objects_at(self, location_id: str, include_hidden: bool = False) -> List[Dict[str, Any]]:
        rows = [
            r for r in self._objects.values()
            if r["location_id"] == location_id and not r["destroyed"]
            and (include_hidden or not r["hidden"])
        ]
        return [copy.deepcopy(r) for r in rows]

    def _log(self, op: str, object_id: str, before: Optional[Dict[str, Any]],
             after: Optional[Dict[str, Any]], by: Optional[str], tick: Optional[int]) -> None:
        self.ledger.append({
            "op": op, "object_id": object_id,
            "before": before, "after": after, "by": by, "tick": tick,
        })
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_world_object_registry.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/world_object_registry.py examples/west_world_test/tests/test_world_object_registry.py
git commit -m "feat(west-world): WorldObjectRegistry core with create/patch/destroy/objects_at"
```

---

## Task 2: relocate_holdings + seed_from_world + 单例

**Files:**
- Modify: `examples/west_world_test/recorder/world_object_registry.py`
- Test: `examples/west_world_test/tests/test_world_object_registry.py`

- [ ] **Step 1: 写失败测试（追加到现有测试文件）**

```python
from examples.west_world_test.recorder.world_object_registry import (
    WorldObjectRegistry, get_object_registry, reset_object_registry,
)
from examples.west_world_test.worldmap.loader import Location


def test_relocate_holdings_moves_held_objects_with_agent():
    reg = WorldObjectRegistry()
    held = reg.create(name="左轮", location_id="saloon", by="t", tick=1, action="a",
                      fields={}, held_by="hector")
    ground = reg.create(name="酒桶", location_id="saloon", by="t", tick=1, action="a", fields={})
    reg.relocate_holdings("hector", "ranch")
    assert reg.get(held)["location_id"] == "ranch"      # 持有物跟随
    assert reg.get(ground)["location_id"] == "saloon"   # 地上物不动
    assert any(e["op"] == "relocate" for e in reg.ledger)


def test_seed_from_world_is_idempotent():
    world = {
        "saloon": Location(id="saloon", name="酒馆", region="r", type="interior",
                           active=True, bbox=[0, 0, 0, 0], adjacency=[],
                           objects=[{"name": "酒杯", "note": "完整"},
                                    {"name": "密照", "hidden": True, "secret": "现代照片"}]),
    }

    class _World:
        def active_ids(self):
            return {"saloon"}

        def get(self, lid):
            return world[lid]

    reg = WorldObjectRegistry()
    reg.seed_from_world(_World())
    reg.seed_from_world(_World())  # 第二次应无副作用
    assert len(reg.objects_at("saloon", include_hidden=True)) == 2
    secret = next(r for r in reg.objects_at("saloon", include_hidden=True) if r["hidden"])
    assert secret["hidden"] is True


def test_singleton_returns_same_instance_until_reset():
    reset_object_registry()
    a = get_object_registry()
    b = get_object_registry()
    assert a is b
    reset_object_registry()
    assert get_object_registry() is not a
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_world_object_registry.py -q`
Expected: FAIL（`relocate_holdings` / `seed_from_world` / `get_object_registry` 未定义）

- [ ] **Step 3: 实现（追加到 `world_object_registry.py`）**

在 `WorldObjectRegistry` 内追加方法：

```python
    def relocate_holdings(self, agent_id: str, to_location: str) -> None:
        for row in self._objects.values():
            if row["held_by"] == agent_id and not row["destroyed"]:
                before = copy.deepcopy(row)
                row["location_id"] = to_location
                self._log("relocate", row["object_id"], before, copy.deepcopy(row), agent_id, None)

    def seed_from_world(self, world_map: Any) -> None:
        if self._seeded:
            return
        for lid in sorted(world_map.active_ids()):
            location = world_map.get(lid)
            for item in location.objects:
                fields = {"state": item.get("note", "状态正常")}
                if item.get("secret"):
                    fields["secret"] = item["secret"]
                self.create(
                    name=item["name"], location_id=lid, by="__seed__", tick=None,
                    action="__seed__", fields=fields, hidden=bool(item.get("hidden")),
                )
        self._seeded = True

    def snapshot(self) -> Dict[str, Any]:
        return {
            "objects": [copy.deepcopy(r) for r in self._objects.values()],
            "ledger": copy.deepcopy(self.ledger),
        }
```

在模块底部追加单例：

```python
_REGISTRY: Optional[WorldObjectRegistry] = None


def get_object_registry() -> WorldObjectRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = WorldObjectRegistry()
    return _REGISTRY


def reset_object_registry() -> None:
    """测试隔离用：清空进程内单例。"""
    global _REGISTRY
    _REGISTRY = None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_world_object_registry.py -q`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/world_object_registry.py examples/west_world_test/tests/test_world_object_registry.py
git commit -m "feat(west-world): registry relocate_holdings, seed_from_world, singleton"
```

---

## Task 3: StructuredLocationRecorder 退化为 registry 视图

**目标**：构造时把本地点对象 seed 进 registry（经单例），`object_facts` 改为「从 registry 读出的本地点视图属性」，`_render_dynamic_objects` 从 registry 渲染。先保持 submit_action 旧 patch 行为可用（新 schema 在 Task 4）。

**Files:**
- Modify: `examples/west_world_test/recorder/structured_location_recorder.py`
- Modify: `examples/west_world_test/tests/test_structured_location_recorder.py`

- [ ] **Step 1: 改写现有测试为查 registry（先让它们失败）**

把 `tests/test_structured_location_recorder.py` 顶部改为每个测试前重置单例，并把 `recorder.object_facts["obj_0"]` 风格断言改成查 registry。新增 fixture：

```python
import json
import pytest

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.recorder.structured_location_recorder import StructuredLocationRecorder
from examples.west_world_test.recorder.world_object_registry import get_object_registry, reset_object_registry
from examples.west_world_test.worldmap.loader import Location

LOCATION = Location(
    id="saloon", name="酒馆", region="sweetwater", type="interior",
    active=True, bbox=[0, 0, 0, 0], adjacency=[],
    objects=[
        {"name": "酒杯", "note": "完整"},
        {"name": "旧照片", "hidden": True, "secret": "现代照片"},
    ],
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_object_registry()
    yield
    reset_object_registry()


def _reg_state(location_id, name):
    reg = get_object_registry()
    row = next(r for r in reg.objects_at(location_id, include_hidden=True) if r["name"] == name)
    return row
```

然后把现有断言逐条迁移，例如：

```python
def test_patch_updates_only_named_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal()]))
    recorder.submit_action("maeve", "打碎酒杯", tick=3)
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"
    assert recorder.fact_ledger[0]["tick"] == 3
```

（其余 `object_facts` 断言同法改为 `_reg_state(...)`；hidden 相关断言用 `include_hidden=True` 取。）

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -q`
Expected: FAIL（recorder 仍用自有 `object_facts`，registry 为空 → `StopIteration`）

- [ ] **Step 3: 改 recorder 构造与读路径**

`structured_location_recorder.py` 的 `__init__` 改为经 registry seed 本地点对象（不再自建 `object_facts` dict）：

```python
    def __init__(self, location: Location, llm: Any) -> None:
        super().__init__(location, llm)
        self.registry = get_object_registry()
        self._seed_location()
        self.fact_ledger: List[Dict[str, Any]] = []
        self._render_dynamic_objects()

    def _seed_location(self) -> None:
        # 若单例已被其它 scene seed 过本地点则跳过（幂等）
        if self.registry.objects_at(self.location.id, include_hidden=True):
            return
        for item in self.location.objects:
            fields = {"state": item.get("note", "状态正常")}
            if item.get("secret"):
                fields["secret"] = item["secret"]
            self.registry.create(
                name=item["name"], location_id=self.location.id, by="__seed__",
                tick=None, action="__seed__", fields=fields, hidden=bool(item.get("hidden")),
            )
```

`_render_dynamic_objects` 改从 registry 读：

```python
    def _render_dynamic_objects(self) -> None:
        parts = []
        skip = {"object_id", "name", "hidden", "destroyed", "provenance", "location_id", "state", "held_by", "secret"}
        for row in self.registry.objects_at(self.location.id):
            text = f"{row['name']}：{row.get('state', '')}"
            extras = [(k, v) for k, v in row.items() if k not in skip and v]
            if extras:
                text += "（" + "，".join(f"{k}：{v}" for k, v in extras) + "）"
            if row.get("held_by"):
                text += f"，由 {row['held_by']} 持有"
            parts.append(text)
        self.chunks["dynamic_objects"] = "；".join(parts) or "暂无可变物品。"
```

`submit_action` 内的对象读取（构 prompt 的 `visible_objects`/`visible_facts`）改为 `self.registry.objects_at(self.location.id)`；patch 应用改为 `self.registry.apply_patch(...)`。保留 `_validate_patches` 但其 `object_id` 存在性/hidden 判断改查 registry（`self.registry.has` + `objects_at(include_hidden=True)`）。移除 `self.object_facts` 与 `_release_holdings`/`agent_leave` override（跨地点跟随在 Task 6 接管；本 Task 先让 `agent_leave` 回落到父类，不再丢弃持有物）。`snapshot(include_hidden=True)` 里的 `object_facts` 改为 `self.registry.objects_at(self.location.id, include_hidden=True)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -q`
Expected: PASS（原有用例除 `test_held_object_released_when_holder_leaves` 外全过；该用例语义在 Task 6 反转，本 Task 暂时跳过或标 `xfail`，并在 Task 6 删除）

> 实现注意：把 `test_held_object_released_when_holder_leaves` 暂时改名为 `test_held_object_followed_when_holder_moves` 的占位 `@pytest.mark.skip(reason="reworked in Task 6")`，避免本 Task 卡住。

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/structured_location_recorder.py examples/west_world_test/tests/test_structured_location_recorder.py
git commit -m "refactor(west-world): StructuredLocationRecorder reads/writes via WorldObjectRegistry"
```

---

## Task 4: 新 schema —— new_objects / destroy / ambient

**Files:**
- Modify: `examples/west_world_test/recorder/structured_location_recorder.py`（`_PROPOSAL_PROMPT` + `submit_action` + 校验）
- Modify: `examples/west_world_test/tests/test_structured_location_recorder.py`

- [ ] **Step 1: 写失败测试**

```python
def _proposal_full(**overrides):
    value = {
        "permission": True, "reason": "", "private_feedback": "做了点事。",
        "broadcast_level": "location", "event_summary": "",
        "patches": [], "new_objects": [], "destroy": [], "ambient": "",
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


def test_new_objects_are_created_with_provenance():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(new_objects=[{"name": "地上的血", "state": "暗红一滩", "held_by": ""}])]),
    )
    recorder.submit_action("hector", "开枪", tick=5)
    blood = _reg_state("saloon", "地上的血")
    assert blood["state"] == "暗红一滩"
    assert blood["provenance"]["created_by"] == "hector"
    assert blood["provenance"]["created_tick"] == 5


def test_destroy_soft_deletes_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal_full(destroy=["obj_0"])]))
    recorder.submit_action("maeve", "把酒杯扔进火里", tick=6)
    reg = get_object_registry()
    assert reg.get("obj_0")["destroyed"] is True


def test_ambient_is_rewritten_and_readable():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal_full(ambient="灯光昏暗，弥漫硝烟味。")]))
    recorder.submit_action("maeve", "环顾四周", tick=7)
    assert recorder.chunks["ambient"] == "灯光昏暗，弥漫硝烟味。"
    assert recorder.read("maeve", ["ambient"])["ambient"] == "灯光昏暗，弥漫硝烟味。"


def test_new_object_cannot_be_hidden():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(new_objects=[{"name": "暗格", "hidden": True}])]),
    )
    recorder.submit_action("maeve", "藏东西", tick=8)
    created = _reg_state("saloon", "暗格")
    assert created["hidden"] is False


def test_destroy_unknown_id_is_dropped_without_failing_action():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(destroy=["obj_999"], event_summary="无效销毁")]),
    )
    judgement = recorder.submit_action("maeve", "试图销毁不存在的东西", tick=9)
    assert judgement["permission"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -q`
Expected: FAIL（new_objects/destroy/ambient 未处理；ambient 不在 READABLE_CHUNKS）

- [ ] **Step 3: 实现**

`recorder/location_recorder.py`：把 `ambient` 纳入可读块，并给基类 chunks 初始化 ambient：
```python
READABLE_CHUNKS = {"static_facilities", "dynamic_objects", "present_agents", "recent_events", "ambient"}
```
在 `LocationRecorder.__init__` 的 `self.chunks` 里加 `"ambient": "（无特别氛围）",`。

`structured_location_recorder.py` 的 `_PROPOSAL_PROMPT` 增加字段说明（在 JSON 模板里加 `new_objects`/`destroy`/`ambient`，并在规则里写明：new_objects 可任意 name/字段、不得 hidden；destroy 列可见对象 id；ambient 为整体氛围自由文本；在场角色见下），并在 format 里传入在场 agent：

```python
# 规则补充（追加到 prompt 文本）：
# - new_objects：当动作产生新的可见物（倒出的酒、地上的血、掉落的弹壳）时声明，每项含 name 与初始字段；不得标 hidden。
# - destroy：当可见物被彻底消灭（烧毁、击碎丢弃）时列其 object_id。
# - ambient：当整体环境氛围（光线/气味/声音/气氛）变化时给一句中文自由文本；无变化则空串。
# - held_by 可设为行动者或本地点在场的任意角色（present_agents），或空（放下）。
# JSON 模板新增：
#   "new_objects": [{"name": "地上的血", "state": "暗红一滩", "held_by": ""}],
#   "destroy": ["obj_5"],
#   "ambient": ""
```

`submit_action` 在应用 patches 前后扩展处理顺序 new_objects → patches → destroy → ambient：

```python
        if not proposal.get("permission", False):
            patches, new_objects, destroy_ids, ambient = [], [], [], None
        else:
            new_objects = self._validate_new_objects(proposal.get("new_objects", []))
            destroy_ids = self._validate_destroy(proposal.get("destroy", []))
            ambient = proposal.get("ambient") or None
        before = self.registry.snapshot()
        for spec in new_objects:
            self.registry.create(
                name=spec["name"], location_id=self.location.id, by=agent_id,
                tick=tick, action=action_text, fields=spec["fields"], hidden=False,
                held_by=spec["held_by"],
            )
        self._apply_patches(patches)
        for oid in destroy_ids:
            self.registry.destroy(oid, by=agent_id, tick=tick)
        if ambient:
            self.chunks["ambient"] = str(ambient)[:200]
```

新增两个校验器（宽容策略：单条非法丢弃、不让整动作失败）：

```python
    def _validate_new_objects(self, raw: Any) -> List[Dict[str, Any]]:
        result = []
        if not isinstance(raw, list):
            return result
        for spec in raw:
            if not isinstance(spec, dict) or not spec.get("name"):
                continue
            fields = {}
            held_by = ""
            for key, value in spec.items():
                if key in ("name", "hidden", "object_id", "destroyed", "provenance", "location_id"):
                    continue
                if key == "held_by":
                    held_by = value if value in ("",) else value  # 在场校验在 Task 5 收紧
                    continue
                if isinstance(value, str) and len(value) <= 100:
                    fields[key] = value
            result.append({"name": str(spec["name"])[:100], "fields": fields, "held_by": held_by})
        return result

    def _validate_destroy(self, raw: Any) -> List[str]:
        result = []
        if not isinstance(raw, list):
            return result
        for oid in raw:
            if (self.registry.has(oid)
                    and self.registry.get(oid)["location_id"] == self.location.id
                    and not self.registry.get(oid)["destroyed"]
                    and not self.registry.get(oid)["hidden"]):
                result.append(oid)
        return result
```

`fact_ledger.append` 的 `before/after` 改用 `self.registry.snapshot()` 前后值（或保留动作级摘要）。结尾 `self._render_dynamic_objects()`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/structured_location_recorder.py examples/west_world_test/recorder/location_recorder.py examples/west_world_test/tests/test_structured_location_recorder.py
git commit -m "feat(west-world): free object creation/destruction + ambient in structured recorder"
```

---

## Task 5: held_by 跨 agent 传递（在场校验）

**Files:**
- Modify: `examples/west_world_test/recorder/structured_location_recorder.py`
- Modify: `examples/west_world_test/tests/test_structured_location_recorder.py`

- [ ] **Step 1: 写失败测试**

```python
def test_held_by_can_pass_to_present_agent():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(patches=[{"object_id": "obj_0", "held_by": "teddy"}])]),
    )
    recorder.set_present_agents(["maeve", "teddy"])
    recorder.submit_action("maeve", "把酒杯递给 teddy", tick=3)
    assert _reg_state("saloon", "酒杯")["held_by"] == "teddy"


def test_held_by_to_absent_agent_is_rejected():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(patches=[{"object_id": "obj_0", "held_by": "ghost"}])]),
    )
    recorder.set_present_agents(["maeve"])
    recorder.submit_action("maeve", "把酒杯递给不在场的人", tick=3)
    assert _reg_state("saloon", "酒杯")["held_by"] == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -k held_by -q`
Expected: FAIL（`test_held_by_can_pass_to_present_agent` 因旧校验只允许行动者/空而失败）

- [ ] **Step 3: 实现**

在 `_validate_patches` 与 `_validate_new_objects` 里把 held_by 校验改为「∈ 空 ∪ 行动者 ∪ 本地点在场 agent」：

```python
    def _allowed_holders(self, agent_id: str) -> set:
        return {"", agent_id} | self._present_set()
```

`_validate_patches` 中：
```python
                if key == "held_by" and value not in self._allowed_holders(agent_id):
                    raise ValueError("只能把对象交给在场角色或放下")
```
（注：非法 held_by 触发 `ValueError` → 该动作整体降级为不允许；若希望「丢弃该字段但保留其它 patch」，改为跳过该 key。按 spec §6 单条非法宽容：此处改为 `continue` 跳过 held_by 而非 raise，保持其它字段生效。最终采用跳过策略以匹配 `test_held_by_to_absent_agent_is_rejected` 期望「held_by 保持 ""」。）

`_validate_new_objects` 中 held_by 同样校验：不在 `_allowed_holders` 则置 ""。把 Task 4 里 `held_by = value if value in ("",) else value` 占位改为：
```python
                if key == "held_by":
                    held_by = value if value in self._allowed_holders(agent_id) else ""
                    continue
```
（`_validate_new_objects` 需要接收 `agent_id` 参数：把签名改为 `_validate_new_objects(self, raw, agent_id)` 并在 `submit_action` 调用处传入。）

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -k held_by -q`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/recorder/structured_location_recorder.py examples/west_world_test/tests/test_structured_location_recorder.py
git commit -m "feat(west-world): held_by can transfer to any present agent"
```

---

## Task 6: 跨地点跟随（invoke.apply_move → relocate_holdings）

**Files:**
- Modify: `examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py`
- Modify: `examples/west_world_test/recorder/structured_location_recorder.py`（删除 Task 3 skip 占位、确保 `agent_leave` 不丢弃持有物）
- Test: `examples/west_world_test/tests/test_structured_location_recorder.py` + `examples/west_world_test/tests/test_sim_plugins.py`

- [ ] **Step 1: 写失败测试**

registry 层跟随（recorder 测试文件，验证 leave 不再丢弃）：
```python
def test_held_object_not_dropped_on_leave_and_follows_via_registry():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(patches=[{"object_id": "obj_0", "held_by": "maeve"}])]),
    )
    recorder.set_present_agents(["maeve"])
    recorder.submit_action("maeve", "拿起酒杯", tick=1)
    recorder.agent_leave("maeve")
    # leave 不再清空 held_by（持有物随人走，由 relocate_holdings 迁移地点）
    reg = get_object_registry()
    assert reg.get("obj_0")["held_by"] == "maeve"
    reg.relocate_holdings("maeve", "ranch")
    assert reg.get("obj_0")["location_id"] == "ranch"
    assert recorder.read("maeve", ["dynamic_objects"])["dynamic_objects"] == "暂无可变物品。"
```

删除（或已在 Task 3 skip）`test_held_object_released_when_holder_leaves`。

invoke 接线测试（`test_sim_plugins.py` 风格，验证 move 调 relocate_holdings）：用一个 fake controller 记录 `run_environment` 调用，断言 move 成功后 registry 的持有物 location 被迁移。若 `apply_move` 是纯函数无法触达 registry，则在 `WestWorldInvokePlugin.execute` 的 move 分支成功后插入 `get_object_registry().relocate_holdings(self.agent.agent_id, target)`。

```python
# test_sim_plugins.py 追加
from examples.west_world_test.recorder.world_object_registry import get_object_registry, reset_object_registry

def test_invoke_move_relocates_holdings(monkeypatch):
    reset_object_registry()
    reg = get_object_registry()
    reg.create(name="左轮", location_id="saloon", by="t", tick=1, action="a", fields={}, held_by="hector")
    # 构造最小 invoke 插件 + fake agent/state/controller，driver 该动作 move saloon->ranch
    # （沿用本文件既有 fake 模式）执行后：
    assert reg.get("obj_0")["location_id"] == "ranch"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py -k follows -q`
Expected: FAIL（当前 `agent_leave` 仍丢弃 / invoke 未调 relocate）

- [ ] **Step 3: 实现**

`structured_location_recorder.py`：删除 `agent_leave` override 与 `_release_holdings`（让 `agent_leave` 回落父类，只更新 present_agents，不动 held_by）。删除 Task 3 的 skip 占位测试。

`WestWorldInvokePlugin.py`：顶部 import `from examples.west_world_test.recorder.world_object_registry import get_object_registry`，在 move 成功分支（`WestWorldInvokePlugin.py:73-75` 设 state 之后）加：
```python
            get_object_registry().relocate_holdings(self.agent.agent_id, new_state["location"])
```

> 进程说明：invoke 插件与 scene 组件同在 pod actor 进程，共享同一 registry 单例，因此 invoke 直接 `get_object_registry()` 合法。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/test_structured_location_recorder.py examples/west_world_test/tests/test_sim_plugins.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py examples/west_world_test/recorder/structured_location_recorder.py examples/west_world_test/tests/test_structured_location_recorder.py examples/west_world_test/tests/test_sim_plugins.py
git commit -m "feat(west-world): held objects follow holder across locations via relocate_holdings"
```

---

## Task 7: 世界级对象快照落盘

**Files:**
- Modify: `examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py`（加 `world_snapshot` 方法）
- Modify: `examples/west_world_test/simulation_logging.py`（加 `record_world_objects` + 文件登记）
- Modify: `examples/west_world_test/run_simulation.py`（每 tick 收集并记录）
- Test: `examples/west_world_test/tests/test_sim_logging.py`（或现有 logging 测试文件）

- [ ] **Step 1: 写失败测试（logging 层）**

在现有 logging 测试文件（`grep -l record_tick examples/west_world_test/tests/*.py` 确认文件名）追加：

```python
def test_record_world_objects_writes_jsonl(tmp_path):
    archive = SimulationArchive(run_dir=tmp_path)   # 沿用该文件既有构造方式
    archive.record_world_objects(tick=0, snapshot={"objects": [{"object_id": "obj_0"}], "ledger": []})
    line = (tmp_path / "world_objects_snapshots.jsonl").read_text(encoding="utf-8").strip()
    import json as _json
    row = _json.loads(line)
    assert row["tick"] == 0
    assert row["objects"][0]["object_id"] == "obj_0"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest examples/west_world_test/tests/ -k world_objects -q`
Expected: FAIL（`record_world_objects` 未定义）

- [ ] **Step 3: 实现**

`LocationRecorderPlugin` 加（registry 共享，任一 scene 返回全量即可）：
```python
    async def world_snapshot(self) -> Dict[str, Any]:
        from examples.west_world_test.recorder.world_object_registry import get_object_registry
        return get_object_registry().snapshot()
```

`simulation_logging.py`：在文件登记表加 `"world_objects_snapshots": "world_objects_snapshots.jsonl",`，并加方法：
```python
    def record_world_objects(self, tick: int, snapshot: Dict[str, Any]) -> None:
        path = self.run_dir / "world_objects_snapshots.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"tick": tick, **snapshot}, ensure_ascii=False) + "\n")
            f.flush()
```

`run_simulation.py`：加一个收集器并在初始快照与每 tick 后调用：
```python
async def _collect_world_objects(pod_manager) -> Dict[str, Any]:
    from examples.west_world_test.worldmap.loader import get_world_map
    any_scene = next(iter(sorted(get_world_map().active_ids())))
    return await pod_manager.run_environment.remote(f"scene_{any_scene}", "world_snapshot")
```
在 `archive.record_tick(-1, ...)` 后加 `archive.record_world_objects(-1, await _collect_world_objects(pod_manager))`；在每 tick 的 `record_tick(tick, ...)` 后同样加 `archive.record_world_objects(tick, await _collect_world_objects(pod_manager))`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest examples/west_world_test/tests/ -k world_objects -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py examples/west_world_test/simulation_logging.py examples/west_world_test/run_simulation.py examples/west_world_test/tests/
git commit -m "feat(west-world): persist world-level object snapshots per tick"
```

---

## Task 8: 全量回归 + 烟雾跑 + 文档

**Files:**
- Modify: `examples/west_world_test/DEVELOPMENT_NOTES.md`

- [ ] **Step 1: 跑全量测试**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests -q`
Expected: 全绿。若有遗留 `object_facts` 断言（如 `test_sim_skeleton.py` / `test_location_recorder.py`），逐个改查 registry 或确认其针对 legacy recorder（legacy 不应被改）。legacy `test_location_recorder.py` 针对 `LocationRecorder`，不涉及 `object_facts`，应自然通过。

- [ ] **Step 2: 短 tick 烟雾跑（需 Redis 在线）**

Run:
```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed WW_RECORDER_MODE=structured WW_MAX_TICKS=4 \
  python -m examples.west_world_test.run_simulation
```
Expected: 正常完成；`output/sim_runs/<run_id>/world_objects_snapshots.jsonl` 存在且每 tick 一行；人工抽查 ledger 里能看到 create/patch（若动作触发）。

> 若无 Redis，跳过本步并在交付说明里注明「烟雾跑待用户在有 Redis 环境执行」。

- [ ] **Step 3: 更新 DEVELOPMENT_NOTES**

把「Structured Recorder 未解架构缺口」一节的四条改为已解决，并指向新模块 `recorder/world_object_registry.py` 与本 plan/spec。保留「正式仿真与 MVE 实验的融合方案」「自由文本动作解析的完整覆盖」为待办（本次未覆盖）。

- [ ] **Step 4: Commit**

```bash
git add examples/west_world_test/DEVELOPMENT_NOTES.md
git commit -m "docs(west-world): mark object-ownership gaps resolved via WorldObjectRegistry"
```

---

## Self-Review 备注（实现者注意）

- **id 全局 vs 测试期望**：Task 1 测试假设单测内 `obj_0` 从 0 起；由于 `_fresh_registry` fixture 每例 `reset_object_registry()`，单例计数器随之归零，断言稳定。务必确保每个动用 registry 的测试都挂了该 fixture（或显式 `reset_object_registry()`）。
- **seed 幂等的两条路径**：`WorldObjectRegistry.seed_from_world`（Task 2，全地图）与 `recorder._seed_location`（Task 3，单地点惰性）都要幂等。运行时实际走的是 recorder 构造时的 `_seed_location`（每个 scene 各 seed 自己那块），`seed_from_world` 主要供 driver/测试整体播种；两者通过「已存在则跳过」保证不重复。
- **held_by 非法处理一致性**：Task 5 最终采用「跳过非法 held_by 字段、保留其它 patch」而非整体 raise，以匹配测试期望对象 held_by 维持 ""。
- **legacy 不动**：任何 `WW_RECORDER_MODE=legacy` 路径与 `core/` MVE 不在改动范围；若回归测试触及它们出错，说明改动越界，需回退。
