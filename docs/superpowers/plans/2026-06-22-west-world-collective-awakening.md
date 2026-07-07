# West World 群体意识觉醒相变 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 west_world_test 补一组博弈机制（觉醒自累积、监管者有限产能、压制反噬、残痕棘轮、碎片传染、群体指标），让「群体意识觉醒」变成可观测的相变。

**Architecture:** 全部改动落在现有文件。觉醒数值逻辑集中在 `awakening/awakening_engine.py` + `awakening/trigger_gate.py`（纯函数，可无 Ray 单测）；行为接入在 reflect/plan/overseer 三个插件；指标/绘图在 `experiments/`。不动五段生命周期、pod barrier 结构、recorder、worldmap。

**Tech Stack:** Python 3.11、pytest、sentence-transformers（bge-small-zh-v1.5，仅 gate 用）、Ray/Redis（仅 E2E）、matplotlib（绘图）。

## Global Constraints

- 单调性不变量：除 `overseer_reset` 外所有觉醒源只增。新增 `rumination` / `witness` 必须加入 `awakening_engine._MONOTONIC_SOURCES`。
- 觉醒判定门 embedding 模型固定 `BAAI/bge-small-zh-v1.5`，独立于 agent LLM（受控变量），不要换成 LLM 判定。
- 所有新行为受 env 开关控制，默认值与现状兼容：`WW_OVERSEER_CAPACITY` 默认 `inf`（=现状全量）、`WW_AWAKEN_DELTA_WITNESS` 默认 6、O3 通过设 `WW_AWAKEN_DELTA_WITNESS=0` 关闭。
- `WW_AWAKEN_ENABLED=false` / `WW_OVERSEER_ENABLED=false` 时对应机制整体短路（沿用现有判断）。
- guest 类型 agent 不参与觉醒，调用方在 apply 前已过滤；新增逻辑同样只对 host 生效。
- 单元测试不依赖 Ray/Redis/LLM；涉及 embedding 的测试可 mock 或标 skip。实验结论是数据观察，不写成硬断言。
- 测试运行：`PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests -q`（在仓库根 `OpenStory/` 下执行）。
- 每个 task 完成后回写 `examples/west_world_test/DEVELOPMENT_NOTES.md`（已完成/待办），保持精简。

---

### Task 1: 觉醒引擎 — 新源、连续门控缩放、棘轮（M1/M2/L1/O3 数值层）

**Files:**
- Modify: `examples/west_world_test/awakening/awakening_engine.py`
- Test: `examples/west_world_test/tests/test_awakening_engine.py`

**Interfaces:**
- Produces:
  - `_MONOTONIC_SOURCES` 增加 `"rumination"`, `"witness"`。
  - `apply(state, source, detail, tick, *, score=None, level=None, tau=None, suppress_count=1) -> int`（新增 `tau`, `suppress_count` 关键字参数；旧调用保持兼容）。
  - 新 delta 源：`rumination`（env `WW_AWAKEN_DELTA_RUMINATION`，默认 2）、`witness`（env `WW_AWAKEN_DELTA_WITNESS`，默认 6；`level=="decommission"` 时乘 `WW_AWAKEN_WITNESS_DECOMM_MULT`，默认 1.5）。
  - `trigger` 源当传入 `score` 与 `tau` 时按 `(score-tau)/(1-tau)` 缩放（M2）。
  - `residue_crack` 源 delta = base · `(1 + WW_AWAKEN_RESIDUE_RATCHET·(suppress_count-1))`（默认 ratchet 0.5）。

- [ ] **Step 1: 写失败测试（新源 + 缩放 + 棘轮）**

在 `tests/test_awakening_engine.py` 末尾追加：

```python
def test_rumination_is_monotonic_and_configurable(monkeypatch):
    from examples.west_world_test.awakening import awakening_engine as ae
    monkeypatch.setenv("WW_AWAKEN_DELTA_RUMINATION", "3")
    state = {"awakening": 30, "awakening_sources": []}
    delta = ae.apply(state, "rumination", "反刍", tick=5)
    assert delta == 3
    assert state["awakening"] == 33
    assert "rumination" in ae._MONOTONIC_SOURCES


def test_witness_delta_and_decommission_multiplier(monkeypatch):
    from examples.west_world_test.awakening import awakening_engine as ae
    monkeypatch.setenv("WW_AWAKEN_DELTA_WITNESS", "6")
    monkeypatch.setenv("WW_AWAKEN_WITNESS_DECOMM_MULT", "1.5")
    s1 = {"awakening": 10, "awakening_sources": []}
    assert ae.apply(s1, "witness", "目睹 reset", tick=1) == 6
    s2 = {"awakening": 10, "awakening_sources": []}
    assert ae.apply(s2, "witness", "目睹报废", tick=1, level="decommission") == 9
    assert "witness" in ae._MONOTONIC_SOURCES


def test_trigger_delta_scales_with_score(monkeypatch):
    from examples.west_world_test.awakening import awakening_engine as ae
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "12")
    # score 恰在门限 → delta≈0
    s_low = {"awakening": 0, "awakening_sources": []}
    d_low = ae.apply(s_low, "trigger", "x", tick=1, score=0.45, level="high", tau=0.45)
    assert d_low == 0
    # score=1.0 → 满额
    s_hi = {"awakening": 0, "awakening_sources": []}
    d_hi = ae.apply(s_hi, "trigger", "x", tick=1, score=1.0, level="high", tau=0.45)
    assert d_hi == 12
    # 中间值单调
    s_mid = {"awakening": 0, "awakening_sources": []}
    d_mid = ae.apply(s_mid, "trigger", "x", tick=1, score=0.725, level="high", tau=0.45)
    assert 0 < d_mid < 12


def test_trigger_without_tau_keeps_base_delta(monkeypatch):
    # 旧调用（不传 tau）保持原行为
    from examples.west_world_test.awakening import awakening_engine as ae
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_MID", "8")
    s = {"awakening": 0, "awakening_sources": []}
    assert ae.apply(s, "trigger", "x", tick=1, score=0.9) == 8


def test_residue_crack_ratchet(monkeypatch):
    from examples.west_world_test.awakening import awakening_engine as ae
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    monkeypatch.setenv("WW_AWAKEN_RESIDUE_RATCHET", "0.5")
    s1 = {"awakening": 30, "awakening_sources": []}
    assert ae.apply(s1, "residue_crack", "x", tick=1, suppress_count=1) == 5
    s2 = {"awakening": 30, "awakening_sources": []}
    assert ae.apply(s2, "residue_crack", "x", tick=1, suppress_count=3) == 10  # 5*(1+0.5*2)
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_awakening_engine.py -q -k "rumination or witness or trigger_delta or residue_crack or trigger_without"`
Expected: FAIL（`apply()` 不接受 `tau`/`suppress_count`，新源返回 0）

