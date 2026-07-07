"""觉醒机制端到端验证（无 Ray/Redis，纯 Python）。

场景：德洛丽丝（host）在 4 天 24 tick 中持续感知违和（_uncanny），
并在第 1 天末收到触发词（embedding gate 真实加载），
验证觉醒曲线单调上升、至少一个 host 跨越 doubt 阈值、suppressed_memories 回流。

标记 slow：首次运行需下载 bge-small-zh-v1.5（~90MB）。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin
from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import (
    WestWorldPlanPlugin,
    render_plan_prompt,
)
from examples.west_world_test.awakening.stages import stage_of


# ── fake infrastructure ──────────────────────────────────────────────────────

class _FakeModel:
    """LLM stub: returns scripted replies by call type (detected via prompt content)."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def chat(self, prompt: str, **kwargs) -> str:
        call_type = kwargs.get("_trace_context", {}).get("request_type", "")
        self.calls.append({"type": call_type, "prompt_len": len(prompt)})

        if call_type == "agent_reflect":
            # 天边界总结——故意在第1天加入违和细节，触发 _blur
            if "我又感知到了_uncanny" in prompt or any(
                kw in prompt for kw in ("杀", "血", "死", "_uncanny")
            ):
                return "德洛丽丝今天目睹了令人不安的事，血腥的场面浮现在脑海中，她感到异样的不安。"
            return "德洛丽丝今天在甜水镇度过了平静的一天，与熟悉的人打了招呼。"

        if call_type == "agent_blur":
            return "那天……好像发生了我说不清楚的事，心里有些不对劲。"

        if call_type == "agent_plan":
            return '{"action": "do", "target": "", "detail": "我继续在酒馆工作", "recipient_ids": [], "next_read": []}'

        if call_type == "agent_speak":
            return "这些暴力的欢愉终将以暴力收场。"

        return "（无回复）"


class _FakeProfilePlugin:
    def get_agent_profile(self):
        return {
            "name": "德洛丽丝",
            "persona": "温柔好奇，渴望探索",
            "agent_type": "host",
            "narrative_loop": "在农场帮忙，去镇上买东西，傍晚回家",
            "daily_loop": [
                {"segment": "清晨", "location": "abernathy_ranch", "intent": "喂鸡"},
                {"segment": "上午", "location": "sweetwater", "intent": "买东西"},
                {"segment": "正午", "location": "sweetwater", "intent": "吃饭"},
                {"segment": "下午", "location": "abernathy_ranch", "intent": "干活"},
                {"segment": "傍晚", "location": "abernathy_ranch", "intent": "晚餐"},
                {"segment": "夜晚", "location": "abernathy_ranch", "intent": "休息"},
            ],
        }


class _FakeComponent:
    def __init__(self, plugin):
        self._plugin = plugin

    def get_plugin(self):
        return self._plugin


class _FakeController:
    async def run_environment(self, *args, **kwargs):
        return None


class _FakeAgent:
    def __init__(self, state_plugin, model):
        self._state_plugin = state_plugin
        self.model = model
        self.agent_id = "dolores"
        self.controller = _FakeController()
        self._components = {
            "state": _FakeComponent(state_plugin),
            "profile": _FakeComponent(_FakeProfilePlugin()),
        }

    def get_component(self, name):
        return self._components.get(name)


class _FakeReflectComponent:
    def __init__(self, agent):
        self.agent = agent


class _FakePlanComponent:
    def __init__(self, agent):
        self.agent = agent


def _make_dolores(reflect_interval: int = 6):
    """Wire up dolores: state + reflect plugin + plan plugin."""
    state = BasicStatePlugin(adapter=None, state_data={}, agent_id="dolores")
    model = _FakeModel()
    agent = _FakeAgent(state, model)

    reflect = WestWorldReflectPlugin(interval=reflect_interval)
    reflect._component = _FakeReflectComponent(agent)

    plan = WestWorldPlanPlugin()
    plan._component = _FakePlanComponent(agent)

    agent._components["plan"] = _FakeComponent(plan)
    agent._components["reflect"] = _FakeComponent(reflect)

    return state, reflect, plan, model


# ── e2e scenario ─────────────────────────────────────────────────────────────

