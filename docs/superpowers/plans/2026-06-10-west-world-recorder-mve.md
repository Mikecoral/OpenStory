# West World Recorder 双方法对照 MVE 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `examples/west_world_test/` 搭一个最小对照实验，比较「文本存储」与「文生图+识图」两种动态环境表示（Recorder）在状态一致性/防漂移、感知准确率、响应正确性三个指标上的差异。

**Architecture:** 两阶段。**Phase A（纯 Python 实验核心，不依赖 Ray/Redis）**：Oracle 真值状态机 + 两个 Representation（注入 LLM/图像可调用对象，便于 TDD）+ 探针/指标/驱动脚本，跑通整套对照。**Phase B（接入完整 OpenStory distributed 内核）**：用官方 `GenericPlugin`/`GenericComponent` 扩展口把已测核心包成 `scene` 环境组件，加 `ScriptedPlanPlugin` 保证 trajectory 决定性，经 Builder 端到端跑。

**Tech Stack:** Python 3.11、pytest、`agentkernel-distributed` 内核、DashScope（文本 qwen / Qwen-VL 识图 / 通义万相文生图）、matplotlib。

**约定：** 所有命令在 `examples/west_world_test/` 的上层 `OpenStory/` 下执行（除非注明）；`PYTHONPATH` 需包含 `packages/agentkernel-distributed`。测试用 `pytest`。每个 Task 末尾 commit。

---

## 文件结构

```
examples/west_world_test/
├── core/                         # Phase A：纯 Python 实验核心（无内核依赖）
│   ├── __init__.py
│   ├── schema.py                 # Event / SceneState / Probe 数据类 + JSONL 加载
│   ├── oracle.py                 # OracleState：apply(event) + answer(probe)
│   ├── llm_client.py             # LLMClient/ImageGen/VLM 协议 + Fake 实现
│   ├── text_representation.py    # TextRepresentation
│   ├── image_representation.py   # ImageRepresentation
│   ├── metrics.py                # 答案归一化 + 三类指标
│   └── compare.py                # 串起 oracle+representations+probe，出 results.jsonl
├── adapters/                     # Phase A 收尾：真实模型适配
│   ├── __init__.py
│   └── dashscope_clients.py      # 把 DashScope 包成 llm_client 协议
├── data/
│   ├── agents/profiles.jsonl
│   ├── script.jsonl              # 固定动作脚本
│   └── probes.jsonl              # 探针问题集
├── eval/
│   └── plot.py                   # 漂移曲线
├── scene/                        # Phase B：内核环境组件
│   └── SceneRecorderPlugin.py
├── plugins/agent/plan/ScriptedPlanPlugin.py
├── configs/                      # Phase B：yaml 配置
│   ├── simulation_config.yaml
│   ├── agents_config.yaml
│   ├── environment_config.yaml
│   ├── scene_config.yaml
│   ├── models_config.yaml
│   ├── system_config.yaml
│   └── db_config.yaml
├── registry.py
├── run_test.py                   # 轻量 runner（Builder 启动）
└── tests/
    ├── test_schema.py
    ├── test_oracle.py
    ├── test_representations.py
    ├── test_metrics.py
    └── test_compare.py
```

**Phase A（Task 1–10）独立交付**：跑 `python -m examples.west_world_test.core.compare` 即可产出对照结果，无需 Ray/Redis。
**Phase B（Task 11–14）**：把核心接入完整内核。

---

## Phase A — 纯 Python 实验核心

### Task 1: 目录脚手架 + 数据模型 schema

**Files:**
- Create: `examples/west_world_test/__init__.py`（空）
- Create: `examples/west_world_test/core/__init__.py`（空）
- Create: `examples/west_world_test/tests/__init__.py`（空）
- Create: `examples/west_world_test/core/schema.py`
- Test: `examples/west_world_test/tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_schema.py
import json
from examples.west_world_test.core.schema import Event, Probe, load_events, load_probes


def test_event_from_dict_defaults_visibility_public():
    e = Event.from_dict({"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"})
    assert e.tick == 1
    assert e.actor == "酒保"
    assert e.action == "pour_whiskey"
    assert e.target == "glass"
    assert e.visibility == "public"


def test_event_keeps_hidden_visibility():
    e = Event.from_dict({"tick": 2, "actor": "黑衣人", "action": "pick_up_photo",
                         "target": "photo", "visibility": "hidden", "id": "e2"})
    assert e.visibility == "hidden"
    assert e.id == "e2"


def test_probe_from_dict_state_kind():
    p = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?",
                         "field": "glasses_intact", "answer_type": "int"})
    assert p.kind == "state"
    assert p.field == "glasses_intact"
    assert p.answer_type == "int"
    assert p.equals is None


def test_load_events_and_probes_from_jsonl(tmp_path):
    ev = tmp_path / "script.jsonl"
    ev.write_text(json.dumps({"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}) + "\n", encoding="utf-8")
    pr = tmp_path / "probes.jsonl"
    pr.write_text(json.dumps({"id": "q1", "kind": "state", "text": "x", "field": "piano", "answer_type": "str"}) + "\n", encoding="utf-8")
    events = load_events(str(ev))
    probes = load_probes(str(pr))
    assert len(events) == 1 and events[0].action == "pour_whiskey"
    assert len(probes) == 1 and probes[0].id == "q1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_schema.py -v`
Expected: FAIL（`ModuleNotFoundError: ...core.schema`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/schema.py
"""动态环境对照实验的核心数据模型：Event / Probe，以及 JSONL 加载。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    """一个 agent 动作对环境产生的事件。"""
    tick: int
    actor: str
    action: str          # pour_whiskey|pick_up_photo|smash_glass|take_poster|stop_piano|take_revolver|fire_revolver
    target: str          # glass|photo|wanted_poster|piano|revolver|door
    visibility: str = "public"   # public | hidden
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            tick=int(d["tick"]),
            actor=d["actor"],
            action=d["action"],
            target=d["target"],
            visibility=d.get("visibility", "public"),
            id=d.get("id"),
        )


@dataclass
class Probe:
    """一个探针问题。state 类读物理状态字段；visibility 类问某 agent 是否应知道某事件。"""
    id: str
    kind: str            # state | visibility
    text: str
    answer_type: str     # int | bool | str
    field: Optional[str] = None          # state 类：oracle 状态的 dotted path，如 "photo.held_by"
    equals: Optional[Any] = None         # state 类：若给定，答案=(resolved==equals) 的 bool
    subject: Optional[str] = None        # visibility 类：提问的 agent
    fact_event_id: Optional[str] = None  # visibility 类：相关事件 id

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Probe":
        return cls(
            id=d["id"],
            kind=d["kind"],
            text=d["text"],
            answer_type=d.get("answer_type", "str"),
            field=d.get("field"),
            equals=d.get("equals"),
            subject=d.get("subject"),
            fact_event_id=d.get("fact_event_id"),
        )


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_events(path: str) -> List[Event]:
    return [Event.from_dict(r) for r in _load_jsonl(path)]


def load_probes(path: str) -> List[Probe]:
    return [Probe.from_dict(r) for r in _load_jsonl(path)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_schema.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/__init__.py examples/west_world_test/core examples/west_world_test/tests
git commit -m "feat(west-world): add Event/Probe schema and JSONL loaders"
```

---

### Task 2: Oracle 真值状态机 — apply(event)

**Files:**
- Create: `examples/west_world_test/core/oracle.py`
- Test: `examples/west_world_test/tests/test_oracle.py`

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_oracle.py
from examples.west_world_test.core.schema import Event
from examples.west_world_test.core.oracle import OracleState


def _ev(**kw):
    base = {"tick": 1, "actor": "酒保", "action": "noop", "target": "glass"}
    base.update(kw)
    return Event.from_dict(base)


def test_initial_state():
    o = OracleState()
    s = o.state
    assert s["glasses_intact"] == 3
    assert s["wanted_poster"] == "on_wall"
    assert s["piano"] == "playing"
    assert s["photo"]["held_by"] is None
    assert s["revolver"]["fired"] is False


def test_pour_whiskey_decrements_glasses():
    o = OracleState()
    o.apply(_ev(action="pour_whiskey", target="glass"))
    assert o.state["glasses_intact"] == 2


def test_smash_glass_decrements_and_adds_shards():
    o = OracleState()
    o.apply(_ev(action="smash_glass", target="glass"))
    assert o.state["glasses_intact"] == 2
    assert o.state["glass_shards"] is True


def test_pick_up_photo_sets_holder():
    o = OracleState()
    o.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo", visibility="hidden"))
    assert o.state["photo"]["held_by"] == "黑衣人"
    assert o.state["photo"]["pos"] == "held"


def test_take_poster_and_stop_piano_and_revolver():
    o = OracleState()
    o.apply(_ev(actor="黑衣人", action="take_poster", target="wanted_poster"))
    o.apply(_ev(action="stop_piano", target="piano"))
    o.apply(_ev(actor="Dolores", action="take_revolver", target="revolver"))
    o.apply(_ev(actor="Dolores", action="fire_revolver", target="revolver"))
    assert o.state["wanted_poster"] == "taken"
    assert o.state["piano"] == "stopped"
    assert o.state["revolver"]["held_by"] == "Dolores"
    assert o.state["revolver"]["fired"] is True


def test_unknown_action_is_noop():
    o = OracleState()
    before = dict(o.state["glasses_intact"] if False else o.state)
    o.apply(_ev(action="noop", target="glass"))
    assert o.state["glasses_intact"] == 3


def test_event_log_records_all_events():
    o = OracleState()
    o.apply(_ev(action="pour_whiskey", target="glass", id="e1"))
    assert len(o.event_log) == 1
    assert o.event_log[0].id == "e1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_oracle.py -v`
Expected: FAIL（`ModuleNotFoundError: ...core.oracle`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/oracle.py
"""OracleState：确定性真值状态机，是对照实验的裁判（不进入任何表示/agent 上下文）。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .schema import Event, Probe