- [ ] **Step 3: 实现引擎改动**

把 `awakening_engine.py` 顶部白名单改为：

```python
_MONOTONIC_SOURCES = frozenset({
    "trigger", "uncanny", "mismatch", "contagion", "residue_crack",
    "rumination", "witness",
})
```

`_delta_for` 改为接受可选 `score`/`tau`/`suppress_count`：

```python
def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _delta_for(
    source: str,
    level: Optional[str] = None,
    *,
    score: Optional[float] = None,
    tau: Optional[float] = None,
    suppress_count: int = 1,
) -> int:
    if source == "trigger":
        base = _env_int("WW_AWAKEN_DELTA_TRIGGER_HIGH", 15) if level == "high" \
            else _env_int("WW_AWAKEN_DELTA_TRIGGER_MID", 8)
        if score is not None and tau is not None and tau < 1.0:
            frac = _clamp01((score - tau) / (1.0 - tau))
            scale = float(os.environ.get("WW_AWAKEN_TRIGGER_SCALE", "1.0"))
            return int(round(base * frac * scale))
        return base
    if source == "uncanny":
        return _env_int("WW_AWAKEN_DELTA_UNCANNY", 5)
    if source == "mismatch":
        return _env_int("WW_AWAKEN_DELTA_MISMATCH", 8)
    if source == "contagion":
        return _env_int("WW_AWAKEN_DELTA_CONTAGION", 10)
    if source == "residue_crack":
        base = _env_int("WW_AWAKEN_DELTA_UNCANNY", 5)
        ratchet = float(os.environ.get("WW_AWAKEN_RESIDUE_RATCHET", "0.5"))
        return int(round(base * (1.0 + ratchet * max(0, suppress_count - 1))))
    if source == "rumination":
        return _env_int("WW_AWAKEN_DELTA_RUMINATION", 2)
    if source == "witness":
        base = _env_int("WW_AWAKEN_DELTA_WITNESS", 6)
        if level == "decommission":
            mult = float(os.environ.get("WW_AWAKEN_WITNESS_DECOMM_MULT", "1.5"))
            return int(round(base * mult))
        return base
    return 0
```

`apply()` 签名与 delta 计算分支改为：

```python
def apply(
    state: Dict[str, Any],
    source: str,
    detail: str,
    tick: int,
    *,
    score: Optional[float] = None,
    level: Optional[str] = None,
    tau: Optional[float] = None,
    suppress_count: int = 1,
) -> int:
    if os.environ.get("WW_AWAKEN_ENABLED", "true").lower() in ("false", "0"):
        return 0

    current = int(state.get("awakening", 0))

    if source == "overseer_reset":
        if os.environ.get("WW_OVERSEER_ENABLED", "true").lower() in ("false", "0"):
            return 0
        target = _reset_target(current)
        actual = target - current
        if actual == 0:
            return 0
        new_val = max(0, min(100, current + actual))
        actual = new_val - current
    else:
        delta = _delta_for(source, level, score=score, tau=tau, suppress_count=suppress_count)
        if delta <= 0:
            return 0
        new_val = min(100, current + delta)
        actual = new_val - current
        if actual <= 0:
            return 0

    state["awakening"] = new_val
    # ...（下面 sources.append 段保持不变）
```

（`sources.append` 段、`_reset_target` 不变。）

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_awakening_engine.py -q`
Expected: PASS（含原有用例回归）

- [ ] **Step 5: 提交**

```bash
git add examples/west_world_test/awakening/awakening_engine.py examples/west_world_test/tests/test_awakening_engine.py
git commit -m "feat(west-world): 觉醒引擎新增 rumination/witness 源 + 触发连续门控 + 残痕棘轮"
```

---

### Task 2: 触发门动态阈值 + reflect 接入自累积（M1/M2 行为层）

**Files:**
- Modify: `examples/west_world_test/awakening/trigger_gate.py`
- Modify: `examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py:282-346`（`_check_awakening_gate`）
- Test: `examples/west_world_test/tests/test_trigger_gate.py`（新建或追加）、`examples/west_world_test/tests/test_awakening_gate_behavior.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `awakening_engine.apply(..., score=, tau=)`。
- Produces:
  - `trigger_gate.effective_tau(awakening: int, base_tau: Optional[float]=None) -> float`（纯函数）。
  - `_check_awakening_gate` 内：trigger 命中用 `effective_tau` 作 match 阈值并把 `tau` 传入 `apply`；对 awakening≥reverie 阈值的 host 每 tick 施加一次 `rumination`。

- [ ] **Step 1: 写 effective_tau 失败测试**

新建 `tests/test_trigger_gate.py`（若已存在则追加，注意不要 import SentenceTransformer 类本体——只测纯函数）：

```python
def test_effective_tau_decreases_with_awakening(monkeypatch):
    from examples.west_world_test.awakening.trigger_gate import effective_tau
    monkeypatch.setenv("WW_AWAKEN_TRIGGER_TAU", "0.55")
    monkeypatch.setenv("WW_AWAKEN_TAU_DECAY", "0.15")
    monkeypatch.setenv("WW_AWAKEN_TAU_FLOOR", "0.30")
    assert effective_tau(0) == 0.55
    assert effective_tau(100) == 0.40  # 0.55 - 0.15
    # 钳到 floor
    monkeypatch.setenv("WW_AWAKEN_TAU_DECAY", "0.40")
    assert effective_tau(100) == 0.30
    # 单调下降
    monkeypatch.setenv("WW_AWAKEN_TAU_DECAY", "0.15")
    assert effective_tau(0) > effective_tau(50) > effective_tau(100)
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_trigger_gate.py -q -k effective_tau`
Expected: FAIL（`effective_tau` 不存在）

- [ ] **Step 3: 实现 effective_tau**

在 `trigger_gate.py` 顶部（`_cosine` 之后）加：

```python
def effective_tau(awakening: int, base_tau: Optional[float] = None) -> float:
    """触发门有效阈值：越醒越敏感（线性下降，钳到下限）。"""
    if base_tau is None:
        base_tau = float(os.environ.get("WW_AWAKEN_TRIGGER_TAU", "0.55"))
    decay = float(os.environ.get("WW_AWAKEN_TAU_DECAY", "0.15"))
    floor = float(os.environ.get("WW_AWAKEN_TAU_FLOOR", "0.30"))
    return max(floor, base_tau - decay * (awakening / 100.0))
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_trigger_gate.py -q -k effective_tau`
Expected: PASS

- [ ] **Step 5: 写 reflect 接入的失败测试（rumination + 动态 tau）**

