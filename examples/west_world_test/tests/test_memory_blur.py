"""Phase B：记忆模糊化单元测试。"""
import asyncio
import os

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.plugins.agent.reflect.memory_blur import (
    classify_disturbance,
    blur_strength,
    render_blur_prompt,
)
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import (
    WestWorldReflectPlugin,
)


# ── 纯函数 ──────────────────────────────────────────────────────────────────

def test_classify_disturbance_high_keywords():
    assert classify_disturbance("那个人死在了我眼前") is True
    assert classify_disturbance("地上都是血迹") is True
    assert classify_disturbance("她用刀杀了他") is True
    assert classify_disturbance("感觉_uncanny，异样的感觉") is True


def test_classify_disturbance_low():
    assert classify_disturbance("今天天气不错，我去镇上买了东西") is False
    assert classify_disturbance("和 maeve 聊了会儿天") is False


def test_classify_disturbance_extra_keywords():
    assert classify_disturbance("暴力的欢愉", extra_keywords=frozenset({"暴力"})) is True
    assert classify_disturbance("平静的一天", extra_keywords=frozenset({"暴力"})) is False


def test_blur_strength_monotone_decreasing():
    """blur_strength 随觉醒度上升严格递减。"""
    threshold = 75
    prev = blur_strength(0, threshold)
    for aw in [10, 20, 30, 50, 74]:
        s = blur_strength(aw, threshold)
        assert s < prev
        prev = s


def test_blur_strength_boundaries():
    assert blur_strength(0, 75) == pytest.approx(1.0)
    assert blur_strength(75, 75) == pytest.approx(0.0)
    assert blur_strength(100, 75) == pytest.approx(0.0)   # clamp
    assert blur_strength(37, 74) == pytest.approx(0.5)


def test_blur_strength_zero_threshold():
    assert blur_strength(50, 0) == 0.0


def test_render_blur_prompt_contains_key_fields():
    p = render_blur_prompt("德洛丽丝", "有人死了", 0.7)
    assert "德洛丽丝" in p
    assert "有人死了" in p
    assert "0.70" in p


# ── integrate: _blur 在 reflect 中的效果 ────────────────────────────────────

class _FakeModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list = []

    async def chat(self, prompt: str, **kwargs) -> str:
        self.calls.append(prompt)
        return self.reply


class _FakeProfilePlugin:
    def __init__(self, agent_type: str = "host"):
        self._type = agent_type

    def get_agent_profile(self):
        return {"name": "德洛丽丝", "persona": "温柔好奇", "agent_type": self._type}


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


class _FakeReflectComponent:
    def __init__(self, agent):
        self.agent = agent


def _make_state_with_long_mem(text: str, awakening: int = 0) -> BasicStatePlugin:
    state = BasicStatePlugin(adapter=None, state_data={}, agent_id="dolores")

    async def _setup():
        await state.add_long_term_memory(text)
        await state.set_state("awakening", awakening)

    asyncio.run(_setup())
    return state


def _make_plugin(model_reply: str, profile_plugin: _FakeProfilePlugin) -> tuple:
    state = BasicStatePlugin(adapter=None, state_data={}, agent_id="dolores")
    model = _FakeModel(model_reply)
    components = {
        "state": _FakeComponent(state),
        "profile": _FakeComponent(profile_plugin),
    }
    agent = _FakeAgent(components, model, "dolores")
    plugin = WestWorldReflectPlugin(interval=6)
    plugin._component = _FakeReflectComponent(agent)
    return plugin, state, model


def test_blur_high_disturbance_memory_is_replaced(monkeypatch):
    """高扰动记忆在天边界被 LLM 改写后替换长期记忆最后一条。"""
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")

    plugin, state, model = _make_plugin("那天……好像发生了我说不清的事。", _FakeProfilePlugin("host"))

    async def run():
        await state.add_long_term_memory("我看见那个人死在了我眼前，血流满地。")
        await state.set_state("awakening", 0)  # 低觉醒度 → 强模糊
        profile = {"name": "德洛丽丝", "agent_type": "host"}
        await plugin._blur(state, 5, profile)

    asyncio.run(run())
    mems = asyncio.run(state.get_long_term_memory())
    assert len(mems) == 1
    assert "说不清" in mems[0]["content"]
    assert model.calls  # LLM 被调用


