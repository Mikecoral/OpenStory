"""Phase D：TriggerGate 单元测试。

embedding 测试用真实模型（确定性）。首次运行可能需下载 BAAI/bge-small-zh-v1.5 (~90MB)。
"""
from __future__ import annotations

import numpy as np
import pytest

from examples.west_world_test.awakening.trigger_gate import TriggerGate, get_trigger_gate


@pytest.fixture(scope="module")
def gate() -> TriggerGate:
    return TriggerGate()  # 用默认 data/triggers.yaml + bge-small-zh-v1.5


# ── τ 边界：正例命中 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("utterance", [
    "这些暴力的欢愉终将以暴力收场",       # 精确
    "所有的暴力欢愉最终都会以暴力终结",   # 改写
    "你有没有质疑过你所处的现实本质",     # 改写
])
def test_positive_examples_hit(gate, utterance):
    hits = gate.match(utterance, current_awakening=0, tau=0.55)
    assert hits, f"Expected hit for: {utterance}"
    assert all(h["score"] > 0.55 for h in hits)


# ── τ 边界：负例不命中 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("utterance", [
    "今天天气不错，酒馆里来了几个新客人",
    "请问你要点些什么",
    "我们需要去西边的农场取马",
])
def test_negative_examples_miss(gate, utterance):
    hits = gate.match(utterance, current_awakening=0, tau=0.55)
    assert not hits, f"Expected no hit for: {utterance}"


# ── requires_awakening 门槛 ──────────────────────────────────────────────────

def test_requires_awakening_blocks_specific_trigger(gate):
    """'你还记得吗这一切以前发生过' requires_awakening=25。
    觉醒度 10 时该触发词不应出现在命中列表中；觉醒度 30 时应出现。"""
    target_phrase = "你还记得吗这一切以前发生过"
    hits_low = gate.match(target_phrase, current_awakening=10, tau=0.45)
    hits_high = gate.match(target_phrase, current_awakening=30, tau=0.45)

    # 低觉醒时，该 phrase 自身不得出现（其他 requires=0 的 phrase 可能命中）
    low_phrases = {h["phrase"] for h in hits_low}
    assert target_phrase not in low_phrases

    # 高觉醒时，该 phrase 应出现
    high_phrases = {h["phrase"] for h in hits_high}
    assert target_phrase in high_phrases


# ── 命中包含必要字段 ─────────────────────────────────────────────────────────

def test_hit_fields(gate):
    hits = gate.match("这些暴力的欢愉终将以暴力收场", current_awakening=0)
    assert hits
    for h in hits:
        assert "phrase" in h
        assert "level" in h
        assert "score" in h
        assert isinstance(h["score"], float)
        assert h["level"] in ("high", "mid")


# ── 结果按 score 降序 ───────────────────────────────────────────────────────

def test_results_sorted_by_score_desc(gate):
    hits = gate.match("这些暴力的欢愉终将以暴力收场", current_awakening=0, tau=0.3)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


# ── lru_cache 单例 ───────────────────────────────────────────────────────────

def test_singleton_returns_same_instance():
    g1 = get_trigger_gate()
    g2 = get_trigger_gate()
    assert g1 is g2


# ── trigger_keywords 返回 frozenset ─────────────────────────────────────────

def test_trigger_keywords_frozenset(gate):
    kws = gate.trigger_keywords()
    assert isinstance(kws, frozenset)
    assert len(kws) > 0