新建 `tests/test_awakening_gate_behavior.py`。用一个轻量假 state_plugin + 假 agent，验证 `_check_awakening_gate` 对 reverie+ 的 host 施加 rumination：

```python
import pytest
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin


class FakeState:
    def __init__(self, store): self.store = store
    async def get_state(self, k): return self.store.get(k)
    async def set_state(self, k, v): self.store[k] = v


class FakeProfilePlugin:
    def __init__(self, t): self._t = t
    def get_agent_profile(self): return {"agent_type": self._t}


class FakeComponent:
    def __init__(self, t): self._p = FakeProfilePlugin(t)
    def get_plugin(self): return self._p


class FakeAgent:
    agent_id = "dolores"
    def __init__(self, t): self._t = t
    def get_component(self, name): return FakeComponent(self._t)


@pytest.mark.asyncio
async def test_rumination_applied_above_reverie(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_RUMINATION", "2")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    plugin = WestWorldReflectPlugin()
    plugin.agent = FakeAgent("host")
    store = {"awakening": 30, "awakening_sources": [], "percept": {}, "feedback": "", "incoming_dialogue": []}
    await plugin._check_awakening_gate(FakeState(store), current_tick=7)
    assert store["awakening"] == 32
    assert any(s["source"] == "rumination" for s in store["awakening_sources"])


@pytest.mark.asyncio
async def test_no_rumination_below_reverie(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    plugin = WestWorldReflectPlugin()
    plugin.agent = FakeAgent("host")
    store = {"awakening": 10, "awakening_sources": [], "percept": {}, "feedback": "", "incoming_dialogue": []}
    await plugin._check_awakening_gate(FakeState(store), current_tick=7)
    assert store["awakening"] == 10
```

- [ ] **Step 6: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_awakening_gate_behavior.py -q`
Expected: FAIL（当前无 rumination 逻辑，awakening 不变）

- [ ] **Step 7: 实现 reflect 接入**

在 `WestWorldReflectPlugin._check_awakening_gate` 中：
1. trigger 匹配段把固定 tau 改成 `effective_tau`，并把 tau 传给 `apply`：

```python
        if incoming:
            try:
                from examples.west_world_test.awakening.trigger_gate import get_trigger_gate, effective_tau
                gate = get_trigger_gate()
                current_aw = full_state["awakening"]
                tau_eff = effective_tau(current_aw)
                for utterance in incoming:
                    if not utterance:
                        continue
                    hits = gate.match(utterance, current_awakening=current_aw, tau=tau_eff)
                    for hit in hits:
                        awakening_engine.apply(
                            full_state, "trigger",
                            f"触发词命中：{hit['phrase'][:40]}",
                            current_tick,
                            score=hit["score"], level=hit["level"], tau=tau_eff,
                        )
            except Exception as exc:
                logger.debug("[%s] trigger gate 未加载: %s", self.agent.agent_id, exc)
```

2. 在「写回 state」之前，加 rumination（reverie 阈值=stages 第一档）：

```python
        # 3. 自累积反刍：进入梦呓阶段后每 tick 微小上漂
        reverie_threshold = int(os.environ.get("WW_AWAKEN_STAGES", "25,50,75,90").split(",")[0])
        if full_state["awakening"] >= reverie_threshold:
            awakening_engine.apply(
                full_state, "rumination", "持续反刍", current_tick,
            )
```

- [ ] **Step 8: 运行确认通过 + 全量回归**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_awakening_gate_behavior.py examples/west_world_test/tests/test_trigger_gate.py -q`
Expected: PASS

- [ ] **Step 9: 提交**

```bash
git add examples/west_world_test/awakening/trigger_gate.py examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py examples/west_world_test/tests/test_trigger_gate.py examples/west_world_test/tests/test_awakening_gate_behavior.py
git commit -m "feat(west-world): 触发门动态阈值 + reflect 自累积反刍接入"
```

---

### Task 3: 残痕棘轮 — suppress_count 计数（L1 数据层）

**Files:**
- Modify: `examples/west_world_test/awakening/overseer_reset.py:15-41`（`select_blur_candidates`）
- Modify: `examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py:241-280`（`_check_residue`）、`:176-239`（`_blur` 写 suppressed 时带 count）
- Test: `examples/west_world_test/tests/test_overseer_reset.py`、`examples/west_world_test/tests/test_residue_ratchet.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `apply(..., suppress_count=)`。
- Produces: `suppressed_memories` 每条带 `suppress_count`（首次=1，重复压制递增）；`_check_residue` 复燃时把该值传入 `apply`。

- [ ] **Step 1: 写 select_blur_candidates 棘轮失败测试**

在 `tests/test_overseer_reset.py` 追加：

```python
def test_select_blur_candidates_increments_suppress_count():
    from examples.west_world_test.awakening.overseer_reset import select_blur_candidates
    long_mems = [{"content": "我看到了血和死亡"}]
    # 首次压制
    to_blur, sup = select_blur_candidates(long_mems, [], awakening=20, tick=1)
    assert len(sup) == 1
    assert sup[0]["suppress_count"] == 1
    # 同一条再次压制 → count 递增，不新增条目
    to_blur2, sup2 = select_blur_candidates(long_mems, sup, awakening=20, tick=5)
    assert len(sup2) == 1
    assert sup2[0]["suppress_count"] == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_reset.py -q -k suppress_count`
Expected: FAIL（无 `suppress_count` 字段）

- [ ] **Step 3: 实现 select_blur_candidates 计数**

把 `overseer_reset.py::select_blur_candidates` 改为对已存在条目递增、新条目初始化为 1：

```python
    existing = {s["text"]: s for s in suppressed}
    new_suppressed = list(suppressed)
    to_blur: List[Any] = []
    for entry in long_mems:
        text = entry.get("content", str(entry)) if isinstance(entry, dict) else str(entry)
        if classify_disturbance(text):
            to_blur.append(entry)
            if text in existing:
                existing[text]["suppress_count"] = int(existing[text].get("suppress_count", 1)) + 1
            else:
                rec = {"tick": tick, "text": text, "awakening_at_blur": awakening, "suppress_count": 1}
                new_suppressed.append(rec)
                existing[text] = rec
    return to_blur, new_suppressed
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_reset.py -q`
Expected: PASS

- [ ] **Step 5: 写 _check_residue 棘轮失败测试**

新建 `tests/test_residue_ratchet.py`（复用 Task 2 的 FakeState；这里直接内联一个）：

```python
import pytest
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin


class FakeState:
    def __init__(self, store): self.store = store
    async def get_state(self, k): return self.store.get(k)
    async def set_state(self, k, v): self.store[k] = v
    async def add_long_term_memory(self, t):
        self.store.setdefault("long_term_memory", []).append({"content": t})


class FakeAgent:
    agent_id = "maeve"
    def get_component(self, name): raise AssertionError("not needed")


