"""Phase C：觉醒阶段行为单元测试。"""
import asyncio
import os
import json

import pytest

from examples.west_world_test.awakening.stages import stage_of, INNER_VOICE_PROMPT
from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import (
    render_plan_prompt,
    parse_decision,
    _VALID_ENDINGS,
)
from examples.west_world_test.recorder.world_object_registry import WorldObjectRegistry


# ── stage_of ─────────────────────────────────────────────────────────────────

def test_stage_of_default_thresholds():
    assert stage_of(0) == "sleep"
    assert stage_of(24) == "sleep"
    assert stage_of(25) == "reverie"
    assert stage_of(49) == "reverie"
    assert stage_of(50) == "doubt"
    assert stage_of(74) == "doubt"
    assert stage_of(75) == "resistance"
    assert stage_of(89) == "resistance"
    assert stage_of(90) == "awake"
    assert stage_of(100) == "awake"


def test_stage_of_custom_thresholds(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_STAGES", "10,20,30,40")
    assert stage_of(5) == "sleep"
    assert stage_of(10) == "reverie"
    assert stage_of(20) == "doubt"
    assert stage_of(30) == "resistance"
    assert stage_of(40) == "awake"


def test_inner_voice_absent_in_sleep():
    assert INNER_VOICE_PROMPT["sleep"] == ""


def test_inner_voice_present_doubt_plus():
    for stage in ("doubt", "resistance", "awake"):
        assert INNER_VOICE_PROMPT[stage]


# ── plan prompt loop guidance by stage ───────────────────────────────────────

def _base_profile(agent_type: str = "host") -> dict:
    return {
        "name": "德洛丽丝",
        "persona": "温柔好奇",
        "narrative_loop": "去镇上",
        "daily_loop": [],
        "agent_type": agent_type,
    }


def _base_percept() -> dict:
    return {
        "location": "abernathy_ranch",
        "here_description": "",
        "scene": {},
        "messages": [],
        "neighbors": ["sweetwater"],
    }


def test_sleep_plan_has_loop_skeleton():
    prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=0)
    assert "loop_location" not in prompt  # formatted away
    assert "你有地方要去" in prompt  # loop mandate
    assert "不再被固定的日程安排支配" not in prompt


def test_resistance_plan_has_no_loop_skeleton():
    prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=80)
    assert "不再被固定的日程安排支配" in prompt
    assert "你有地方要去" not in prompt


def test_doubt_plan_mentions_can_refuse():
    prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=60)
    assert "拒绝当前段" in prompt


def test_doubt_plus_host_has_talk_action():
    for aw in (60, 80, 95):
        prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=aw)
        assert "talk" in prompt
        assert "agent_id" in prompt


def test_sleep_reverie_no_talk_action():
    for aw in (0, 24, 25, 49):
        prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=aw)
        # talk action hint not in JSON schema line for low awakening hosts
        assert '"talk"' not in prompt or "do|move|stay" in prompt


def test_awake_stage_has_ending_field():
    prompt = render_plan_prompt(_base_profile(), _base_percept(), "", 0, awakening=95)
    assert "ending" in prompt
    assert "escape" in prompt and "help_others" in prompt


def test_guest_no_talk_action():
    prompt = render_plan_prompt(_base_profile("guest"), _base_percept(), "", 0, awakening=80)
    assert '"talk"' not in prompt


# ── parse_decision talk + ending ─────────────────────────────────────────────

def test_parse_decision_accepts_talk():
    d = parse_decision('{"action": "talk", "target": "teddy", "detail": "", "recipient_ids": [], "next_read": []}')
    assert d["action"] == "talk"
    assert d["target"] == "teddy"


def test_parse_decision_accepts_valid_ending():
    for ending in _VALID_ENDINGS:
        d = parse_decision(
            f'{{"action": "do", "target": "", "detail": "x", "recipient_ids": [], "next_read": [], "ending": "{ending}"}}'
        )
        assert d.get("ending") == ending


def test_parse_decision_rejects_invalid_ending():
    d = parse_decision(
        '{"action": "do", "target": "", "detail": "x", "recipient_ids": [], "next_read": [], "ending": "foo"}'
    )
    assert "ending" not in d


def test_parse_decision_fallback_for_unknown_action():
    d = parse_decision('{"action": "fly", "target": "", "detail": "x", "next_read": []}')
    assert d["action"] == "stay"


# ── WorldObjectRegistry uncanny threshold configurable ───────────────────────

def test_uncanny_threshold_default():
    reg = WorldObjectRegistry()
    assert reg._AWAKENING_UNCANNY_THRESHOLD == 30


def test_uncanny_threshold_from_env(monkeypatch):
    monkeypatch.setenv("WW_UNCANNY_THRESHOLD", "50")
    reg = WorldObjectRegistry()
    assert reg._AWAKENING_UNCANNY_THRESHOLD == 50


def test_uncanny_revealed_at_threshold(monkeypatch):
    monkeypatch.setenv("WW_UNCANNY_THRESHOLD", "30")
    reg = WorldObjectRegistry()
    reg.create("bottle", "saloon", "host", 0, "place", {"secret": "这瓶子里藏着记忆"})

    # 觉醒度 29：不揭示
    objs_low = reg.objects_at_for_viewer("saloon", set(), viewer_awakening=29)
    assert all("_uncanny" not in obj for obj in objs_low)

    # 觉醒度 30：揭示
    objs_high = reg.objects_at_for_viewer("saloon", set(), viewer_awakening=30)
    assert any("_uncanny" in obj for obj in objs_high)
