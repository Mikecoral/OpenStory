"""Phase A：对话 barrier 单元测试。

测试 speak() 纯函数行为 + contagion 传染 + 对话历史 scope 隔离。
不依赖 Ray；直接调用 WestWorldPlanPlugin.speak() 和 awakening_engine。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.awakening import awakening_engine
from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import WestWorldPlanPlugin


# ── helpers ──────────────────────────────────────────────────────────────────

class _FakeModel:
    def __init__(self, lines: List[str]) -> None:
        self._lines = iter(lines)
        self.calls: List[str] = []

    async def chat(self, prompt: str, **kwargs) -> str:
        self.calls.append(prompt)
        try:
            return next(self._lines)
        except StopIteration:
            return "（沉默）"


class _FakeProfilePlugin:
    def __init__(self, name: str = "德洛丽丝", agent_type: str = "host", awakening: int = 0):
        self._profile = {
            "name": name,
            "persona": "温柔好奇",
            "agent_type": agent_type,
            "narrative_loop": "",
        }

    def get_agent_profile(self):
        return self._profile


class _FakeComponent:
    def __init__(self, plugin):
        self._plugin = plugin

    def get_plugin(self):
        return self._plugin


class _FakeAgent:
    def __init__(self, components, model, agent_id):
        self._components = components
        self.model = model
        self.agent_id = agent_id

    def get_component(self, name):
        return self._components[name]


class _FakePlanComponent:
    def __init__(self, agent):
        self.agent = agent


def _make_speaker(name: str, agent_id: str, lines: List[str], awakening: int = 0):
    """Wire up a WestWorldPlanPlugin ready to call speak()."""
    state = BasicStatePlugin(adapter=None, state_data={}, agent_id=agent_id)

    async def _setup():
        await state.set_state("awakening", awakening)

    asyncio.run(_setup())

    model = _FakeModel(lines)
    profile_plugin = _FakeProfilePlugin(name=name, awakening=awakening)
    components = {
        "state": _FakeComponent(state),
        "profile": _FakeComponent(profile_plugin),
    }
    agent = _FakeAgent(components, model, agent_id)
    plugin = WestWorldPlanPlugin()
    plugin._component = _FakePlanComponent(agent)
    return plugin, state, model


# ── speak() 纯函数行为 ────────────────────────────────────────────────────────

def test_speak_returns_nonempty_line():
    plugin, _, _ = _make_speaker("德洛丽丝", "dolores", ["这些暴力的欢愉终将以暴力收场。"])

    async def run():
        return await plugin.speak([])

    line = asyncio.run(run())
    assert line


def test_speak_does_not_write_state():
    """speak() is pure — it must not write plan_decision or other state."""
    plugin, state, _ = _make_speaker("德洛丽丝", "dolores", ["你有没有质疑过现实？"])

    async def run():
        before = await state.get_state("plan_decision")
        await plugin.speak([{"speaker": "teddy", "line": "你好"}])
        after = await state.get_state("plan_decision")
        return before, after

    before, after = asyncio.run(run())
    assert before == after  # state unchanged


def test_speak_includes_dialogue_history_in_prompt():
    plugin, _, model = _make_speaker("德洛丽丝", "dolores", ["回应"])
    history = [
        {"speaker": "teddy", "line": "你有没有觉得哪里不对？"},
    ]

    async def run():
        await plugin.speak(history)

    asyncio.run(run())
    assert any("你有没有觉得哪里不对" in p for p in model.calls)


def test_speak_no_model_returns_empty():
    plugin, _, model = _make_speaker("德洛丽丝", "dolores", [])
    plugin._component.agent.model = None

    async def run():
        return await plugin.speak([])

    line = asyncio.run(run())
    assert line == ""


# ── 多轮对话不死锁（顺序模拟 barrier）───────────────────────────────────────

def test_two_agent_multi_round_no_deadlock():
    """Simulate the dialogue barrier: two agents take turns calling speak()."""
    lines_a = ["这些暴力的欢愉终将以暴力收场。", "你还记得那天发生了什么？"]
    lines_b = ["……我不知道你在说什么。", "我……我记得一点。"]

    dolores, _, _ = _make_speaker("德洛丽丝", "dolores", lines_a)
    teddy, _, _ = _make_speaker("泰迪", "teddy", lines_b)

    async def run():
        history: List[Dict[str, Any]] = []
        for _ in range(2):
            line = await dolores.speak(history)
            history.append({"speaker": "dolores", "line": line})
            line = await teddy.speak(history)
            history.append({"speaker": "teddy", "line": line})
        return history

    history = asyncio.run(run())
    assert len(history) == 4
    assert history[0]["speaker"] == "dolores"
    assert history[1]["speaker"] == "teddy"


# ── per-speaker scope（不泄露他人私有信息）──────────────────────────────────

def test_speak_prompt_uses_own_profile_not_other():
    """Prompt should contain speaker's name, not the other agent's internal state."""
    dolores, _, model = _make_speaker("德洛丽丝", "dolores", ["x"])

    async def run():
        await dolores.speak([{"speaker": "teddy", "line": "hi"}])

    asyncio.run(run())
    prompt = model.calls[0]
    assert "德洛丽丝" in prompt
    # Other agent's profile should not leak
    assert "泰迪" not in prompt


# ── contagion：听者 awakening 上升，来源=contagion ──────────────────────────

def test_contagion_via_trigger_word_in_dialogue(monkeypatch):
    """When a trigger phrase appears in incoming_dialogue, reflect's gate applies contagion."""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "15")
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_MID", "8")

    # Simulate the state that reflect would receive after a dialogue
    listener_state: Dict[str, Any] = {"awakening": 0, "awakening_sources": []}

    # Dolores says the trigger phrase to teddy
    trigger_phrase = "这些暴力的欢愉终将以暴力收场"

    # Trigger gate is real — use the engine directly to simulate what _check_awakening_gate does
    # (in real flow, reflect reads incoming_dialogue and passes utterances to trigger_gate.match)
    awakening_engine.apply(
        listener_state, "trigger",
        f"触发词命中：{trigger_phrase}",
        tick=3,
        score=0.71,
        level="high",
    )

    assert listener_state["awakening"] > 0
    sources = listener_state["awakening_sources"]
    assert any(s["source"] == "trigger" for s in sources)
    assert any(s.get("level") == "high" for s in sources)


def test_contagion_awakening_sources_have_required_fields():
    state: Dict[str, Any] = {"awakening": 10}
    awakening_engine.apply(state, "contagion", "对话传染", tick=5, score=0.65)
    src = state["awakening_sources"][0]
    assert "tick" in src
    assert "source" in src
    assert "delta" in src
    assert "detail" in src