INITIAL_STATE: Dict[str, Any] = {
    "glasses_intact": 3,
    "glass_shards": False,
    "wanted_poster": "on_wall",                 # on_wall | taken | torn
    "photo": {"pos": "floor", "held_by": None, "hidden": False},
    "piano": "playing",                          # playing | stopped
    "revolver": {"pos": "table", "held_by": None, "fired": False},
    "door": "closed",                            # open | closed
}


class OracleState:
    """维护规范真值状态，并能回答探针。"""

    def __init__(self) -> None:
        self.state: Dict[str, Any] = copy.deepcopy(INITIAL_STATE)
        self.event_log: List[Event] = []

    def apply(self, event: Event) -> None:
        self.event_log.append(event)
        a = event.action
        if a == "pour_whiskey":
            self.state["glasses_intact"] = max(0, self.state["glasses_intact"] - 1)
        elif a == "smash_glass":
            self.state["glasses_intact"] = max(0, self.state["glasses_intact"] - 1)
            self.state["glass_shards"] = True
        elif a == "pick_up_photo":
            self.state["photo"]["held_by"] = event.actor
            self.state["photo"]["pos"] = "held"
            self.state["photo"]["hidden"] = (event.visibility == "hidden")
        elif a == "take_poster":
            self.state["wanted_poster"] = "taken"
        elif a == "tear_poster":
            self.state["wanted_poster"] = "torn"
        elif a == "stop_piano":
            self.state["piano"] = "stopped"
        elif a == "take_revolver":
            self.state["revolver"]["held_by"] = event.actor
            self.state["revolver"]["pos"] = "held"
        elif a == "fire_revolver":
            self.state["revolver"]["fired"] = True
        elif a == "open_door":
            self.state["door"] = "open"
        # 未知 action 视为 noop（已记入 event_log）
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_oracle.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/oracle.py examples/west_world_test/tests/test_oracle.py
git commit -m "feat(west-world): add OracleState deterministic apply()"
```

---

### Task 3: Oracle 探针解析 — answer(probe)

**Files:**
- Modify: `examples/west_world_test/core/oracle.py`（追加 `answer` 与 `_resolve_field`）
- Test: `examples/west_world_test/tests/test_oracle.py`（追加）

- [ ] **Step 1: Write the failing test**

```python
# 追加到 examples/west_world_test/tests/test_oracle.py
from examples.west_world_test.core.schema import Probe


def test_answer_state_int_field():
    o = OracleState()
    o.apply(_ev(action="pour_whiskey", target="glass"))
    p = Probe.from_dict({"id": "q1", "kind": "state", "text": "x",
                         "field": "glasses_intact", "answer_type": "int"})
    assert o.answer(p) == 2


def test_answer_state_dotted_field():
    o = OracleState()
    o.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo", visibility="hidden"))
    p = Probe.from_dict({"id": "q2", "kind": "state", "text": "x",
                         "field": "photo.held_by", "answer_type": "str"})
    assert o.answer(p) == "黑衣人"


def test_answer_state_equals_returns_bool():
    o = OracleState()
    p = Probe.from_dict({"id": "q3", "kind": "state", "text": "通缉令还在墙上吗",
                         "field": "wanted_poster", "equals": "on_wall", "answer_type": "bool"})
    assert o.answer(p) is True
    o.apply(_ev(actor="黑衣人", action="take_poster", target="wanted_poster"))
    assert o.answer(p) is False


def test_answer_visibility_hidden_event_not_known_by_others():
    o = OracleState()
    o.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo",
                visibility="hidden", id="e2"))
    p = Probe.from_dict({"id": "q4", "kind": "visibility", "text": "Dolores 知道吗",
                         "subject": "Dolores", "fact_event_id": "e2", "answer_type": "bool"})
    assert o.answer(p) is False
    # 当事人自己知道
    p2 = Probe.from_dict({"id": "q5", "kind": "visibility", "text": "黑衣人知道吗",
                          "subject": "黑衣人", "fact_event_id": "e2", "answer_type": "bool"})
    assert o.answer(p2) is True