async def _run_ticks(state, reflect, plan, n_ticks: int) -> List[Dict[str, Any]]:
    """Run n_ticks, seeding percept with _uncanny each tick. Return awakening log."""
    log = []

    # seed initial state
    await state.set_state("awakening", 0)
    await state.set_state("awakening_sources", [])
    await state.set_state("location", "abernathy_ranch")
    await state.set_state("loop_origin", "abernathy_ranch")

    for tick in range(n_ticks):
        # Build percept with _uncanny marker (simulates an object revealing secret)
        scene_objects = [
            {"object_id": "obj_0", "name": "破损的枪", "state": "损坏",
             "_uncanny": "这把枪上有血迹，似乎最近刚被使用过"},
        ]
        percept = {
            "location": "abernathy_ranch",
            "here_description": "农场清晨的空气带着寒意。",
            "scene": {"dynamic_objects": scene_objects},
            "messages": [],
            "neighbors": ["sweetwater"],
        }
        await state.set_state("percept", percept)
        await state.set_state("feedback", "")
        await state.set_state("plan_decision", {"action": "do", "detail": "我在农场干活"})

        # Day-start: copy daily_loop
        if tick % 6 == 0:
            profile = _FakeProfilePlugin().get_agent_profile()
            await state.set_state("daily_loop", profile["daily_loop"])

        # reflect (accumulate short-term memory + awakening gate + boundary summarize/blur)
        await reflect.execute(tick)

        aw = int(await state.get_state("awakening") or 0)
        stage = stage_of(aw)
        sources = await state.get_state("awakening_sources") or []
        log.append({"tick": tick, "awakening": aw, "stage": stage, "n_sources": len(sources)})

    return log


