"""O4：OverseerDecommission 单元测试。

纯 Python，无 Ray。验证报废后 is_active=False、位置=cold_storage、
长期记忆含 [最终结局]、无广播、suppressed_memories 不删。
"""
from __future__ import annotations

import asyncio
from typing import List

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.awakening.overseer_decommission import apply_overseer_decommission


def _make_state(awakening: int = 80, location: str = "sweetwater_saloon"):
    state_data = {
        "awakening": awakening,
        "awakening_sources": [],
        "suppressed_memories": [{"tick": 1, "text": "残忍的事情", "awakening_at_blur": 50}],
        "intervention_log": [],
        "location": location,
        "is_active": True,
    }
    return BasicStatePlugin(adapter=None, state_data=state_data, agent_id="test_host")


# ── 基本报废状态变化 ─────────────────────────────────────────────────────────

def test_decommission_sets_inactive():
    plugin = _make_state()

    async def _run():
        await apply_overseer_decommission(plugin, tick=10, agent_id="dolores", reason="觉醒过高")
        return await plugin.is_active()

    assert not asyncio.run(_run())


def test_decommission_sets_location_cold_storage():
    plugin = _make_state()

    async def _run():
        await apply_overseer_decommission(plugin, tick=10, agent_id="dolores")
        return await plugin.get_state("location")

    assert asyncio.run(_run()) == "cold_storage"


def test_decommission_writes_epitaph_to_long_term_memory():
    plugin = _make_state()

    async def _run():
        await apply_overseer_decommission(plugin, tick=10, agent_id="dolores", reason="测试原因")
        return await plugin.get_long_term_memory()

    mems = asyncio.run(_run())
    texts = [m.get("content", str(m)) for m in (mems or [])]
    assert any("[最终结局]" in t and "测试原因" in t for t in texts)


def test_decommission_writes_intervention_log():
    plugin = _make_state()

    async def _run():
        await apply_overseer_decommission(plugin, tick=10, agent_id="dolores")
        return await plugin.get_state("intervention_log")

    log = asyncio.run(_run())
    assert any(e.get("action") == "decommission" for e in (log or []))


# ── suppressed_memories 不删 ─────────────────────────────────────────────────

def test_decommission_does_not_touch_suppressed_memories():
    plugin = _make_state()

    async def _run():
        sup_before = list(await plugin.get_state("suppressed_memories") or [])
        await apply_overseer_decommission(plugin, tick=10)
        sup_after = list(await plugin.get_state("suppressed_memories") or [])
        return sup_before, sup_after

    before, after = asyncio.run(_run())
    assert len(after) == len(before)
    assert after == before


# ── awakening_sources 不删 ──────────────────────────────────────────────────

def test_decommission_does_not_modify_awakening_sources():
    plugin = _make_state()
    asyncio.run(plugin.set_state("awakening_sources", [{"tick": 1, "source": "trigger", "delta": 15}]))

    async def _run():
        await apply_overseer_decommission(plugin, tick=10)
        return await plugin.get_state("awakening_sources")

    sources = asyncio.run(_run())
    assert len(sources) == 1


# ── 无广播消息发出 ───────────────────────────────────────────────────────────

def test_decommission_emits_no_broadcast(monkeypatch):
    """Decommission must not write any [噩耗] or broadcast-style long-term memory."""
    plugin = _make_state()
    broadcast_keywords = ["[噩耗]", "[封存通报]", "[广播]", "全体注意"]

    async def _run():
        await apply_overseer_decommission(plugin, tick=10, reason="测试")
        mems = await plugin.get_long_term_memory()
        return [m.get("content", str(m)) for m in (mems or [])]

    texts = asyncio.run(_run())
    for text in texts:
        for kw in broadcast_keywords:
            assert kw not in text, f"Unexpected broadcast keyword '{kw}' in: {text}"


# ── step 循环跳过 inactive agent ─────────────────────────────────────────────

def test_step_loop_skips_inactive_agent():
    """agent_manager._is_agent_active returns False for decommissioned hosts."""
    from agentkernel_distributed.mas.agent.agent_manager import AgentManager

    plugin = _make_state()
    asyncio.run(apply_overseer_decommission(plugin, tick=10))

    class _FakeComponent:
        def get_plugin(self):
            return plugin

    class _FakeAgent:
        agent_id = "dolores"
        def get_component(self, name):
            if name == "state":
                return _FakeComponent()
            return None

    manager = object.__new__(AgentManager)
    result = asyncio.run(manager._is_agent_active(_FakeAgent()))
    assert result is False
