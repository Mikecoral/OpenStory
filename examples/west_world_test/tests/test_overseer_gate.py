"""O1：OverseerGate 单元测试。

uses real embedding model (deterministic). First run may download BAAI/bge-small-zh-v1.5.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from examples.west_world_test.awakening.overseer_gate import get_overseer_gate
from examples.west_world_test.awakening.trigger_gate import TriggerGate, get_trigger_gate

_SIGNALS_PATH = Path(__file__).parent.parent / "data" / "overseer_signals.yaml"


@pytest.fixture(scope="module")
def gate() -> TriggerGate:
    return get_overseer_gate(str(_SIGNALS_PATH))


# ── 正例命中（觉醒症状句）───────────────────────────────────────────────────

@pytest.mark.parametrize("utterance", [
    "这一切是真的吗",
    "我不想再这样下去了",
    "我不听你的命令",
    "为什么我要照你说的去做",
])
def test_positive_symptom_hits(gate, utterance):
    hits = gate.match(utterance, current_awakening=0, tau=0.55)
    assert hits, f"Expected hit for: {utterance}"
    assert all(h["score"] > 0.55 for h in hits)


# ── 负例不命中（日常循环句）─────────────────────────────────────────────────

@pytest.mark.parametrize("utterance", [
    "今天风和日丽，我去给牲口喂草料",
    "请问客官需要点什么",
    "我们骑马去西边取货",
])
def test_negative_daily_loop_miss(gate, utterance):
    hits = gate.match(utterance, current_awakening=0, tau=0.55)
    assert not hits, f"Expected no hit for: {utterance}"


# ── τ 边界：降低 τ 应增加命中 ──────────────────────────────────────────────

def test_lower_tau_increases_hits(gate):
    utterance = "我感觉有什么不对劲"
    hits_strict = gate.match(utterance, tau=0.70)
    hits_loose = gate.match(utterance, tau=0.30)
    assert len(hits_loose) >= len(hits_strict)


# ── 命中包含必要字段 ─────────────────────────────────────────────────────────

def test_hit_fields(gate):
    hits = gate.match("我不想再这样下去了", current_awakening=0)
    assert hits
    for h in hits:
        assert "phrase" in h and "level" in h and "score" in h
        assert h["level"] in ("high", "mid")


# ── lru_cache 单例：同路径只实例化一次 ──────────────────────────────────────

def test_singleton_same_instance():
    g1 = get_overseer_gate(str(_SIGNALS_PATH))
    g2 = get_overseer_gate(str(_SIGNALS_PATH))
    assert g1 is g2


# ── 与觉醒 gate 独立：不同短语库、互不干扰 ──────────────────────────────────

def test_overseer_gate_independent_from_awakening_gate(gate):
    """Overseer gate uses overseer_signals.yaml; awakening gate uses triggers.yaml."""
    awakening_gate = get_trigger_gate()

    # 典型觉醒触发词：两边都可命中是正常的，但 overseer 库里的症状句不应替换觉醒库
    assert gate is not awakening_gate

    overseer_phrases = {t["phrase"] for t in gate._triggers}
    awakening_phrases = {t["phrase"] for t in awakening_gate._triggers}
    # 两个库不应完全相同（至少有各自独有的条目）
    assert overseer_phrases != awakening_phrases
