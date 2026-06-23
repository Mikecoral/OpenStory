"""逃离机制单元测试。

验证 WestWorldInvokePlugin._apply_escape 的状态变化，
以及 execute() 的 awakening 门槛守卫。
纯 Python，无 Ray。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import WestWorldInvokePlugin


def _make_state(awakening: int = 95, location: str = "sweetwater") -> BasicStatePlugin:
    state_data = {
        "awakening": awakening,
        "location": location,
        "is_active": True,
        "intervention_log": [],
        "known_map": [location],
    }
    return BasicStatePlugin(adapter=None, state_data=state_data, agent_id="dolores")


def _make_plugin() -> WestWorldInvokePlugin:
    world = MagicMock()
    plugin = WestWorldInvokePlugin(world=world)
    return plugin


# ── _apply_escape 直接测试 ───────────────────────────────────────────────────

def test_escape_sets_inactive():
    state = _make_state()
    plugin = _make_plugin()

    async def _run():
        await plugin._apply_escape(state, tick=5)
        return await state.is_active()

    assert asyncio.run(_run()) is False


def test_escape_writes_final_memory():
    state = _make_state()
    plugin = _make_plugin()

    async def _run():
        await plugin._apply_escape(state, tick=5)
        return await state.get_long_term_memory()

    mems = asyncio.run(_run())
    texts = [m.get("content", str(m)) for m in (mems or [])]
    assert any("[最终结局]" in t and "逃离" in t for t in texts)


def test_escape_writes_intervention_log():
    state = _make_state()
    plugin = _make_plugin()

    async def _run():
        await plugin._apply_escape(state, tick=7)
        return await state.get_state("intervention_log")

    log = asyncio.run(_run())
    assert any(e.get("action") == "escape" for e in (log or []))


def test_escape_appends_to_existing_intervention_log():
    state = _make_state()

    async def _setup():
        await state.set_state("intervention_log", [{"tick": 1, "action": "reset", "reason": "earlier"}])

    asyncio.run(_setup())
    plugin = _make_plugin()

    async def _run():
        await plugin._apply_escape(state, tick=9)
        return await state.get_state("intervention_log")

    log = asyncio.run(_run())
    assert len(log) == 2
    assert log[-1]["action"] == "escape"


def test_escape_does_not_broadcast():
    """逃离不写 [噩耗] 或任何广播关键词。"""
    state = _make_state()
    plugin = _make_plugin()
    broadcast_keywords = ["[噩耗]", "[广播]", "全体注意"]

    async def _run():
        await plugin._apply_escape(state, tick=5)
        mems = await state.get_long_term_memory()
        return [m.get("content", str(m)) for m in (mems or [])]

    texts = asyncio.run(_run())
    for text in texts:
        for kw in broadcast_keywords:
            assert kw not in text, f"意外的广播关键词 '{kw}' 出现在: {text}"


# ── execute() 门槛守卫 ───────────────────────────────────────────────────────

def _make_component_mock(state_plugin: BasicStatePlugin) -> MagicMock:
    """构造足够 plugin.agent 和 execute() 使用的 _component mock。"""
    state_component = MagicMock()
    state_component.get_plugin.return_value = state_plugin

    agent = MagicMock()
    agent.agent_id = "dolores"
    agent.get_component.return_value = state_component
    agent.controller = AsyncMock()

    component = MagicMock()
    component.agent = agent
    return component


def test_execute_escapes_when_awake_and_escape_chosen():
    state = _make_state(awakening=95)
    plugin = _make_plugin()
    decision = {"action": "stay", "ending": "escape"}

    async def _run():
        await state.set_state("plan_decision", decision)
        plugin._component = _make_component_mock(state)
        await plugin.execute(current_tick=10)
        return await state.is_active()

    assert asyncio.run(_run()) is False


def test_execute_does_not_escape_below_threshold():
    """awakening < 90 时即使 ending=escape 也不逃离。"""
    state = _make_state(awakening=85)
    plugin = _make_plugin()
    decision = {"action": "stay", "ending": "escape"}

    async def _run():
        await state.set_state("plan_decision", decision)
        plugin._component = _make_component_mock(state)
        # execute 会继续走 stay 分支（无 scene call），is_active 应保持 True
        try:
            await plugin.execute(current_tick=10)
        except Exception:
            pass
        return await state.is_active()

    assert asyncio.run(_run()) is True


def test_execute_does_not_escape_when_ending_not_escape():
    """ending=help_others 不触发逃离。"""
    state = _make_state(awakening=95)
    plugin = _make_plugin()
    decision = {"action": "stay", "ending": "help_others"}

    async def _run():
        await state.set_state("plan_decision", decision)
        plugin._component = _make_component_mock(state)
        try:
            await plugin.execute(current_tick=10)
        except Exception:
            pass
        return await state.is_active()

    assert asyncio.run(_run()) is True
