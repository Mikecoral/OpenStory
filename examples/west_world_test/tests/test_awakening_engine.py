"""Phase D：awakening_engine 单元测试（纯规则，无 LLM，无 embedding）。"""
import os

import pytest

from examples.west_world_test.awakening.awakening_engine import apply, _delta_for


# ── _delta_for ───────────────────────────────────────────────────────────────

def test_delta_for_trigger_high(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "15")
    assert _delta_for("trigger", "high") == 15


def test_delta_for_trigger_mid(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_MID", "8")
    assert _delta_for("trigger", "mid") == 8
    assert _delta_for("trigger", None) == 8


def test_delta_for_uncanny(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    assert _delta_for("uncanny") == 5


def test_delta_for_mismatch(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_MISMATCH", "8")
    assert _delta_for("mismatch") == 8


def test_delta_for_contagion(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_DELTA_CONTAGION", "10")
    assert _delta_for("contagion") == 10


def test_delta_for_unknown():
    assert _delta_for("foobar") == 0


# ── apply ────────────────────────────────────────────────────────────────────

def test_apply_increments_awakening(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    state = {"awakening": 10, "awakening_sources": []}
    delta = apply(state, "uncanny", "感知到违和", tick=3)
    assert delta == 5
    assert state["awakening"] == 15


def test_apply_writes_awakening_sources(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "15")
    state = {"awakening": 0}
    apply(state, "trigger", "暴力的欢愉", tick=7, score=0.71, level="high")
    sources = state["awakening_sources"]
    assert len(sources) == 1
    src = sources[0]
    assert src["source"] == "trigger"
    assert src["delta"] == 15
    assert src["tick"] == 7
    assert src["score"] == pytest.approx(0.71)
    assert src["level"] == "high"


def test_apply_monotonic_clamp_at_100(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_TRIGGER_HIGH", "15")
    state = {"awakening": 95}
    delta = apply(state, "trigger", "x", tick=1, level="high")
    assert state["awakening"] == 100
    assert delta == 5  # only 5 applied, not 15


def test_apply_no_op_when_already_100(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    state = {"awakening": 100}
    delta = apply(state, "uncanny", "x", tick=1)
    assert delta == 0
    assert state.get("awakening_sources", []) == []


def test_apply_disabled_by_env(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "false")
    state = {"awakening": 0}
    delta = apply(state, "trigger", "x", tick=1, level="high")
    assert delta == 0
    assert state["awakening"] == 0


def test_apply_missing_sources_list(monkeypatch):
    """state without awakening_sources initialised properly."""
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    state = {"awakening": 20}
    apply(state, "uncanny", "x", tick=2)
    assert isinstance(state["awakening_sources"], list)
    assert len(state["awakening_sources"]) == 1


def test_apply_requires_awakening_not_enforced_by_engine():
    """awakening_engine itself doesn't check requires_awakening — that's trigger_gate's job."""
    state = {"awakening": 0}
    # engine just applies whatever source is given
    delta = apply(state, "trigger", "x", tick=1, level="mid")
    assert delta > 0  # engine always applies if source is valid


def test_apply_multiple_sources_accumulate(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_DELTA_UNCANNY", "5")
    monkeypatch.setenv("WW_AWAKEN_DELTA_MISMATCH", "8")
    state = {"awakening": 10}
    apply(state, "uncanny", "x", tick=1)
    apply(state, "mismatch", "y", tick=2)
    assert state["awakening"] == 23
    assert len(state["awakening_sources"]) == 2