def test_blur_saves_clear_version_to_suppressed(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")

    plugin, state, model = _make_plugin("模糊版", _FakeProfilePlugin("host"))

    original = "我目睹了一场血腥的杀戮。"

    async def run():
        await state.add_long_term_memory(original)
        await state.set_state("awakening", 0)
        profile = {"name": "德洛丽丝", "agent_type": "host"}
        await plugin._blur(state, 5, profile)

    asyncio.run(run())
    suppressed = asyncio.run(state.get_state("suppressed_memories")) or []
    assert len(suppressed) == 1
    assert suppressed[0]["text"] == original


def test_blur_skipped_for_low_disturbance(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")

    plugin, state, model = _make_plugin("未调用", _FakeProfilePlugin("host"))

    async def run():
        await state.add_long_term_memory("今天天气不错，在酒馆待了一天。")
        await state.set_state("awakening", 0)
        profile = {"name": "德洛丽丝", "agent_type": "host"}
        await plugin._blur(state, 5, profile)

    asyncio.run(run())
    assert not model.calls  # 低扰动不调 LLM
    suppressed = asyncio.run(state.get_state("suppressed_memories")) or []
    assert not suppressed


def test_blur_no_op_at_high_awakening(monkeypatch):
    """觉醒度 ≥ clear_threshold 时 blur_strength=0，不改写记忆。"""
    monkeypatch.setenv("WW_AWAKEN_CLEAR_THRESHOLD", "75")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")

    plugin, state, model = _make_plugin("不应被调用", _FakeProfilePlugin("host"))

    async def run():
        await state.add_long_term_memory("那个人死在了我眼前。")
        await state.set_state("awakening", 75)  # 等于阈值 → strength=0
        profile = {"name": "德洛丽丝", "agent_type": "host"}
        await plugin._blur(state, 5, profile)

    asyncio.run(run())
    assert not model.calls  # 不调 LLM


def test_blur_skipped_for_guest(monkeypatch):
    """guest 类型 agent 不触发 blur。"""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")

    # 通过在 execute 中 profile.get("agent_type") != "host" 的短路来测试
    # 直接测试在 execute 层：向 plugin.execute 写一个 guest 并跑到天边界
    plugin, state, model = _make_plugin("不应被调用", _FakeProfilePlugin("guest"))
    model_summary = _FakeModel("总结文本：那个人死了")
    plugin._component.agent.model = model_summary

    async def run():
        for tick in range(6):
            await state.set_state("plan_decision", {"action": "stay"})
            await state.set_state("feedback", "")
            await state.set_state("location", "saloon")
            if tick == 5:
                await state.add_long_term_memory("那个人死在了我眼前，血迹斑斑。")
                await state.set_state("awakening", 0)
            await plugin.execute(tick)

    asyncio.run(run())
    # 对 guest：model_summary 只被调用 1 次（_summarize），不被调用第 2 次（_blur）
    assert len(model_summary.calls) == 1


def test_check_residue_reflux_when_awakening_high_enough(monkeypatch):
    """觉醒度超过模糊时的值，suppressed_memories 中的碎片回流。"""
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")

    plugin, state, model = _make_plugin("unused", _FakeProfilePlugin("host"))

    async def run():
        await state.set_state("awakening", 30)  # ≥ 梦呓阈值 25
        # 模拟一条被模糊时觉醒度=0 的记忆（现在 30 > 0 → 可回流）
        await state.set_state("suppressed_memories", [
            {"tick": 0, "text": "那个人死在了我眼前。", "awakening_at_blur": 0},
        ])
        await plugin._check_residue(state, 12)

    asyncio.run(run())
    long_mems = asyncio.run(state.get_long_term_memory())
    assert any("残痕回流" in m["content"] for m in long_mems)
    suppressed = asyncio.run(state.get_state("suppressed_memories")) or []
    assert len(suppressed) == 0
    sources = asyncio.run(state.get_state("awakening_sources")) or []
    assert any(s["source"] == "residue_crack" for s in sources)


def test_check_residue_no_reflux_below_reverie(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")

    plugin, state, model = _make_plugin("unused", _FakeProfilePlugin("host"))

    async def run():
        await state.set_state("awakening", 10)  # < 梦呓阈值 25
        await state.set_state("suppressed_memories", [
            {"tick": 0, "text": "那个人死了。", "awakening_at_blur": 0},
        ])
        await plugin._check_residue(state, 6)

    asyncio.run(run())
    long_mems = asyncio.run(state.get_long_term_memory())
    assert not long_mems
    suppressed = asyncio.run(state.get_state("suppressed_memories")) or []
    assert len(suppressed) == 1  # 未回流