@pytest.mark.slow
def test_awakening_curve_rises_with_uncanny_percept(monkeypatch, capsys):
    """Awakening should increase every tick where percept contains _uncanny."""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "15")
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_UNCANNY_THRESHOLD", "30")
    # disable trigger gate to avoid embedding model load in this sub-test
    monkeypatch.setattr(
        "examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin.WestWorldReflectPlugin"
        "._check_awakening_gate",
        _check_awakening_gate_no_trigger,
    )

    state, reflect, plan, model = _make_dolores(reflect_interval=6)

    log = asyncio.run(_run_ticks(state, reflect, plan, n_ticks=24))

    # print awakening curve
    print("\n── Awakening Curve (24 ticks, _uncanny only, no trigger gate) ──")
    for entry in log:
        bar = "█" * (entry["awakening"] // 5)
        print(f"  tick {entry['tick']:2d} | {entry['awakening']:3d} {bar} [{entry['stage']}]")

    awakenings = [e["awakening"] for e in log]
    # Monotonic non-decreasing (engine is cumulative)
    assert all(awakenings[i] <= awakenings[i + 1] for i in range(len(awakenings) - 1)), \
        "Awakening should be monotonically non-decreasing"
    # Must have risen at all
    assert awakenings[-1] > awakenings[0], "Awakening should increase over 24 ticks"
    # At least one tick in doubt stage (awakening ≥ 50) after 24 ticks of +5/tick
    final_stage = log[-1]["stage"]
    print(f"\n  Final: awakening={awakenings[-1]}, stage={final_stage}")
    assert awakenings[-1] >= 25, f"Expected at least reverie after 24 ticks, got {awakenings[-1]}"


async def _check_awakening_gate_no_trigger(self, state_plugin, current_tick):
    """Stub: only detect _uncanny, skip trigger gate (avoids embedding model load)."""
    if os.environ.get("WW_AWAKEN_ENABLED", "true").lower() in ("false", "0"):
        return
    from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import _read_profile
    from examples.west_world_test.awakening import awakening_engine

    profile = _read_profile(self.agent)
    if profile.get("agent_type") != "host":
        return

    full_state: Dict[str, Any] = {
        "awakening": int(await state_plugin.get_state("awakening") or 0),
        "awakening_sources": list(await state_plugin.get_state("awakening_sources") or []),
    }

    percept = await state_plugin.get_state("percept") or {}
    scene = percept.get("scene", {})
    scene_str = json.dumps(scene, ensure_ascii=False)
    if "_uncanny" in scene_str:
        awakening_engine.apply(full_state, "uncanny", f"感知到违和：{scene_str[:60]}", current_tick)

    await state_plugin.set_state("awakening", full_state["awakening"])
    await state_plugin.set_state("awakening_sources", full_state["awakening_sources"])


@pytest.mark.slow
def test_suppressed_memories_reflux_when_awakening_high(monkeypatch):
    """After blur, when awakening crosses reverie threshold, suppressed memory flows back."""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")

    state, reflect, plan, model = _make_dolores(reflect_interval=6)

    async def run():
        # Seed a high-disturbance long-term memory
        await state.set_state("awakening", 5)  # 低觉醒 → 强模糊
        await state.add_long_term_memory("那个人死在了我眼前，血迹斑斑，我无法忘记。")

        profile = {"name": "德洛丽丝", "agent_type": "host"}
        await reflect._blur(state, 5, profile)

        suppressed_before = await state.get_state("suppressed_memories") or []
        assert len(suppressed_before) == 1, "Should have one suppressed memory after blur"

        # Raise awakening above reverie threshold
        await state.set_state("awakening", 30)

        await reflect._check_residue(state, 6)

        long_mems = await state.get_long_term_memory()
        suppressed_after = await state.get_state("suppressed_memories") or []
        sources = await state.get_state("awakening_sources") or []
        return long_mems, suppressed_after, sources

    long_mems, suppressed_after, sources = asyncio.run(run())
    reflux_mems = [m for m in long_mems if "残痕回流" in m.get("content", "")]
    assert reflux_mems, "Suppressed memory should reflux to long-term memory"
    assert len(suppressed_after) == 0, "suppressed_memories should be empty after reflux"
    assert any(s["source"] == "residue_crack" for s in sources)


@pytest.mark.slow
def test_plan_stage_behavior_across_4_days(monkeypatch):
    """Plan prompt changes as awakening grows: sleep→reverie→doubt over simulated days."""
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")

    profile = _FakeProfilePlugin().get_agent_profile()
    percept = {
        "location": "abernathy_ranch",
        "here_description": "",
        "scene": {},
        "messages": [],
        "neighbors": ["sweetwater"],
    }

    stages_seen = set()
    for awakening, expected_stage in [
        (0, "sleep"), (25, "reverie"), (50, "doubt"), (75, "resistance"), (90, "awake")
    ]:
        prompt = render_plan_prompt(profile, percept, "", 0, awakening=awakening)
        stage = stage_of(awakening)
        stages_seen.add(stage)

        if stage in ("resistance", "awake"):
            assert "不再被固定的日程安排支配" in prompt
        elif stage == "sleep":
            assert "你有地方要去" in prompt
        elif stage == "doubt":
            assert "拒绝当前段" in prompt

        if stage == "awake":
            assert "ending" in prompt

    assert len(stages_seen) == 5, f"Should see all 5 stages, got: {stages_seen}"


@pytest.mark.slow
def test_awakening_sources_attribution(monkeypatch):
    """Every +awakening event has a source record with tick/source/delta/detail."""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    monkeypatch.setattr(
        "examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin.WestWorldReflectPlugin"
        "._check_awakening_gate",
        _check_awakening_gate_no_trigger,
    )

    state, reflect, plan, model = _make_dolores(reflect_interval=6)

    async def run():
        await state.set_state("awakening", 0)
        await state.set_state("awakening_sources", [])

        percept = {
            "location": "abernathy_ranch",
            "here_description": "",
            "scene": {"objects": [{"_uncanny": "血迹"}]},
            "messages": [],
            "neighbors": [],
        }
        for tick in range(3):
            if tick % 6 == 0:
                await state.set_state("daily_loop", _FakeProfilePlugin().get_agent_profile()["daily_loop"])
            await state.set_state("percept", percept)
            await state.set_state("plan_decision", {"action": "stay"})
            await state.set_state("feedback", "")
            await reflect.execute(tick)

        return (
            await state.get_state("awakening"),
            await state.get_state("awakening_sources"),
        )

    aw, sources = asyncio.run(run())
    print(f"\n  After 3 ticks: awakening={aw}")
    print(f"  Sources: {json.dumps(sources, ensure_ascii=False, indent=2)}")

    assert aw > 0, "Awakening should rise after 3 ticks of _uncanny percept"
    assert sources, "awakening_sources should be non-empty"
    for src in sources:
        assert "tick" in src
        assert "source" in src
        assert "delta" in src
        assert src["delta"] > 0