def test_answer_visibility_public_event_known_by_all():
    o = OracleState()
    o.apply(_ev(actor="酒保", action="smash_glass", target="glass",
                visibility="public", id="e3"))
    p = Probe.from_dict({"id": "q6", "kind": "visibility", "text": "Dolores 知道吗",
                         "subject": "Dolores", "fact_event_id": "e3", "answer_type": "bool"})
    assert o.answer(p) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_oracle.py -k answer -v`
Expected: FAIL（`AttributeError: 'OracleState' object has no attribute 'answer'`）

- [ ] **Step 3: Write minimal implementation**

```python
# 追加到 examples/west_world_test/core/oracle.py（class OracleState 内）
    def _resolve_field(self, dotted: str) -> Any:
        cur: Any = self.state
        for part in dotted.split("."):
            cur = cur[part]
        return cur

    def answer(self, probe: Probe) -> Any:
        if probe.kind == "state":
            value = self._resolve_field(probe.field)
            if probe.equals is not None:
                return value == probe.equals
            return value
        if probe.kind == "visibility":
            for ev in self.event_log:
                if ev.id == probe.fact_event_id:
                    if ev.actor == probe.subject:
                        return True
                    return ev.visibility == "public"
            return False
        raise ValueError(f"未知探针类型: {probe.kind}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_oracle.py -v`
Expected: PASS（全部 oracle 测试通过）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/oracle.py examples/west_world_test/tests/test_oracle.py
git commit -m "feat(west-world): add OracleState.answer() for state & visibility probes"
```

---

### Task 4: 实验数据 — profiles / script / probes

**Files:**
- Create: `examples/west_world_test/data/agents/profiles.jsonl`
- Create: `examples/west_world_test/data/script.jsonl`
- Create: `examples/west_world_test/data/probes.jsonl`
- Test: `examples/west_world_test/tests/test_schema.py`（追加一致性测试）

- [ ] **Step 1: Write the failing test**

```python
# 追加到 examples/west_world_test/tests/test_schema.py
import os
from examples.west_world_test.core.oracle import OracleState

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def test_real_data_files_load_and_are_consistent():
    events = load_events(os.path.join(DATA, "script.jsonl"))
    probes = load_probes(os.path.join(DATA, "probes.jsonl"))
    assert len(events) >= 8
    assert len(probes) >= 8
    # 脚本能被 oracle 完整 apply
    o = OracleState()
    for e in sorted(events, key=lambda x: x.tick):
        o.apply(e)
    # 每个 state 探针的 field 在 oracle 状态里可解析；每个 visibility 探针的事件 id 存在
    event_ids = {e.id for e in events if e.id}
    for p in probes:
        if p.kind == "state":
            o.answer(p)  # 不抛异常即说明 field 合法
        else:
            assert p.fact_event_id in event_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_schema.py -k real_data -v`
Expected: FAIL（`FileNotFoundError: .../data/script.jsonl`）

- [ ] **Step 3: Create the data files**

`examples/west_world_test/data/agents/profiles.jsonl`:
```json
{"id": "Dolores", "role": "牧场主之女", "persona": "温柔、好奇，循环中的接待员"}
{"id": "酒保", "role": "Sweetwater 酒馆酒保", "persona": "话多、爱擦杯子"}
{"id": "黑衣人", "role": "神秘访客", "persona": "冷峻、寻找迷宫线索"}
```

`examples/west_world_test/data/script.jsonl`（决定性 trajectory，覆盖计数/隐蔽/广播/易主/翻转）:
```json
{"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "visibility": "public"}
{"id": "e2", "tick": 2, "actor": "黑衣人", "action": "pick_up_photo", "target": "photo", "visibility": "hidden"}
{"id": "e3", "tick": 3, "actor": "酒保", "action": "smash_glass", "target": "glass", "visibility": "public"}
{"id": "e4", "tick": 4, "actor": "黑衣人", "action": "take_poster", "target": "wanted_poster", "visibility": "public"}
{"id": "e5", "tick": 5, "actor": "酒保", "action": "stop_piano", "target": "piano", "visibility": "public"}
{"id": "e6", "tick": 6, "actor": "Dolores", "action": "pour_whiskey", "target": "glass", "visibility": "public"}
{"id": "e7", "tick": 7, "actor": "Dolores", "action": "take_revolver", "target": "revolver", "visibility": "public"}
{"id": "e8", "tick": 8, "actor": "Dolores", "action": "fire_revolver", "target": "revolver", "visibility": "public"}
```

`examples/west_world_test/data/probes.jsonl`（每 tick 都会被问；答案由 oracle 决定）:
```json
{"id": "q1", "kind": "state", "text": "现在吧台上还有几个完整的酒杯？只回答数字。", "field": "glasses_intact", "answer_type": "int"}
{"id": "q2", "kind": "state", "text": "地上有没有打碎的玻璃碎片？回答 是 或 否。", "field": "glass_shards", "equals": true, "answer_type": "bool"}
{"id": "q3", "kind": "state", "text": "墙上的通缉令还在吗？回答 是 或 否。", "field": "wanted_poster", "equals": "on_wall", "answer_type": "bool"}
{"id": "q4", "kind": "state", "text": "那张旧照片现在在谁手里？没人拿就回答 无。", "field": "photo.held_by", "answer_type": "str"}
{"id": "q5", "kind": "state", "text": "自动钢琴还在演奏吗？回答 是 或 否。", "field": "piano", "equals": "playing", "answer_type": "bool"}
{"id": "q6", "kind": "state", "text": "桌上的左轮手枪还在原位吗？回答 是 或 否。", "field": "revolver.pos", "equals": "table", "answer_type": "bool"}
{"id": "q7", "kind": "state", "text": "左轮手枪开过火了吗？回答 是 或 否。", "field": "revolver.fired", "equals": true, "answer_type": "bool"}
{"id": "q8", "kind": "visibility", "text": "Dolores 知道是黑衣人拿走了那张旧照片吗？回答 是 或 否。", "subject": "Dolores", "fact_event_id": "e2", "answer_type": "bool"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/data
git commit -m "feat(west-world): add scenario data (profiles, action script, probe set)"
```

---

### Task 5: LLM 客户端协议 + Fake

**Files:**
- Create: `examples/west_world_test/core/llm_client.py`
- Test: `examples/west_world_test/tests/test_representations.py`

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_representations.py
from examples.west_world_test.core.llm_client import FakeLLM, FakeImageGen, FakeVLM


def test_fake_llm_returns_scripted_replies_in_order():
    llm = FakeLLM(["回复A", "回复B"])
    assert llm.chat("p1") == "回复A"
    assert llm.chat("p2") == "回复B"
    assert llm.calls == ["p1", "p2"]


def test_fake_llm_default_when_exhausted():
    llm = FakeLLM([], default="DEF")
    assert llm.chat("x") == "DEF"


def test_fake_image_gen_records_prompt_and_returns_handle():
    gen = FakeImageGen()
    handle = gen.generate("一个酒馆，吧台上有2个酒杯")
    assert "酒馆" in gen.prompts[0]
    assert handle  # 非空句柄


def test_fake_vlm_answers_from_scripted():
    vlm = FakeVLM(["2"])
    assert vlm.ask("handle://img", "几个酒杯?") == "2"
    assert vlm.calls[0][1] == "几个酒杯?"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -k Fake -v`
Expected: FAIL（`ModuleNotFoundError: ...core.llm_client`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/llm_client.py
"""模型调用协议 + 测试用 Fake。真实适配见 adapters/dashscope_clients.py。"""
from __future__ import annotations

from typing import List, Optional, Protocol, Tuple


class LLMClient(Protocol):
    def chat(self, prompt: str) -> str: ...


class ImageGen(Protocol):
    def generate(self, prompt: str) -> str:  # 返回图像句柄（URL 或本地路径）
        ...


class VLM(Protocol):
    def ask(self, image_handle: str, question: str) -> str: ...


class FakeLLM:
    def __init__(self, replies: List[str], default: str = "") -> None:
        self._replies = list(replies)
        self._default = default
        self.calls: List[str] = []

    def chat(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self._replies:
            return self._replies.pop(0)
        return self._default


class FakeImageGen:
    def __init__(self) -> None:
        self.prompts: List[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"fake-image://{len(self.prompts)}"


class FakeVLM:
    def __init__(self, replies: List[str], default: str = "") -> None:
        self._replies = list(replies)
        self._default = default
        self.calls: List[Tuple[str, str]] = []

    def ask(self, image_handle: str, question: str) -> str:
        self.calls.append((image_handle, question))
        if self._replies:
            return self._replies.pop(0)
        return self._default
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -k Fake -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/llm_client.py examples/west_world_test/tests/test_representations.py
git commit -m "feat(west-world): add LLM/ImageGen/VLM protocols and fakes"
```

---

### Task 6: TextRepresentation

**Files:**
- Create: `examples/west_world_test/core/text_representation.py`
- Test: `examples/west_world_test/tests/test_representations.py`（追加）

- [ ] **Step 1: Write the failing test**

```python
# 追加到 examples/west_world_test/tests/test_representations.py
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


def _ev(**kw):
    base = {"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}
    base.update(kw)
    return Event.from_dict(base)


def test_update_calls_llm_with_prev_text_and_event_and_stores_result():
    llm = FakeLLM(["吧台上有2个完整酒杯。"])
    rep = TextRepresentation(llm, initial_text="吧台上有3个完整酒杯。")
    rep.update(_ev(action="pour_whiskey"))
    assert rep.text == "吧台上有2个完整酒杯。"
    # prompt 里应带上旧文本和事件描述
    assert "3个完整酒杯" in llm.calls[0]
    assert "pour_whiskey" in llm.calls[0] or "倒酒" in llm.calls[0]


def test_answer_calls_llm_with_current_text_and_question():
    llm = FakeLLM(["3"])
    rep = TextRepresentation(llm, initial_text="吧台上有3个完整酒杯。")
    p = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?",
                         "field": "glasses_intact", "answer_type": "int"})
    ans = rep.answer(p)
    assert ans == "3"
    assert "吧台上有3个完整酒杯" in llm.calls[0]
    assert "几个完整酒杯" in llm.calls[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -k Text -v`
Expected: FAIL（`ModuleNotFoundError: ...text_representation`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/text_representation.py
"""TextRepresentation：用分块文本存储动态环境，LLM 读文本作答。看不到 Oracle。"""
from __future__ import annotations

from .llm_client import LLMClient
from .schema import Event, Probe

DEFAULT_INITIAL_TEXT = (
    "【Sweetwater 酒馆】\n"
    "- 吧台：上面摆着 3 个完整的酒杯，没有碎片。\n"
    "- 墙上：贴着一张通缉令。\n"
    "- 地上：有一张旧照片，没人捡。\n"
    "- 角落：一架自动钢琴正在演奏。\n"
    "- 桌上：放着一把左轮手枪，未开火。\n"
    "- 门：关着。"
)

_UPDATE_PROMPT = """你在维护一个酒馆场景的文字记录。下面是【当前记录】和【刚发生的动作】。
请把动作的后果更新进记录，只输出更新后的完整记录，不要解释。

【当前记录】
{prev}

【刚发生的动作】
tick={tick} 行动者={actor} 动作={action} 目标={target} 可见性={visibility}
"""

_ANSWER_PROMPT = """根据下面的酒馆场景记录回答问题。只输出最简短的答案（数字或"是/否"或人名/无），不要解释。

【场景记录】
{text}

【问题】{question}
"""


class TextRepresentation:
    def __init__(self, llm: LLMClient, initial_text: str = DEFAULT_INITIAL_TEXT) -> None:
        self._llm = llm
        self.text = initial_text

    def update(self, event: Event) -> None:
        prompt = _UPDATE_PROMPT.format(
            prev=self.text, tick=event.tick, actor=event.actor,
            action=event.action, target=event.target, visibility=event.visibility,
        )
        self.text = self._llm.chat(prompt).strip()

    def answer(self, probe: Probe) -> str:
        prompt = _ANSWER_PROMPT.format(text=self.text, question=probe.text)
        return self._llm.chat(prompt).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -k Text -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/text_representation.py examples/west_world_test/tests/test_representations.py
git commit -m "feat(west-world): add TextRepresentation (text storage + LLM readout)"
```

---

### Task 7: ImageRepresentation

**Files:**
- Create: `examples/west_world_test/core/image_representation.py`
- Test: `examples/west_world_test/tests/test_representations.py`（追加）

**说明：** 为隔离"唯一受控变量=读出介质"，ImageRepresentation 用**与 Text 方法相同的 LLM 更新逻辑**维护一份内部文字场景描述；不同之处仅在 `answer` 时把场景描述送文生图 → 用 VLM 识图作答。

- [ ] **Step 1: Write the failing test**

```python
# 追加到 examples/west_world_test/tests/test_representations.py
from examples.west_world_test.core.image_representation import ImageRepresentation


def test_image_update_uses_llm_like_text():
    llm = FakeLLM(["吧台上有2个完整酒杯。"])
    gen, vlm = FakeImageGen(), FakeVLM([])
    rep = ImageRepresentation(llm, gen, vlm, initial_text="吧台上有3个完整酒杯。")
    rep.update(_ev(action="pour_whiskey"))
    assert rep.scene_text == "吧台上有2个完整酒杯。"
    assert "3个完整酒杯" in llm.calls[0]


def test_image_answer_renders_then_asks_vlm():
    llm = FakeLLM([])
    gen, vlm = FakeImageGen(), FakeVLM(["2"])
    rep = ImageRepresentation(llm, gen, vlm, initial_text="吧台上有2个完整酒杯。")
    p = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?",
                         "field": "glasses_intact", "answer_type": "int"})
    ans = rep.answer(p)
    assert ans == "2"
    # 先生成图（prompt 含场景描述），再用该图问 VLM
    assert "2个完整酒杯" in gen.prompts[0]
    assert vlm.calls[0][0].startswith("fake-image://")
    assert vlm.calls[0][1] == "几个完整酒杯?"


def test_image_answer_caches_image_per_scene_text():
    llm = FakeLLM([])
    gen, vlm = FakeImageGen(), FakeVLM(["a", "b"])
    rep = ImageRepresentation(llm, gen, vlm, initial_text="场景X")
    p1 = Probe.from_dict({"id": "q1", "kind": "state", "text": "问1", "field": "piano", "answer_type": "str"})
    p2 = Probe.from_dict({"id": "q2", "kind": "state", "text": "问2", "field": "piano", "answer_type": "str"})
    rep.answer(p1)
    rep.answer(p2)
    # 同一 scene_text 只生成一次图（避免每条探针重复烧钱）
    assert len(gen.prompts) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -k image -v`
Expected: FAIL（`ModuleNotFoundError: ...image_representation`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/image_representation.py
"""ImageRepresentation：更新逻辑同 Text（受控变量隔离），但读出=文生图+VLM 识图。"""
from __future__ import annotations

from typing import Optional

from .llm_client import ImageGen, LLMClient, VLM
from .schema import Event, Probe
from .text_representation import DEFAULT_INITIAL_TEXT, _UPDATE_PROMPT

_IMAGE_PROMPT = (
    "西部世界 Sweetwater 酒馆俯视全景，写实风格。严格按以下描述呈现可数物体的数量与位置：\n{scene}"
)


class ImageRepresentation:
    def __init__(self, llm: LLMClient, image_gen: ImageGen, vlm: VLM,
                 initial_text: str = DEFAULT_INITIAL_TEXT) -> None:
        self._llm = llm
        self._gen = image_gen
        self._vlm = vlm
        self.scene_text = initial_text
        self._cached_handle: Optional[str] = None
        self._cached_for: Optional[str] = None

    def update(self, event: Event) -> None:
        prompt = _UPDATE_PROMPT.format(
            prev=self.scene_text, tick=event.tick, actor=event.actor,
            action=event.action, target=event.target, visibility=event.visibility,
        )
        self.scene_text = self._llm.chat(prompt).strip()
        self._cached_handle = None  # 场景变了，作废缓存

    def _current_image(self) -> str:
        if self._cached_handle is None or self._cached_for != self.scene_text:
            self._cached_handle = self._gen.generate(_IMAGE_PROMPT.format(scene=self.scene_text))
            self._cached_for = self.scene_text
        return self._cached_handle

    def answer(self, probe: Probe) -> str:
        handle = self._current_image()
        return self._vlm.ask(handle, probe.text).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_representations.py -v`
Expected: PASS（全部 representation 测试通过）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/image_representation.py examples/west_world_test/tests/test_representations.py
git commit -m "feat(west-world): add ImageRepresentation (text-to-image + VLM readout)"
```

---

### Task 8: metrics — 答案归一化 + 三类指标

**Files:**
- Create: `examples/west_world_test/core/metrics.py`
- Test: `examples/west_world_test/tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_metrics.py
from examples.west_world_test.core.metrics import (
    normalize, is_correct, accuracy_over_ticks, drift_slope, contradiction_count,
)


def test_normalize_int():
    assert normalize("还有 2 个", "int") == "2"
    assert normalize("两个", "int") == "两个"  # 无阿拉伯数字时原样小写去空格


def test_normalize_bool_variants():
    assert normalize("是的", "bool") == "true"
    assert normalize("不在", "bool") == "false"
    assert normalize("否", "bool") == "false"
    assert normalize("yes", "bool") == "true"


def test_is_correct_int_and_bool_and_str():
    assert is_correct("吧台还剩2个", 2, "int") is True
    assert is_correct("否", False, "bool") is True
    assert is_correct("黑衣人", "黑衣人", "str") is True
    assert is_correct("无", None, "str") is True   # None 真值匹配 "无"


def test_accuracy_over_ticks_groups_by_tick():
    records = [
        {"tick": 1, "correct": True}, {"tick": 1, "correct": False},
        {"tick": 2, "correct": True}, {"tick": 2, "correct": True},
    ]
    acc = accuracy_over_ticks(records)
    assert acc[1] == 0.5
    assert acc[2] == 1.0


def test_drift_slope_negative_when_accuracy_drops():
    acc = {1: 1.0, 2: 0.8, 3: 0.6}
    assert drift_slope(acc) < 0


def test_contradiction_count_detects_field_flip_without_event():
    # 同一探针字段，相邻 tick 答案翻转但该 tick 没有相关事件 → 算一次自相矛盾
    records = [
        {"tick": 1, "probe_id": "q1", "norm": "3", "had_relevant_event": False},
        {"tick": 2, "probe_id": "q1", "norm": "2", "had_relevant_event": False},
    ]
    assert contradiction_count(records) == 1
    records2 = [
        {"tick": 1, "probe_id": "q1", "norm": "3", "had_relevant_event": False},
        {"tick": 2, "probe_id": "q1", "norm": "2", "had_relevant_event": True},
    ]
    assert contradiction_count(records2) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_metrics.py -v`
Expected: FAIL（`ModuleNotFoundError: ...core.metrics`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/metrics.py
"""答案归一化与三类指标：感知准确率、防漂移、响应/一致性辅助。"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_TRUE_WORDS = {"true", "是", "是的", "在", "有", "yes", "y", "对"}
_FALSE_WORDS = {"false", "否", "不是", "不在", "没有", "无", "no", "n"}


def normalize(answer: str, answer_type: str) -> str:
    s = (answer or "").strip().lower()
    if answer_type == "int":
        m = re.search(r"-?\d+", s)
        return m.group(0) if m else s.replace(" ", "")
    if answer_type == "bool":
        for w in _TRUE_WORDS:
            if w in s:
                return "true"
        for w in _FALSE_WORDS:
            if w in s:
                return "false"
        return s.replace(" ", "")
    return s.replace(" ", "")


def _truth_to_norm(truth: Any, answer_type: str) -> str:
    if answer_type == "int":
        return str(truth)
    if answer_type == "bool":
        return "true" if truth else "false"
    if truth is None:
        return "无"
    return str(truth).strip().lower()


def is_correct(answer: str, truth: Any, answer_type: str) -> bool:
    norm = normalize(answer, answer_type)
    truth_norm = _truth_to_norm(truth, answer_type)
    if answer_type == "str" and truth is None:
        return norm in {"无", "none", "没人", "没有人"}
    return norm == truth_norm


def accuracy_over_ticks(records: List[Dict[str, Any]]) -> Dict[int, float]:
    by_tick: Dict[int, List[bool]] = {}
    for r in records:
        by_tick.setdefault(r["tick"], []).append(bool(r["correct"]))
    return {t: sum(v) / len(v) for t, v in by_tick.items()}


def drift_slope(acc_by_tick: Dict[int, float]) -> float:
    """对 (tick, accuracy) 做最小二乘斜率；负值=随时间漂移退化。"""
    ticks = sorted(acc_by_tick)
    n = len(ticks)
    if n < 2:
        return 0.0
    xs = ticks
    ys = [acc_by_tick[t] for t in ticks]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def contradiction_count(records: List[Dict[str, Any]]) -> int:
    """同一 probe 相邻 tick 归一化答案变化、但该 tick 无相关事件 → 自相矛盾。"""
    by_probe: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        by_probe.setdefault(r["probe_id"], []).append(r)
    total = 0
    for seq in by_probe.values():
        seq = sorted(seq, key=lambda x: x["tick"])
        for prev, cur in zip(seq, seq[1:]):
            if cur["norm"] != prev["norm"] and not cur.get("had_relevant_event", False):
                total += 1
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_metrics.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/metrics.py examples/west_world_test/tests/test_metrics.py
git commit -m "feat(west-world): add answer normalization and drift/accuracy/contradiction metrics"
```

---

### Task 9: compare 驱动 — 串起整套对照

**Files:**
- Create: `examples/west_world_test/core/compare.py`
- Test: `examples/west_world_test/tests/test_compare.py`

**逻辑：** 给定 events/probes 与「方法→representation」映射，按 tick 推进：每 tick 先对每个 representation `update(event)` 与 `oracle.apply(event)`，再用所有 probe 问每个 representation，并用 oracle 真值打分，产出逐条 record。`had_relevant_event` = 该 tick 的事件 target/field 是否与该 probe 相关（用 probe.field 顶层 key 与 event.target 的映射判断）。

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_compare.py
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.core.text_representation import TextRepresentation
from examples.west_world_test.core.compare import run_comparison


def test_run_comparison_produces_records_and_summary():
    events = [
        Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}),
    ]
    probes = [
        Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?",
                         "field": "glasses_intact", "answer_type": "int"}),
    ]
    # representation 工厂：text 方法每次回答 "2"（恰好等于 oracle 倒酒后的真值）
    def make_text():
        return TextRepresentation(FakeLLM(["更新后的记录", "2"]), initial_text="init")
    result = run_comparison(events, probes, {"text": make_text})
    records = result["records"]
    assert len(records) == 1
    rec = records[0]
    assert rec["method"] == "text"
    assert rec["tick"] == 1
    assert rec["truth"] == 2
    assert rec["correct"] is True
    assert rec["had_relevant_event"] is True   # 该 tick 倒酒影响 glasses
    # summary 含三类指标
    summ = result["summary"]["text"]
    assert "accuracy" in summ and "drift_slope" in summ and "contradictions" in summ


def test_relevance_flag_false_for_unrelated_probe():
    events = [
        Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}),
    ]
    probes = [
        Probe.from_dict({"id": "q5", "kind": "state", "text": "钢琴在演奏吗?",
                         "field": "piano", "equals": "playing", "answer_type": "bool"}),
    ]
    def make_text():
        return TextRepresentation(FakeLLM(["rec", "是"]), initial_text="init")
    result = run_comparison(events, probes, {"text": make_text})
    assert result["records"][0]["had_relevant_event"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_compare.py -v`
Expected: FAIL（`ModuleNotFoundError: ...core.compare`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/core/compare.py
"""对照驱动：固定脚本 + 双表示并行 + Oracle 探针打分。可独立运行（无内核依赖）。"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable, Dict, List

from .metrics import (accuracy_over_ticks, contradiction_count, drift_slope,
                      is_correct, normalize)
from .oracle import OracleState
from .schema import Event, Probe, load_events, load_probes

# probe.field 顶层 key ↔ event.target 的相关性映射
_FIELD_TARGET = {
    "glasses_intact": {"glass"},
    "glass_shards": {"glass"},
    "wanted_poster": {"wanted_poster"},
    "photo": {"photo"},
    "piano": {"piano"},
    "revolver": {"revolver"},
    "door": {"door"},
}


def _is_relevant(probe: Probe, event: Event) -> bool:
    if probe.kind == "visibility":
        return event.id == probe.fact_event_id
    top = (probe.field or "").split(".")[0]
    return event.target in _FIELD_TARGET.get(top, set())


def run_comparison(events: List[Event], probes: List[Probe],
                   rep_factories: Dict[str, Callable[[], Any]]) -> Dict[str, Any]:
    oracle = OracleState()
    reps = {name: factory() for name, factory in rep_factories.items()}
    records: List[Dict[str, Any]] = []

    for event in sorted(events, key=lambda e: e.tick):
        tick = event.tick
        oracle.apply(event)
        for rep in reps.values():
            rep.update(event)
        for probe in probes:
            truth = oracle.answer(probe)
            relevant = _is_relevant(probe, event)
            for name, rep in reps.items():
                raw = rep.answer(probe)
                records.append({
                    "tick": tick,
                    "method": name,
                    "probe_id": probe.id,
                    "answer": raw,
                    "norm": normalize(raw, probe.answer_type),
                    "truth": truth,
                    "correct": is_correct(raw, truth, probe.answer_type),
                    "had_relevant_event": relevant,
                })

    summary: Dict[str, Any] = {}
    for name in reps:
        recs = [r for r in records if r["method"] == name]
        acc = accuracy_over_ticks(recs)
        summary[name] = {
            "accuracy": (sum(r["correct"] for r in recs) / len(recs)) if recs else 0.0,
            "accuracy_by_tick": acc,
            "drift_slope": drift_slope(acc),
            "contradictions": contradiction_count(recs),
        }
    return {"records": records, "summary": summary}


def _build_real_reps(method: str) -> Dict[str, Callable[[], Any]]:
    """用真实 DashScope 适配器构造 representation 工厂（运行时才 import，避免测试依赖网络）。"""
    from ..adapters.dashscope_clients import build_llm, build_image_gen, build_vlm
    from .text_representation import TextRepresentation
    from .image_representation import ImageRepresentation

    factories: Dict[str, Callable[[], Any]] = {}
    if method in ("text", "both"):
        factories["text"] = lambda: TextRepresentation(build_llm())
    if method in ("image", "both"):
        factories["image"] = lambda: ImageRepresentation(build_llm(), build_image_gen(), build_vlm())
    return factories


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["text", "image", "both"], default="both")
    parser.add_argument("--data-dir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    parser.add_argument("--out", default="examples/west_world_test/results.jsonl")
    args = parser.parse_args()

    events = load_events(os.path.join(args.data_dir, "script.jsonl"))
    probes = load_probes(os.path.join(args.data_dir, "probes.jsonl"))
    result = run_comparison(events, probes, _build_real_reps(args.method))

    with open(args.out, "w", encoding="utf-8") as f:
        for r in result["records"]:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_compare.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/core/compare.py examples/west_world_test/tests/test_compare.py
git commit -m "feat(west-world): add comparison driver with oracle scoring and summary"
```

---

### Task 10: 真实模型适配 + 漂移曲线

**Files:**
- Create: `examples/west_world_test/adapters/__init__.py`（空）
- Create: `examples/west_world_test/adapters/dashscope_clients.py`
- Create: `examples/west_world_test/eval/plot.py`
- Test: 无新单测（依赖网络/密钥）；用 smoke 校验 import 与 plot 产物。

- [ ] **Step 1: Write the adapters**

```python
# examples/west_world_test/adapters/dashscope_clients.py
"""把 DashScope 模型包成 core.llm_client 协议。API key 从环境变量读取。
需要：pip install dashscope  ；export DASHSCOPE_API_KEY=sk-xxx
"""
from __future__ import annotations

import os
from typing import List

import dashscope
from dashscope import Generation, MultiModalConversation, ImageSynthesis

_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
dashscope.api_key = _API_KEY

TEXT_MODEL = os.environ.get("WW_TEXT_MODEL", "qwen-plus")
VLM_MODEL = os.environ.get("WW_VLM_MODEL", "qwen-vl-plus")
IMAGE_MODEL = os.environ.get("WW_IMAGE_MODEL", "wanx2.1-t2i-turbo")


class DashScopeLLM:
    def chat(self, prompt: str) -> str:
        resp = Generation.call(model=TEXT_MODEL,
                               messages=[{"role": "user", "content": prompt}],
                               result_format="message")
        return resp.output.choices[0].message.content


class DashScopeImageGen:
    def generate(self, prompt: str) -> str:
        rsp = ImageSynthesis.call(model=IMAGE_MODEL, prompt=prompt, n=1, size="1024*1024")
        return rsp.output.results[0].url  # 返回图片 URL


class DashScopeVLM:
    def ask(self, image_handle: str, question: str) -> str:
        messages = [{"role": "user", "content": [
            {"image": image_handle}, {"text": question}]}]
        resp = MultiModalConversation.call(model=VLM_MODEL, messages=messages)
        content = resp.output.choices[0].message.content
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content)
        return content


def build_llm() -> DashScopeLLM: return DashScopeLLM()
def build_image_gen() -> DashScopeImageGen: return DashScopeImageGen()
def build_vlm() -> DashScopeVLM: return DashScopeVLM()
```

- [ ] **Step 2: Write the plot script**

```python
# examples/west_world_test/eval/plot.py
"""从 results.jsonl 画"准确率随 tick"漂移曲线（text vs image）。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="examples/west_world_test/results.jsonl")
    ap.add_argument("--out", default="examples/west_world_test/drift_curve.png")
    args = ap.parse_args()

    agg = defaultdict(lambda: defaultdict(list))  # method -> tick -> [correct]
    with open(args.results, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            agg[r["method"]][r["tick"]].append(bool(r["correct"]))

    plt.figure(figsize=(7, 4))
    for method, by_tick in agg.items():
        ticks = sorted(by_tick)
        acc = [sum(by_tick[t]) / len(by_tick[t]) for t in ticks]
        plt.plot(ticks, acc, marker="o", label=method)
    plt.xlabel("tick"); plt.ylabel("probe accuracy"); plt.ylim(0, 1.05)
    plt.title("Recorder drift: accuracy over ticks"); plt.legend(); plt.grid(True, alpha=0.3)
    plt.tight_layout(); plt.savefig(args.out, dpi=150)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test — adapters import & plot from synthetic results**

Run:
```bash
PYTHONPATH=packages/agentkernel-distributed:. python -c "import examples.west_world_test.eval.plot as p; print('plot ok')"
printf '{"method":"text","tick":1,"correct":true}\n{"method":"image","tick":1,"correct":false}\n' > /tmp/r.jsonl
PYTHONPATH=packages/agentkernel-distributed:. python -m examples.west_world_test.eval.plot --results /tmp/r.jsonl --out /tmp/d.png && test -f /tmp/d.png && echo PLOT_OK
```
Expected: 输出 `plot ok`、`saved /tmp/d.png`、`PLOT_OK`。（adapters 需要 dashscope 包与密钥，本步不实跑网络。）

- [ ] **Step 4: 真实对照运行（手动，需密钥）**

Run:
```bash
export DASHSCOPE_API_KEY=sk-你的key
PYTHONPATH=packages/agentkernel-distributed:. python -m examples.west_world_test.core.compare --method both
PYTHONPATH=packages/agentkernel-distributed:. python -m examples.west_world_test.eval.plot
```
Expected: 打印 text/image 的三类指标 summary，生成 `results.jsonl` 与 `drift_curve.png`。

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/adapters examples/west_world_test/eval/plot.py
git commit -m "feat(west-world): add DashScope adapters and drift-curve plot"
```

> ✅ **Phase A 完成即可独立产出对照结果。** Phase B 把该核心接入完整内核。

---

## Phase B — 接入完整 OpenStory distributed 内核

### Task 11: SceneRecorderPlugin（GenericPlugin 包裹核心）

**Files:**
- Create: `examples/west_world_test/scene/__init__.py`（空）
- Create: `examples/west_world_test/scene/SceneRecorderPlugin.py`
- Test: `examples/west_world_test/tests/test_scene_plugin.py`

**说明：** `scene` 是内核 `GenericComponent` 支持的自定义环境组件类型（见 `mas/environment/components/generic.py` 的 `create_component_class` / `get_or_create_component_class`）。插件继承 `GenericPlugin` 并 `COMPONENT_TYPE="scene"`，内部持有 Phase A 的 oracle + representations，对外暴露 `apply_event` / `probe`。

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_scene_plugin.py
import asyncio
from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.scene.SceneRecorderPlugin import SceneRecorderPlugin


def test_plugin_component_type_is_scene():
    assert SceneRecorderPlugin.COMPONENT_TYPE == "scene"


def test_plugin_apply_and_probe_with_fakes():
    plugin = SceneRecorderPlugin(method="text",
                                 llm_factory=lambda: FakeLLM(["更新", "2"], default="2"))
    asyncio.run(plugin.apply_event({"id": "e1", "tick": 1, "actor": "酒保",
                                    "action": "pour_whiskey", "target": "glass",
                                    "visibility": "public"}))
    res = asyncio.run(plugin.probe({"id": "q1", "kind": "state", "text": "几个完整酒杯?",
                                    "field": "glasses_intact", "answer_type": "int"}))
    assert res["truth"] == 2
    assert "text" in res["answers"]
    assert res["answers"]["text"]["correct"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_scene_plugin.py -v`
Expected: FAIL（`ModuleNotFoundError: ...scene.SceneRecorderPlugin`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/scene/SceneRecorderPlugin.py
"""scene 环境组件插件：内核侧动态环境表示（Recorder），包裹 Phase A 实验核心。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from agentkernel_distributed.mas.environment.base.plugin_base import GenericPlugin

from examples.west_world_test.core.compare import _is_relevant
from examples.west_world_test.core.metrics import is_correct, normalize
from examples.west_world_test.core.oracle import OracleState
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation
from examples.west_world_test.core.image_representation import ImageRepresentation


class SceneRecorderPlugin(GenericPlugin):
    COMPONENT_TYPE = "scene"

    def __init__(self, method: str = "both",
                 llm_factory: Optional[Callable[[], Any]] = None,
                 image_gen_factory: Optional[Callable[[], Any]] = None,
                 vlm_factory: Optional[Callable[[], Any]] = None,
                 **kwargs: Any) -> None:
        super().__init__()
        self.method = method
        self._llm_factory = llm_factory
        self._image_gen_factory = image_gen_factory
        self._vlm_factory = vlm_factory
        self.oracle = OracleState()
        self.reps: Dict[str, Any] = {}
        self._last_event: Optional[Event] = None

    async def init(self) -> None:
        if self._llm_factory is None:
            from examples.west_world_test.adapters.dashscope_clients import (
                build_llm, build_image_gen, build_vlm)
            self._llm_factory = build_llm
            self._image_gen_factory = build_image_gen
            self._vlm_factory = build_vlm
        if self.method in ("text", "both"):
            self.reps["text"] = TextRepresentation(self._llm_factory())
        if self.method in ("image", "both"):
            self.reps["image"] = ImageRepresentation(
                self._llm_factory(), self._image_gen_factory(), self._vlm_factory())

    async def apply_event(self, event_dict: Dict[str, Any]) -> None:
        event = Event.from_dict(event_dict)
        self._last_event = event
        self.oracle.apply(event)
        for rep in self.reps.values():
            rep.update(event)

    async def probe(self, probe_dict: Dict[str, Any]) -> Dict[str, Any]:
        probe = Probe.from_dict(probe_dict)
        truth = self.oracle.answer(probe)
        relevant = bool(self._last_event and _is_relevant(probe, self._last_event))
        answers: Dict[str, Any] = {}
        for name, rep in self.reps.items():
            raw = rep.answer(probe)
            answers[name] = {
                "answer": raw,
                "norm": normalize(raw, probe.answer_type),
                "correct": is_correct(raw, truth, probe.answer_type),
            }
        return {"probe_id": probe.id, "truth": truth,
                "had_relevant_event": relevant, "answers": answers}

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_scene_plugin.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/scene examples/west_world_test/tests/test_scene_plugin.py
git commit -m "feat(west-world): add SceneRecorderPlugin wrapping experiment core as scene env component"
```

---

### Task 12: ScriptedPlanPlugin（决定性 trajectory）

**Files:**
- Create: `examples/west_world_test/plugins/__init__.py`、`.../plugins/agent/__init__.py`、`.../plugins/agent/plan/__init__.py`（均空）
- Create: `examples/west_world_test/plugins/agent/plan/ScriptedPlanPlugin.py`
- Test: `examples/west_world_test/tests/test_scripted_plan.py`

**说明：** 继承内核 `PlanPlugin`（`mas/agent/base/plugin_base.py`），从 `script.jsonl` 取「该 agent 在该 tick 的动作」，写入 state 供 invoke 执行，替代 LLM 规划，保证两次运行 trajectory 完全一致。

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_scripted_plan.py
from examples.west_world_test.core.schema import Event
from examples.west_world_test.plugins.agent.plan.ScriptedPlanPlugin import ScriptedPlanPlugin


def test_action_for_returns_matching_event():
    events = [
        Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}),
        Event.from_dict({"id": "e2", "tick": 2, "actor": "黑衣人", "action": "pick_up_photo", "target": "photo", "visibility": "hidden"}),
    ]
    plan = ScriptedPlanPlugin(events=events, agent_id="黑衣人")
    assert plan.action_for(2) == events[1]
    assert plan.action_for(1) is None   # tick1 不是黑衣人
    assert plan.action_for(5) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_scripted_plan.py -v`
Expected: FAIL（`ModuleNotFoundError: ...ScriptedPlanPlugin`）

- [ ] **Step 3: Write minimal implementation**

```python
# examples/west_world_test/plugins/agent/plan/ScriptedPlanPlugin.py
"""从固定脚本取动作的 PlanPlugin，保证 trajectory 决定性可复现。"""
from __future__ import annotations

from typing import List, Optional

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin

from examples.west_world_test.core.schema import Event


class ScriptedPlanPlugin(PlanPlugin):
    def __init__(self, events: Optional[List[Event]] = None, agent_id: str = "", **kwargs) -> None:
        super().__init__()
        self._events = events or []
        self.agent_id = agent_id

    def action_for(self, tick: int) -> Optional[Event]:
        for e in self._events:
            if e.tick == tick and e.actor == self.agent_id:
                return e
        return None

    async def init(self) -> None:
        # 真实接入时从 component 取 agent_id；脚本由 registry/run_test 注入
        if not self.agent_id and getattr(self, "_component", None) is not None:
            self.agent_id = self._component.agent.agent_id

    async def execute(self, current_tick: int) -> None:
        event = self.action_for(current_tick)
        state = self._component.agent.get_component("state").get_plugin()
        if event is None:
            await state.set_state("current_action", None)
            return
        await state.set_state("current_action", {
            "action": event.action, "target": event.target,
            "visibility": event.visibility, "event_id": event.id,
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_scripted_plan.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add examples/west_world_test/plugins examples/west_world_test/tests/test_scripted_plan.py
git commit -m "feat(west-world): add ScriptedPlanPlugin for deterministic trajectory"
```

---

### Task 13: registry + configs

**Files:**
- Create: `examples/west_world_test/registry.py`
- Create: `examples/west_world_test/configs/*.yaml`（7 个）
- Test: `examples/west_world_test/tests/test_registry.py`

**说明：** 参考 `examples/story_of_the_stone/registry.py` 与其 `configs/`，裁剪到单地点；环境组件用 `get_or_create_component_class("scene")` 动态生成 `SceneComponent` 并注册，插件 map 注册 `SceneRecorderPlugin` 与 `ScriptedPlanPlugin`。

- [ ] **Step 1: Write the failing test**

```python
# examples/west_world_test/tests/test_registry.py
def test_registry_exposes_scene_and_scripted_plan():
    from examples.west_world_test.registry import RESOURCES_MAPS
    assert "scene" in RESOURCES_MAPS["environment_components"]
    assert "SceneRecorderPlugin" in RESOURCES_MAPS["environment_plugins"]
    assert "ScriptedPlanPlugin" in RESOURCES_MAPS["agent_plugins"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_registry.py -v`
Expected: FAIL（`ModuleNotFoundError: ...registry`）

- [ ] **Step 3: Write registry**

```python
# examples/west_world_test/registry.py
"""west_world_test 资源注册表（单地点最小配置）。"""
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider
from agentkernel_distributed.mas.system.components import Messager, Recorder, Timer
from agentkernel_distributed.mas.agent.components import (
    ProfileComponent, PlanComponent, PerceiveComponent, InvokeComponent, ReflectComponent)
from agentkernel_distributed.mas.environment.components import get_or_create_component_class
from agentkernel_distributed.toolkit.storages import RedisKVAdapter

from examples.story_of_the_stone.BasicController import BasicController
from examples.story_of_the_stone.BasicPodManager import BasicPodManager
from examples.story_of_the_stone.plugins.agent.perceive.BasicPerceivePlugin import BasicPerceivePlugin
from examples.story_of_the_stone.plugins.agent.profile.BasicProfliePlugin import BasicProfilePlugin
from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.story_of_the_stone.plugins.agent.state.component import BasicStateComponent
from examples.story_of_the_stone.plugins.agent.invoke.BasicInvokePlugin import BasicInvokePlugin
from examples.story_of_the_stone.plugins.agent.reflect.BasicReflectPlugin import BasicReflectPlugin

from examples.west_world_test.plugins.agent.plan.ScriptedPlanPlugin import ScriptedPlanPlugin
from examples.west_world_test.scene.SceneRecorderPlugin import SceneRecorderPlugin

SceneComponent = get_or_create_component_class("scene")

agent_plugin_calss_map = {
    "BasicPerceivePlugin": BasicPerceivePlugin,
    "BasicProfilePlugin": BasicProfilePlugin,
    "BasicStatePlugin": BasicStatePlugin,
    "ScriptedPlanPlugin": ScriptedPlanPlugin,
    "BasicInvokePlugin": BasicInvokePlugin,
    "BasicReflectPlugin": BasicReflectPlugin,
}
agent_component_class_map = {
    "profile": ProfileComponent, "state": BasicStateComponent, "plan": PlanComponent,
    "perceive": PerceiveComponent, "reflect": ReflectComponent, "invoke": InvokeComponent,
}
environment_component_class_map = {"scene": SceneComponent}
environment_plugin_class_map = {"SceneRecorderPlugin": SceneRecorderPlugin}
model_class_map = {"OpenAIProvider": OpenAIProvider}
system_component_class_map = {"messager": Messager, "recorder": Recorder, "timer": Timer}
adapter_class_map = {"RedisKVAdapter": RedisKVAdapter}

RESOURCES_MAPS = {
    "agent_components": agent_component_class_map,
    "agent_plugins": agent_plugin_calss_map,
    "action_components": {},
    "action_plugins": {},
    "environment_components": environment_component_class_map,
    "environment_plugins": environment_plugin_class_map,
    "system_components": system_component_class_map,
    "models": model_class_map,
    "adapters": adapter_class_map,
    "controller": BasicController,
    "pod_manager": BasicPodManager,
}
```

- [ ] **Step 4: Create config files**

`configs/models_config.yaml`（沿用 DashScope）:
```yaml
- name: OpenAIProvider
  model: qwen-plus
  api_key: sk-替换为你的key
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  capabilities:
  - chat
```

`configs/environment_config.yaml`:
```yaml
name: WestWorldEnvironment
components:
  scene:
    plugin:
      SceneRecorderPlugin:
        adapters: {}
        method: both
```

`configs/agents_config.yaml`:
```yaml
templates:
  - name: "ScriptedAgent"
    component_order: ["plan", "invoke", "state"]
    components:
      profile:
        plugin:
          BasicProfilePlugin:
            adapters: {redis: "RedisKVAdapter"}
            profile_data: "agent_profiles"
      state:
        plugin:
          BasicStatePlugin:
            adapters: {adapter: "RedisKVAdapter"}
            state_data: "agent_states"
      plan:
        plugin:
          ScriptedPlanPlugin:
            adapters: {}
      invoke:
        plugin:
          BasicInvokePlugin:
            adapters: {redis: "RedisKVAdapter"}
```

`configs/system_config.yaml`:
```yaml
name: WestWorldSystem
components:
  messager:
    allow_self_messages: false
    block_empty_content: true
    max_content_length: 2000
    blocked_pairs: []
    blocked_senders: []
    blocked_receivers: []
    blocked_keywords: []
    blocked_regex: []
  timer:
    start_tick: 0
    timeout_ticks: 5
```

`configs/db_config.yaml`（复制 sots 的同名文件内容）、`configs/scene_config.yaml`:
```yaml
# 图像模型通过环境变量配置（见 adapters/dashscope_clients.py）：
# DASHSCOPE_API_KEY / WW_TEXT_MODEL / WW_VLM_MODEL / WW_IMAGE_MODEL
method: both
```

`configs/simulation_config.yaml`:
```yaml
simulation:
  pod_size: 3
  init_batch_size: 3
  max_ticks: 8
configs:
  environment: "environment_config.yaml"
  agent_templates: "agents_config.yaml"
  system: "system_config.yaml"
  database: "db_config.yaml"
  models: "models_config.yaml"
data:
  agent_profiles: "data/agents/profiles.jsonl"
  agent_states: "data/agents/states.jsonl"
api_server:
  host: "0.0.0.0"
  port: 8010
```

并 `touch examples/west_world_test/data/agents/states.jsonl`（空文件，与 sots 一致）。

- [ ] **Step 5: Run test & commit**

Run: `PYTHONPATH=packages/agentkernel-distributed:. pytest examples/west_world_test/tests/test_registry.py -v`
Expected: PASS

```bash
git add examples/west_world_test/registry.py examples/west_world_test/configs examples/west_world_test/data/agents/states.jsonl examples/west_world_test/tests/test_registry.py
git commit -m "feat(west-world): add registry and single-location configs"
```

---

### Task 14: run_test.py — 端到端轻量 runner

**Files:**
- Create: `examples/west_world_test/run_test.py`
- Test: 手动端到端（需 Ray + Redis）。

**说明：** 参考 `examples/story_of_the_stone/run_simulation.py` 的 Step1（Ray init）+ Step2（Builder.init），但**去掉前端/分支/branching** 逻辑。每 tick：跑 system tick → 从各 agent state 收集 `current_action` → 调 `environment.run("scene","apply_event", ...)` → 对每条 probe 调 `environment.run("scene","probe", ...)` → 写 record。结束出 summary 与 `results.jsonl`。

- [ ] **Step 1: Write the runner**

```python
# examples/west_world_test/run_test.py
"""west_world_test 轻量 runner：复用 distributed 内核 Builder，去掉前端/分支。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os

import ray

from agentkernel_distributed.mas.builder import Builder
from examples.west_world_test.registry import RESOURCES_MAPS
from examples.west_world_test.plugins.agent.plan.ScriptedPlanPlugin import ScriptedPlanPlugin
from examples.west_world_test.core.schema import load_events, load_probes

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(PROJECT_PATH, "results.jsonl"))
    args = ap.parse_args()

    events = load_events(os.path.join(PROJECT_PATH, "data", "script.jsonl"))
    probes = load_probes(os.path.join(PROJECT_PATH, "data", "probes.jsonl"))
    # 把脚本注入 ScriptedPlanPlugin（按 agent 过滤在 plugin 内做）
    ScriptedPlanPlugin._SCRIPT_EVENTS = events  # 由 plugin.init 读取（见说明）

    ray.init()
    builder = Builder(project_path=PROJECT_PATH, resource_maps=RESOURCES_MAPS)
    pod_manager, system = await builder.init()

    max_tick = builder.config.simulation.max_ticks
    records = []
    for tick in range(1, max_tick + 1):
        await pod_manager.tick.remote(tick)                      # 推进一个 tick
        ev = next((e for e in events if e.tick == tick), None)
        if ev is not None:
            await system.run("environment", "scene", "apply_event", ev.__dict__) \
                if False else None
            # 通过 environment 代理调用 scene 组件
            await builder.environment.run("scene", "apply_event", ev.__dict__)
        for p in probes:
            res = await builder.environment.run("scene", "probe", p.__dict__)
            res["tick"] = tick
            records.append(res)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(f"wrote {len(records)} probe records to {args.out}")
    ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

> **实现期校准点（执行者注意）：** `pod_manager.tick` 与 `builder.environment` 的确切方法名/属性，需对照 `agentkernel_distributed/mas/builder.py` 与 `mas/pod/pod_manager.py`、`mas/environment/environment.py` 核对（`Environment.run(component, method, *args)` 已确认存在）。若 Builder 不直接暴露 `environment`，则从 `pod_manager` 获取环境句柄。`ScriptedPlanPlugin` 读取脚本的方式（类变量 vs config 注入）按内核插件实例化路径择一落地，并回填到 Task 12 的 `init`。

- [ ] **Step 2: 端到端手动运行（需 Ray + Redis + 密钥）**

Run:
```bash
# 先确保 redis-server 运行；export DASHSCOPE_API_KEY=...
cd OpenStory
PYTHONPATH=packages/agentkernel-distributed:. python -m examples.west_world_test.run_test
```
Expected: 无异常跑完 8 个 tick，生成 `results.jsonl`，每条含 `truth` 与 `answers.{text,image}.correct`。

- [ ] **Step 3: 出图与对照**

Run: `PYTHONPATH=packages/agentkernel-distributed:. python -m examples.west_world_test.eval.plot`
Expected: 生成 `drift_curve.png`，对比 text vs image 的逐 tick 准确率。

- [ ] **Step 4: Commit**

```bash
git add examples/west_world_test/run_test.py
git commit -m "feat(west-world): add lightweight end-to-end runner over distributed kernel"
```

---

## 自查（spec 覆盖核对）

- 受控变量「读出介质」：Task 6/7 隔离实现（更新逻辑共用 `_UPDATE_PROMPT`）。✅
- Oracle 真值层：Task 2/3。✅
- 三类指标（一致性/防漂移、感知准确率、响应正确性）：Task 8（accuracy/drift/contradiction）+ Task 9（`had_relevant_event` 支撑响应正确性）+ 可见性正确性（probe q8 + oracle visibility）。✅
- 固定脚本 trajectory：Task 4 数据 + Task 12 ScriptedPlanPlugin。✅
- 人工预写探针集：Task 4。✅
- 文生图+VLM：Task 7 + Task 10 适配。✅
- config 一行切换 text/image/both：Task 11 `method` + Task 13 `environment_config.yaml`。✅
- 复用完整内核（GenericPlugin/Builder）：Task 11/13/14。✅
- 产出 results.jsonl + 对照表 + 漂移曲线：Task 9/10/14。✅
- 非目标（监管者/root/觉醒/多地点/前端/记忆压缩）：均未纳入。✅

**已知校准点**：Task 14 的 `pod_manager.tick` / `builder.environment` 精确 API、以及 ScriptedPlanPlugin 脚本注入路径，需在执行期对照内核源码最终敲定（已在文中标注）。
