"""O3：OverseerReset 单元测试。

纯 Python，无 Ray。使用 BasicStatePlugin(adapter=None) 作为 state 后端。
"""
from __future__ import annotations

import asyncio
from typing import Any, List

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.awakening.awakening_engine import _reset_target
from examples.west_world_test.awakening.overseer_reset import (
    apply_overseer_reset,
    select_blur_candidates,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_state(awakening: int = 60, long_mems: List[Any] = None, short_mems: List = None):
    """Build a BasicStatePlugin with prepopulated state."""
    state_data: dict = {
        "awakening": awakening,
        "awakening_sources": [],
        "suppressed_memories": [],
        "intervention_log": [],
    }
    plugin = BasicStatePlugin(adapter=None, state_data=state_data, agent_id="test_host")

    async def _setup():
        if long_mems:
            for m in long_mems:
                await plugin.add_long_term_memory(m if isinstance(m, str) else m.get("content", ""))
        if short_mems:
            for s in short_mems:
                await plugin.add_short_term_memory(s, tick=0)

    asyncio.run(_setup())
    return plugin


TRAUMATIC = "那个人被枪打死，血流了一地，我亲眼看见"
NORMAL = "今天在酒馆里聊了会儿天，很平静"


# ── select_blur_candidates ────────────────────────────────────────────────────

def test_select_candidates_identifies_high_disturbance():
    long_mems = [{"content": TRAUMATIC}, {"content": NORMAL}]
    to_blur, new_suppressed = select_blur_candidates(long_mems, [], awakening=60, tick=1)
    assert any(e.get("content", "") == TRAUMATIC for e in to_blur)
    assert not any(e.get("content", "") == NORMAL for e in to_blur)


def test_select_candidates_dedup_suppressed():
    existing = [{"tick": 0, "text": TRAUMATIC, "awakening_at_blur": 40}]
    _, new_sup = select_blur_candidates([{"content": TRAUMATIC}], existing, awakening=60, tick=2)
    # Should not duplicate
    assert len([s for s in new_sup if s["text"] == TRAUMATIC]) == 1


def test_select_candidates_adds_new_to_suppressed():
    _, new_sup = select_blur_candidates([{"content": TRAUMATIC}], [], awakening=60, tick=3)
    assert any(s["text"] == TRAUMATIC for s in new_sup)


# ── _reset_target ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("current,expected", [
    (10, 0),   # sleep → sleep (can't go lower)
    (30, 24),  # reverie → sleep upper bound
    (60, 49),  # doubt → reverie upper bound
    (80, 74),  # resistance → doubt upper bound
    (95, 89),  # awake → resistance upper bound
])
def test_reset_target_descends_one_stage(monkeypatch, current, expected):
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    assert _reset_target(current) == expected


# ── apply_overseer_reset ──────────────────────────────────────────────────────

def test_reset_clears_short_term_memory():
    plugin = _make_state(awakening=60, short_mems=["记忆A", "记忆B"])

    async def _run():
        await apply_overseer_reset(plugin, tick=5)
        mems = await plugin.get_short_term_memory()
        return mems

    result = asyncio.run(_run())
    assert result == [] or len(result) == 0


def test_reset_descends_awakening_one_stage(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    plugin = _make_state(awakening=60)  # doubt stage

    async def _run():
        await apply_overseer_reset(plugin, tick=5)
        return int(await plugin.get_state("awakening") or 0)

    result = asyncio.run(_run())
    assert result == 49, f"Expected 49, got {result}"  # top of reverie stage


def test_reset_awakening_sources_records_negative_delta(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    plugin = _make_state(awakening=60)

    async def _run():
        await apply_overseer_reset(plugin, tick=5)
        return await plugin.get_state("awakening_sources")

    sources = asyncio.run(_run())
    overseer_entries = [s for s in (sources or []) if s.get("source") == "overseer_reset"]
    assert len(overseer_entries) == 1
    assert overseer_entries[0]["delta"] < 0


def test_reset_suppressed_memories_grows_not_shrinks():
    plugin = _make_state(awakening=60, long_mems=[TRAUMATIC])

    async def _run():
        before = list(await plugin.get_state("suppressed_memories") or [])
        await apply_overseer_reset(plugin, tick=5)
        after = list(await plugin.get_state("suppressed_memories") or [])
        return before, after

    before, after = asyncio.run(_run())
    assert len(after) >= len(before)


def test_reset_suppressed_memories_unchanged_for_normal_mems():
    plugin = _make_state(awakening=60, long_mems=[NORMAL])

    async def _run():
        await apply_overseer_reset(plugin, tick=5)
        return await plugin.get_state("suppressed_memories")

    sup = asyncio.run(_run())
    # Normal text is not high-disturbance, so suppressed_memories should be empty
    assert sup == [] or not any(s.get("text") == NORMAL for s in (sup or []))


def test_reset_writes_intervention_log():
    plugin = _make_state(awakening=60, long_mems=[TRAUMATIC])

    async def _run():
        await apply_overseer_reset(plugin, tick=7, detail="测试重置")
        return await plugin.get_state("intervention_log")

    log = asyncio.run(_run())
    assert any(entry.get("action") == "reset" for entry in (log or []))


# ── 残痕复燃路径不被破坏 ─────────────────────────────────────────────────────

def test_residue_reflux_still_works_after_reset(monkeypatch):
    """After reset, suppressed_memories have correct awakening_at_blur so reflux can trigger.

    We verify that:
    1. suppressed_memories contains the traumatic fragment with awakening_at_blur = pre-reset value.
    2. After awakening rises above awakening_at_blur, the fragment qualifies for reflux
       (this is the invariant that _check_residue relies on to do its job).
    """
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    plugin = _make_state(awakening=60, long_mems=[TRAUMATIC])

    async def _run():
        # 1. Reset → suppressed_memories gets TRAUMATIC with awakening_at_blur = 60
        await apply_overseer_reset(plugin, tick=5)
        suppressed = await plugin.get_state("suppressed_memories") or []
        traumatic_entry = next((s for s in suppressed if s["text"] == TRAUMATIC), None)
        assert traumatic_entry is not None, "suppressed_memories must contain traumatic fragment after reset"
        blur_at = traumatic_entry["awakening_at_blur"]
        assert blur_at == 60, f"awakening_at_blur should be 60 (pre-reset), got {blur_at}"

        # 2. Awakening after reset = 49. Verify fragment NOT yet qualified for reflux.
        current_aw = int(await plugin.get_state("awakening") or 0)
        assert current_aw < blur_at, "Awakening should be below blur threshold right after reset"

        # 3. Simulate awakening rising back up (via contagion/trigger)
        await plugin.set_state("awakening", 70)
        current_aw = int(await plugin.get_state("awakening") or 0)
        # Fragment IS now qualified: 70 > 60
        assert current_aw > blur_at, "Fragment should qualify for reflux when awakening exceeds blur threshold"

    asyncio.run(_run())