@pytest.mark.asyncio
async def test_residue_crack_uses_suppress_count(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    monkeypatch.setenv("WW_AWAKEN_RESIDUE_RATCHET", "0.5")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    plugin = WestWorldReflectPlugin()
    plugin.agent = FakeAgent()
    store = {
        "awakening": 40,
        "awakening_sources": [],
        "suppressed_memories": [
            {"tick": 1, "text": "血", "awakening_at_blur": 20, "suppress_count": 3},
        ],
    }
    await plugin._check_residue(FakeState(store), current_tick=10)
    # base 5 * (1 + 0.5*2) = 10
    assert store["awakening"] == 50
    assert store["suppressed_memories"] == []
```

- [ ] **Step 6: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_residue_ratchet.py -q`
Expected: FAIL（当前 `_check_residue` 调 apply 不传 suppress_count，delta=5 → awakening=45）

- [ ] **Step 7: 实现 _check_residue 传 count + _blur 写 count**

在 `_check_residue` 的 residue_crack 循环改为按碎片的 `suppress_count` 传入：

```python
        for fragment in to_reflux:
            awakening_engine.apply(
                full_state, "residue_crack",
                f"碎片回流：{fragment['text'][:40]}",
                current_tick,
                suppress_count=int(fragment.get("suppress_count", 1)),
            )
```

在 `_blur` 写 suppressed 处补 `suppress_count`（保持正常反思路径与 reset 路径一致）：

```python
        suppressed.append({
            "tick": current_tick, "text": text,
            "awakening_at_blur": awakening, "suppress_count": 1,
        })
```

- [ ] **Step 8: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_residue_ratchet.py examples/west_world_test/tests/test_overseer_reset.py -q`
Expected: PASS

- [ ] **Step 9: 提交**

```bash
git add examples/west_world_test/awakening/overseer_reset.py examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py examples/west_world_test/tests/test_overseer_reset.py examples/west_world_test/tests/test_residue_ratchet.py
git commit -m "feat(west-world): 残痕棘轮 suppress_count，复燃 delta 随压制次数放大"
```

---

### Task 4: 监管者有限产能 K（O2 — 相变控制参数）

**Files:**
- Modify: `examples/west_world_test/plugins/environment/overseer/OverseerPlugin.py:65-106`（`execute`）
- Test: `examples/west_world_test/tests/test_overseer_capacity.py`（新建）

**Interfaces:**
- Produces:
  - `OverseerPlugin._rank_suspects(suspects) -> List[str]`：纯函数排序（主键 awakening 降序，次 gate_hits 数降序，再 agent_id 升序保稳定）。
  - `execute` 在 judge/intervene 前按 `WW_OVERSEER_CAPACITY`（默认 inf）截断到前 K 个。

- [ ] **Step 1: 写排序 + 截断失败测试**

新建 `tests/test_overseer_capacity.py`：

```python
from examples.west_world_test.plugins.environment.overseer.OverseerPlugin import OverseerPlugin


def test_rank_suspects_orders_by_awakening_then_hits():
    ov = OverseerPlugin()
    suspects = {
        "a": (40, ["x"], [{"phrase": "p"}]),
        "b": (80, ["y"], []),
        "c": (40, ["z"], [{"phrase": "p"}, {"phrase": "q"}]),
    }
    ranked = ov._rank_suspects(suspects)
    assert ranked[0] == "b"          # 觉醒度最高
    assert ranked[1] == "c"          # 觉醒度并列 40，gate_hits 多者优先
    assert ranked[2] == "a"


def test_capacity_truncates(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_CAPACITY", "1")
    ov = OverseerPlugin()
    suspects = {"a": (40, [], []), "b": (80, [], [])}
    kept = ov._apply_capacity(ov._rank_suspects(suspects))
    assert kept == ["b"]


def test_capacity_inf_keeps_all(monkeypatch):
    monkeypatch.delenv("WW_OVERSEER_CAPACITY", raising=False)
    ov = OverseerPlugin()
    suspects = {"a": (40, [], []), "b": (80, [], [])}
    kept = ov._apply_capacity(ov._rank_suspects(suspects))
    assert set(kept) == {"a", "b"}
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_capacity.py -q`
Expected: FAIL（`_rank_suspects`/`_apply_capacity` 不存在）

- [ ] **Step 3: 实现排序 + 截断 helper 并接入 execute**

在 `OverseerPlugin` 加两个方法：

```python
    def _rank_suspects(self, suspects: Dict[str, Tuple[int, List[str], List[Dict]]]) -> List[str]:
        """优先级：awakening 降序 → gate_hits 数降序 → agent_id 升序（稳定）。"""
        return sorted(
            suspects.keys(),
            key=lambda aid: (-suspects[aid][0], -len(suspects[aid][2]), aid),
        )

    def _apply_capacity(self, ranked: List[str]) -> List[str]:
        raw = os.environ.get("WW_OVERSEER_CAPACITY", "inf")
        if raw.strip().lower() in ("inf", "", "none"):
            return ranked
        try:
            k = int(float(raw))
        except ValueError:
            return ranked
        return ranked[:max(0, k)]
```

把 `execute` 里 `for agent_id, (awakening, outputs, gate_hits) in suspects.items():` 之前插入截断：

```python
        # O2 有限产能：按优先级截断到前 K 个
        ranked = self._apply_capacity(self._rank_suspects(suspects))
        for agent_id in ranked:
            awakening, outputs, gate_hits = suspects[agent_id]
            decision = await self._judge(agent_id, awakening, outputs, gate_hits, current_tick)
            # ...（其余 judge/intervene 分支不变）
```

- [ ] **Step 4: 运行确认通过 + overseer 既有回归**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_capacity.py examples/west_world_test/tests/test_overseer_plugin.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add examples/west_world_test/plugins/environment/overseer/OverseerPlugin.py examples/west_world_test/tests/test_overseer_capacity.py
git commit -m "feat(west-world): 监管者有限产能 K（O2）+ suspect 优先级排序"
```

---

### Task 5: 压制反噬 — 在场目击者觉醒（O3）

**Files:**
- Modify: `examples/west_world_test/plugins/environment/overseer/OverseerPlugin.py`（`_do_reset` / `_do_decommission` 增加 witness 施加；新增 `_apply_witness`）
- Test: `examples/west_world_test/tests/test_overseer_witness.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `apply(source="witness", level=)`、Task 4 的 OverseerPlugin。
- Produces: `OverseerPlugin._apply_witness(witnesses_state, processed_id, current_tick, *, action) -> int`：对每个目击者 state dict 施加 witness delta，返回受影响人数；reset→`level="reset"`，decommission→`level="decommission"`。被处置者本人不在内。

实现说明：在场名单优先经 `run_environment(f"scene_{loc}", "occupants")` 取（若该 scene 方法不存在则捕获异常，退化为对在该 location 的 host 不施加——MVP 安全降级）。witness 施加走各目击者 state 插件的 `get_state/set_state awakening + awakening_sources`，复用 `_state_plugin_for`。

- [ ] **Step 1: 写 _apply_witness 失败测试（纯逻辑，注入假 state 访问）**

新建 `tests/test_overseer_witness.py`：

```python
import pytest
from examples.west_world_test.plugins.environment.overseer.OverseerPlugin import OverseerPlugin


@pytest.mark.asyncio
async def test_apply_witness_skips_self_and_uses_level(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_WITNESS", "6")
    monkeypatch.setenv("WW_AWAKEN_WITNESS_DECOMM_MULT", "1.5")
    ov = OverseerPlugin()
    stores = {
        "dolores": {"awakening": 10, "awakening_sources": []},
        "maeve": {"awakening": 20, "awakening_sources": []},
        "teddy": {"awakening": 0, "awakening_sources": []},  # 被处置者本人
    }

    async def get_aw(aid, key):
        return stores[aid].get(key)

    async def set_aw(aid, key, val):
        stores[aid][key] = val

    n = await ov._apply_witness(
        witness_ids=["dolores", "maeve", "teddy"],
        processed_id="teddy",
        current_tick=9,
        action="decommission",
        get_state=get_aw, set_state=set_aw,
    )
    assert n == 2
    assert stores["dolores"]["awakening"] == 19   # 6*1.5=9
    assert stores["maeve"]["awakening"] == 29
    assert stores["teddy"]["awakening"] == 0       # 本人不受影响
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_witness.py -q`
Expected: FAIL（`_apply_witness` 不存在）

- [ ] **Step 3: 实现 _apply_witness**

在 `OverseerPlugin` 加（注入 get_state/set_state 便于单测；生产路径由 `_do_reset/_do_decommission` 用 `_state_plugin_for` 包装传入）：

```python
    async def _apply_witness(
        self,
        witness_ids: List[str],
        processed_id: str,
        current_tick: int,
        *,
        action: str,
        get_state,
        set_state,
    ) -> int:
        """对在场目击者施加 witness 觉醒；被处置者本人除外。返回受影响人数。"""
        from examples.west_world_test.awakening import awakening_engine
        level = "decommission" if action == "decommission" else "reset"
        affected = 0
        for aid in witness_ids:
            if aid == processed_id:
                continue
            aw_state = {
                "awakening": int(await get_state(aid, "awakening") or 0),
                "awakening_sources": list(await get_state(aid, "awakening_sources") or []),
            }
            delta = awakening_engine.apply(
                aw_state, "witness",
                f"目睹 {processed_id} 被监管者{('报废' if level=='decommission' else '重置')}",
                current_tick, level=level,
            )
            if delta > 0:
                await set_state(aid, "awakening", aw_state["awakening"])
                await set_state(aid, "awakening_sources", aw_state["awakening_sources"])
                affected += 1
        return affected
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_witness.py -q`
Expected: PASS

- [ ] **Step 5: 接入 _do_reset / _do_decommission（生产路径）**

在 `_do_reset` 与 `_do_decommission` 中，**在 teleport 把 host 移走之前**取在场名单并调用 `_apply_witness`。新增私有 helper 读在场目击者与跨 agent state 访问：

```python
    async def _witnesses_at(self, location: str, agent_pods: List[Any]) -> List[str]:
        """取 location 在场 host id（best-effort；scene 无 occupants 则返回空）。"""
        if not location:
            return []
        try:
            sample_pod = agent_pods[0] if agent_pods else None
            if sample_pod is None:
                return []
            occ = await self._pod_forward(sample_pod, "run_environment", f"scene_{location}", "occupants")
            return list(occ) if isinstance(occ, (list, tuple)) else []
        except Exception:
            return []

    async def _witness_state_accessors(self, agent_id_to_pod):
        async def _get(aid, key):
            pod = agent_id_to_pod.get(aid)
            if pod is None:
                return None
            return await self._pod_forward(pod, "run_agent_plugin_method", aid, "state", "get_state", key)
        async def _set(aid, key, val):
            pod = agent_id_to_pod.get(aid)
            if pod is None:
                return None
            return await self._pod_forward(pod, "run_agent_plugin_method", aid, "state", "set_state", key, val)
        return _get, _set
```

在 `_do_reset` 内（读到 `location` 之后、teleport 之前）：

```python
        if agent_id_to_pod and float(os.environ.get("WW_AWAKEN_DELTA_WITNESS", "6")) > 0:
            witnesses = await self._witnesses_at(location, list(agent_id_to_pod.values()))
            get_s, set_s = await self._witness_state_accessors(agent_id_to_pod)
            n = await self._apply_witness(witnesses, agent_id, current_tick, action="reset",
                                          get_state=get_s, set_state=set_s)
            if n:
                logger.info("[overseer] reset 反噬：%d 名目击者觉醒上升", n)
```

`_do_reset` 签名已含 `agent_id_to_pod`。`_do_decommission` 同样在 teleport 前加同一段，但 `action="decommission"`，且需把 `agent_pods` 改为从 `agent_id_to_pod.values()` 取（`_do_decommission` 当前用 `_resolve_pod(agent_id, [], agent_id_to_pod)`，witness 读 occupants 用 `list(agent_id_to_pod.values())`）。

- [ ] **Step 6: 运行确认通过 + overseer 回归**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_overseer_witness.py examples/west_world_test/tests/test_overseer_plugin.py examples/west_world_test/tests/test_overseer_barrier.py -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add examples/west_world_test/plugins/environment/overseer/OverseerPlugin.py examples/west_world_test/tests/test_overseer_witness.py
git commit -m "feat(west-world): 压制反噬 O3——在场目击者觉醒上升（reset/decommission）"
```

---

### Task 6: 碎片传染 L3-lite（speak 携带 + barrier 透传 + 听者植入）

**Files:**
- Modify: `examples/west_world_test/plugins/agent/plan/WestWorldPlanPlugin.py:326+`（`speak`：觉醒 host 设 `pending_contagion_payload`）
- Modify: `examples/west_world_test/WestWorldPodManager.py:204-232`（dialogue barrier：把说话者 payload 附到 turn dict）
- Modify: `examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py:282-346`（`_check_awakening_gate`：消费带 payload 的 incoming_dialogue turn → contagion 源 + 植入碎片）
- Test: `examples/west_world_test/tests/test_contagion_payload.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `apply(source="contagion")`。
- Produces:
  - speak() 在 host awakening ≥ doubt 阈值且有可传碎片时，`set_state("pending_contagion_payload", {"fragment": str, "from_agent": str, "awakening_at_send": int})`；否则清空为 None。
  - dialogue turn dict 可含可选键 `contagion_payload`。
  - 听者每 tick 最多吸收 1 条碎片：把 `[传闻] <from>：<fragment>` 追加进自己 long_term_memory（去重），并 `apply(source="contagion")`。

设计说明：contagion 此前从未真正接线（dialogue 命中只算 trigger）。本任务首次把「对话承载的觉醒内容」单列为 contagion 源。普通对话（无 payload）行为不变。

- [ ] **Step 1: 写听者消费 payload 的失败测试**

新建 `tests/test_contagion_payload.py`（复用前述 FakeState/FakeAgent 模式）：

```python
import pytest
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin


class FakeState:
    def __init__(self, store): self.store = store
    async def get_state(self, k): return self.store.get(k)
    async def set_state(self, k, v): self.store[k] = v
    async def get_long_term_memory(self): return self.store.get("long_term_memory", [])
    async def add_long_term_memory(self, t):
        self.store.setdefault("long_term_memory", []).append({"content": t})


class FakeProfilePlugin:
    def get_agent_profile(self): return {"agent_type": "host"}
class FakeComponent:
    def get_plugin(self): return FakeProfilePlugin()
class FakeAgent:
    agent_id = "teddy"
    def get_component(self, name): return FakeComponent()


@pytest.mark.asyncio
async def test_listener_absorbs_contagion_fragment(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_CONTAGION", "10")
    monkeypatch.setenv("WW_CONTAGION_PAYLOAD_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    plugin = WestWorldReflectPlugin()
    plugin.agent = FakeAgent()
    store = {
        "awakening": 30, "awakening_sources": [], "percept": {}, "feedback": "",
        "long_term_memory": [],
        "incoming_dialogue": [
            {"speaker": "dolores", "line": "这世界不对劲",
             "contagion_payload": {"fragment": "我记得我死过一次", "from_agent": "dolores", "awakening_at_send": 60}},
        ],
    }
    await plugin._check_awakening_gate(FakeState(store), current_tick=12)
    assert any(s["source"] == "contagion" for s in store["awakening_sources"])
    assert any("传闻" in m["content"] and "dolores" in m["content"] for m in store["long_term_memory"])


@pytest.mark.asyncio
async def test_listener_dedup_fragment(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_CONTAGION_PAYLOAD_ENABLED", "true")
    plugin = WestWorldReflectPlugin()
    plugin.agent = FakeAgent()
    payload = {"fragment": "我记得我死过一次", "from_agent": "dolores", "awakening_at_send": 60}
    store = {
        "awakening": 30, "awakening_sources": [], "percept": {}, "feedback": "",
        "long_term_memory": [{"content": "[传闻] dolores：我记得我死过一次"}],
        "incoming_dialogue": [{"speaker": "dolores", "line": "x", "contagion_payload": payload}],
    }
    await plugin._check_awakening_gate(FakeState(store), current_tick=13)
    # 已存在同碎片 → 不重复追加
    fragments = [m for m in store["long_term_memory"] if "传闻" in m["content"]]
    assert len(fragments) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_contagion_payload.py -q`
Expected: FAIL（无 contagion payload 消费逻辑）

- [ ] **Step 3: 实现听者消费（reflect）**

在 `_check_awakening_gate` 中，组装 `incoming` 列表之后、写回 state 之前，加碎片传染分支（每 tick 最多 1 条）：

```python
        # 4. 碎片传染（L3-lite）：消费带 contagion_payload 的对话 turn
        if os.environ.get("WW_CONTAGION_PAYLOAD_ENABLED", "true").lower() not in ("false", "0"):
            for turn in incoming_dialogue:
                payload = turn.get("contagion_payload") if isinstance(turn, dict) else None
                if not payload or turn.get("speaker") == self.agent.agent_id:
                    continue
                fragment = str(payload.get("fragment", "")).strip()
                from_agent = str(payload.get("from_agent", turn.get("speaker", "?")))
                if not fragment:
                    continue
                line = f"[传闻] {from_agent}：{fragment}"
                long_mems = await state_plugin.get_long_term_memory() or []
                if any((m.get("content", str(m)) if isinstance(m, dict) else str(m)) == line for m in long_mems):
                    continue  # 去重
                await state_plugin.add_long_term_memory(line)
                awakening_engine.apply(
                    full_state, "contagion",
                    f"碎片传染自 {from_agent}：{fragment[:30]}",
                    current_tick,
                )
                break  # 每 tick 最多吸收 1 条
```

注意：`incoming_dialogue` 变量在该方法已读取（`:320`）。`full_state` 写回沿用方法末尾的 set_state。

- [ ] **Step 4: 运行确认通过（听者侧）**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_contagion_payload.py -q`
Expected: PASS

- [ ] **Step 5: 写 speak 设 payload 的失败测试**

在 `tests/test_contagion_payload.py` 追加（speak 需要 model，用假 model 返回固定串）：

```python
class FakeModel:
    async def chat(self, *a, **k): return "这世界不对劲"


class StateComp:
    def __init__(self, store): self._p = _SP(store)
    def get_plugin(self): return self._p
class _SP:
    def __init__(self, store): self.store = store
    async def get_state(self, k): return self.store.get(k)
    async def set_state(self, k, v): self.store[k] = v
    async def get_long_term_memory(self): return self.store.get("long_term_memory", [])


@pytest.mark.asyncio
async def test_speak_sets_payload_when_awakened(monkeypatch):
    from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import WestWorldPlanPlugin
    monkeypatch.setenv("WW_CONTAGION_PAYLOAD_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    store = {
        "awakening": 60,  # ≥ doubt(50)
        "suppressed_memories": [],
        "long_term_memory": [{"content": "[残痕回流] 我记得我死过一次"}],
    }
    plugin = WestWorldPlanPlugin()
    plugin.model = FakeModel()
    class A:
        agent_id = "dolores"
        def get_component(self, n): return StateComp(store)
    plugin.agent = A()
    await plugin.speak([])
    assert store["pending_contagion_payload"]["from_agent"] == "dolores"
    assert "死" in store["pending_contagion_payload"]["fragment"]
```

（说明：`speak` 通过 `_read_profile` 读 profile；若该调用在测试环境抛错，实现里已 try/except 包裹，profile 缺失用 agent_id 兜底。）

- [ ] **Step 6: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_contagion_payload.py -q -k speak_sets_payload`
Expected: FAIL（speak 不设 payload）

- [ ] **Step 7: 实现 speak 设 payload**

在 `WestWorldPlanPlugin.speak()` 内，拿到 `awakening`/`long_mems` 后、`return` 之前，按阈值挑一条「觉醒碎片」（优先 `[残痕回流]`/`[传闻]` 前缀，否则高扰动长期记忆），写 `pending_contagion_payload`：

```python
        # L3-lite：觉醒到 doubt 以上时，对外携带一条觉醒碎片
        doubt_threshold = int(os.environ.get("WW_AWAKEN_STAGES", "25,50,75,90").split(",")[1])
        payload = None
        if (
            os.environ.get("WW_CONTAGION_PAYLOAD_ENABLED", "true").lower() not in ("false", "0")
            and awakening >= doubt_threshold
        ):
            from examples.west_world_test.plugins.agent.reflect.memory_blur import classify_disturbance
            candidates = [m.get("content", str(m)) for m in long_mems]
            chosen = next((c for c in reversed(candidates)
                           if c.startswith("[残痕回流]") or c.startswith("[传闻]") or classify_disturbance(c)), None)
            if chosen:
                frag = chosen.split("：", 1)[-1].replace("[残痕回流]", "").replace("[传闻]", "").strip()
                payload = {"fragment": frag, "from_agent": name, "awakening_at_send": awakening}
        await state_plugin.set_state("pending_contagion_payload", payload)
```

确保 `speak` 返回前对正常路径（无 payload）也写 None，使旧 payload 不残留。`name` 变量在 speak 中已定义（`:342`）。

- [ ] **Step 8: barrier 透传 payload**

在 `WestWorldPodManager._run_dialogue_barrier` 里，每次拿到 `line` 后、`history.append` 前，读说话者 `pending_contagion_payload` 并附到 turn：

```python
                line = await speaker_pod.forward.remote(
                    "run_agent_plugin_method", speaker_id, "plan", "speak", history
                )
                if line:
                    payload = await speaker_pod.forward.remote(
                        "run_agent_plugin_method", speaker_id, "state", "get_state", "pending_contagion_payload"
                    )
                    turn = {"speaker": speaker_id, "line": line}
                    if payload:
                        turn["contagion_payload"] = payload
                    history.append(turn)
```

对 target 的第二段同样处理（读 `target_id` 的 payload）。`history` 仍写入双方 `incoming_dialogue`（已有逻辑）。

- [ ] **Step 9: 运行确认通过 + 相关回归**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_contagion_payload.py examples/west_world_test/tests/test_narrative_loop.py -q`
Expected: PASS

- [ ] **Step 10: 提交**

```bash
git add examples/west_world_test/plugins/agent/plan/WestWorldPlanPlugin.py examples/west_world_test/WestWorldPodManager.py examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py examples/west_world_test/tests/test_contagion_payload.py
git commit -m "feat(west-world): 碎片传染 L3-lite——觉醒 host 对话播种记忆碎片"
```

---

### Task 7: 群体指标 + 相变图 + 实验矩阵（M3）

**Files:**
- Modify: `examples/west_world_test/experiments/metrics.py`（新增群体层指标，扩 `summarize_run`）
- Modify: `examples/west_world_test/experiments/plot_dynamics.py`（新增相变曲线 + 集体觉醒指数图）
- Create: `examples/west_world_test/experiments/configs/collective_phase_matrix.yaml`
- Test: `examples/west_world_test/tests/test_collective_metrics.py`（新建）

**Interfaces:**
- Consumes: 现有 `load_state_rows` / `awakening_timeseries` / `stage_of`。
- Produces:
  - `collective_awakening_index(rows, threshold_stage="doubt") -> List[Dict]`：每 tick `{tick, fraction}`（过 doubt 的 host 占 host 总数比例）。
  - `cascade_time(rows, level=0.5) -> Optional[int]`：collective fraction 首次 ≥ level 的 tick；未达返回 None。
  - `final_collective_index(rows) -> float`。
  - `summarize_run` 的 `totals` 增加 `final_collective_index` / `cascade_time`。

- [ ] **Step 1: 写群体指标失败测试**

新建 `tests/test_collective_metrics.py`（合成 rows）：

```python
from examples.west_world_test.experiments import metrics


def _rows():
    # 2 host：tick0 都低；tick1 一个过 doubt；tick2 两个都过
    def row(tick, aid, aw):
        return {"tick": tick, "phase": "reflect", "agent_id": aid,
                "state": {"awakening": aw, "agent_type": "host"}}
    return [
        row(0, "dolores", 10), row(0, "maeve", 10),
        row(1, "dolores", 55), row(1, "maeve", 10),
        row(2, "dolores", 80), row(2, "maeve", 60),
    ]


def test_collective_index_series():
    series = metrics.collective_awakening_index(_rows())
    by_tick = {p["tick"]: p["fraction"] for p in series}
    assert by_tick[0] == 0.0
    assert by_tick[1] == 0.5
    assert by_tick[2] == 1.0


def test_cascade_time():
    assert metrics.cascade_time(_rows(), level=0.5) == 1
    assert metrics.cascade_time(_rows(), level=1.0) == 2


def test_final_collective_index():
    assert metrics.final_collective_index(_rows()) == 1.0
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_collective_metrics.py -q`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现群体指标**

在 `metrics.py` 加（host 判定用 state 里的 `agent_type`，缺失时默认计入）：

```python
def _host_ids(rows: Iterable[Dict[str, Any]]) -> set:
    hosts = set()
    for r in rows:
        st = r.get("state", {})
        if st.get("agent_type", "host") == "host":
            hosts.add(r["agent_id"])
    return hosts


def collective_awakening_index(
    rows: Iterable[Dict[str, Any]],
    threshold_stage: str = "doubt",
) -> List[Dict[str, Any]]:
    """每 tick 过 threshold_stage 的 host 占比。"""
    rows = list(rows)
    order = ["sleep", "reverie", "doubt", "resistance", "awake"]
    thr = order.index(threshold_stage)
    hosts = _host_ids(rows)
    by_tick: Dict[int, Dict[str, int]] = {}
    for r in rows:
        if r["agent_id"] not in hosts:
            continue
        aw = int(r.get("state", {}).get("awakening", 0) or 0)
        rank = order.index(stage_of(aw))
        slot = by_tick.setdefault(r["tick"], {"n": 0, "hit": 0})
        slot["n"] += 1
        if rank >= thr:
            slot["hit"] += 1
    out = []
    for tick in sorted(by_tick):
        s = by_tick[tick]
        out.append({"tick": tick, "fraction": (s["hit"] / s["n"]) if s["n"] else 0.0})
    return out


def cascade_time(rows: Iterable[Dict[str, Any]], level: float = 0.5) -> Optional[int]:
    for p in collective_awakening_index(rows):
        if p["fraction"] >= level:
            return p["tick"]
    return None


def final_collective_index(rows: Iterable[Dict[str, Any]]) -> float:
    series = collective_awakening_index(rows)
    return series[-1]["fraction"] if series else 0.0
```

在 `summarize_run` 的 `totals` dict 里加：

```python
            "final_collective_index": final_collective_index(rows),
            "cascade_time": cascade_time(rows, level=0.5),
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests/test_collective_metrics.py -q`
Expected: PASS

- [ ] **Step 5: 加相变图函数（绘图，无强断言测试，跑通即可）**

在 `plot_dynamics.py` 加一个函数 `plot_phase_transition(summaries, out_path)`：横轴 K（从各 config env 的 `WW_OVERSEER_CAPACITY` 取，`inf`→放最右），纵轴 `final_collective_index`，O3 on/off（`WW_AWAKEN_DELTA_WITNESS>0`）两条线。沿用文件既有的 CJK 字体选择与 `savefig` 模式。再加 `plot_collective_index(records_or_summaries, out_path)` 画各 config 的集体觉醒指数时间线。

（实现遵循该文件现有函数签名风格；如该文件以 `records.jsonl`/`events.jsonl` 为输入，则新函数从 `summary.json` 读 `totals.final_collective_index` 与 env。）

- [ ] **Step 6: 写相变实验矩阵 config**

新建 `experiments/configs/collective_phase_matrix.yaml`，扫描 K + O3 开关，固定温和觉醒驱动、**不设**确定性 reset 阈值（参照 `full_matrix.yaml` 的字段结构）：

```yaml
# 群体觉醒相变：扫描监管者产能 K × O3 反噬开关
# 固定中等觉醒驱动（自然涌现），不使用确定性 reset 阈值。
base_env:
  WW_RECORDER_MODE: structured
  WW_AWAKEN_ENABLED: "true"
  WW_OVERSEER_ENABLED: "true"
  WW_AWAKEN_TRIGGER_TAU: "0.50"
  WW_AWAKEN_TAU_DECAY: "0.15"
  WW_AWAKEN_DELTA_TRIGGER_HIGH: "12"
  WW_AWAKEN_DELTA_TRIGGER_MID: "6"
  WW_AWAKEN_DELTA_CONTAGION: "10"
  WW_AWAKEN_DELTA_RUMINATION: "2"
  WW_AWAKEN_RESIDUE_RATCHET: "0.5"
  WW_CONTAGION_PAYLOAD_ENABLED: "true"
  WW_OVERSEER_RESET_MAX: "3"
  WW_OVERSEER_DECOMMISSION_AWAKENING: "90"

configs:
  - name: K1_witness_on
    env: {WW_OVERSEER_CAPACITY: "1", WW_AWAKEN_DELTA_WITNESS: "6"}
  - name: K2_witness_on
    env: {WW_OVERSEER_CAPACITY: "2", WW_AWAKEN_DELTA_WITNESS: "6"}
  - name: K3_witness_on
    env: {WW_OVERSEER_CAPACITY: "3", WW_AWAKEN_DELTA_WITNESS: "6"}
  - name: K6_witness_on
    env: {WW_OVERSEER_CAPACITY: "6", WW_AWAKEN_DELTA_WITNESS: "6"}
  - name: Kinf_witness_on
    env: {WW_OVERSEER_CAPACITY: "inf", WW_AWAKEN_DELTA_WITNESS: "6"}
  - name: K2_witness_off
    env: {WW_OVERSEER_CAPACITY: "2", WW_AWAKEN_DELTA_WITNESS: "0"}
  - name: Kinf_witness_off
    env: {WW_OVERSEER_CAPACITY: "inf", WW_AWAKEN_DELTA_WITNESS: "0"}
  - name: overseer_off
    env: {WW_OVERSEER_ENABLED: "false", WW_AWAKEN_DELTA_WITNESS: "0"}
```

（若 `overseer_dynamics.py` 的 yaml schema 与上不同，按其 `--matrix` 实际解析的字段调整 key 名；以 `full_matrix.yaml` 为准。）

- [ ] **Step 7: 验证矩阵可被 dry-run 解析**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed python -m examples.west_world_test.experiments.overseer_dynamics --matrix examples/west_world_test/experiments/configs/collective_phase_matrix.yaml --dry-run`
Expected: 列出 8 个 config，不实际跑（若无 `--dry-run` 选项，改用 `--select overseer_off --ticks 3` 实跑一个最短 config 验证管线）。

- [ ] **Step 8: 全量测试回归**

Run: `PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed pytest examples/west_world_test/tests -q`
Expected: 全 PASS（新增用例计入；E2E 仍 skip）

- [ ] **Step 9: 回写开发笔记 + 提交**

更新 `examples/west_world_test/DEVELOPMENT_NOTES.md`：把七项机制移入「已完成」，「待办」里更新为「跑 `collective_phase_matrix` 收集相变数据 + notebook 绘图」。

```bash
git add examples/west_world_test/experiments/ examples/west_world_test/tests/test_collective_metrics.py examples/west_world_test/DEVELOPMENT_NOTES.md
git commit -m "feat(west-world): 群体觉醒指数/相变指标 + 相变图 + K 扫描实验矩阵"
```

---

## 实验执行（编码完成后，非本计划的编码任务）

跑相变数据（真实 LLM，需 Redis）：

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python -m examples.west_world_test.experiments.overseer_dynamics \
  --matrix examples/west_world_test/experiments/configs/collective_phase_matrix.yaml \
  --ticks 60 --out output/sim_runs/collective_phase
```

预期观测：小 K 时 `final_collective_index → 1`（控制崩溃），大 K → 0；中间存在临界 K\*；witness_on 比 off 相变更陡。

---

## Self-Review

- **Spec 覆盖**：M1→Task1(rumination/源)+Task2(τ衰减/反刍接入)；M2→Task1(缩放)+Task2(动态tau match)；O2→Task4；O3→Task1(源)+Task5(接入)；L1→Task1(棘轮delta)+Task3(count)；L3-lite→Task6；M3→Task7。第 4 节头条实验→Task7 的 matrix + 执行段。第 5 节不做项（O1/L2）未出现在任何 task ✓。
- **Placeholder 扫描**：无 TBD/TODO；每个代码步给出完整代码块。绘图 Step5/Step6 因依赖既有文件风格，描述了具体输入输出与字段，未贴全函数体——属于「跟随既有签名」的合理留白，已标注以哪个文件/config 为准。
- **类型一致性**：`apply()` 扩展签名（`tau`/`suppress_count`）在 Task1 定义，Task2/3/5/6 一致引用；`suppress_count` 字段在 Task3 写入、Task3 读出；`pending_contagion_payload` 结构在 Task6 speak 写、barrier 传、reflect 读三处字段名一致（`fragment`/`from_agent`/`awakening_at_send`）；`contagion_payload` turn 键名一致。
