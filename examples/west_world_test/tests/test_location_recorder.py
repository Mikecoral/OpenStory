"""Tests for LocationRecorder（FakeLLM，无需 Ray/Redis）。"""
import json

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.recorder.location_recorder import LocationRecorder
from examples.west_world_test.worldmap.loader import Location

SALOON = Location(
    id="sweetwater_saloon", name="甜水镇酒馆", region="sweetwater", type="interior",
    active=True, bbox=[0, 0, 0, 0], adjacency=["sweetwater"],
    description="昏黄的灯光下摆着吧台和几张牌桌。",
    objects=[
        {"name": "自动演奏钢琴", "note": "循环播放老歌"},
        {"name": "旧照片", "hidden": True, "secret": "照片上是现代都市夜景"},
    ],
    default_occupants=["maeve"],
)


def make_recorder(replies=None):
    return LocationRecorder(location=SALOON, llm=FakeLLM(replies or []))


def test_init_builds_chunks_from_location():
    rec = make_recorder()
    assert "吧台" in rec.chunks["static_facilities"]
    assert "钢琴" in rec.chunks["static_facilities"]
    assert "旧照片" not in rec.chunks["static_facilities"]      # hidden 不进可见块
    assert "现代都市" in rec.chunks["hidden_notes"]
    assert "maeve" in rec.chunks["present_agents"]


def test_read_returns_requested_chunks_and_never_hidden():
    rec = make_recorder()
    out = rec.read("dolores", ["present_agents", "recent_events", "hidden_notes"])
    assert set(out) == {"present_agents", "recent_events"}      # hidden_notes 被剥除
    out2 = rec.read("dolores", ["static_facilities"])
    assert "吧台" in out2["static_facilities"]


def test_enter_and_leave_update_presence():
    rec = make_recorder()
    desc = rec.agent_enter("dolores")
    assert "吧台" in desc and "钢琴" in desc                    # 初见描述含可见物件
    assert "dolores" in rec.chunks["present_agents"]
    rec.agent_leave("dolores")
    assert "dolores" not in rec.chunks["present_agents"]


JUDGE_PICK_PHOTO = json.dumps({
    "permission": True, "reason": "",
    "private_feedback": "你捡起照片：照片上是现代都市夜景。",
    "broadcast_level": "none", "event_summary": "",
}, ensure_ascii=False)

JUDGE_BREAK_GLASS = json.dumps({
    "permission": True, "reason": "",
    "private_feedback": "杯子在你手里碎了。",
    "broadcast_level": "location", "event_summary": "有人打碎了一只酒杯。",
}, ensure_ascii=False)


def test_submit_action_secret_leaks_only_via_private_feedback():
    rec = make_recorder([JUDGE_PICK_PHOTO])
    result = rec.submit_action("dolores", "偷偷捡起角落里的旧照片")
    assert result["permission"] is True
    assert "现代都市" in result["private_feedback"]
    assert rec._pending_actions[0]["broadcast_level"] == "none"
    # 公开块此刻仍无泄露
    assert "现代都市" not in json.dumps(rec.read("teddy", list(rec.chunks)), ensure_ascii=False)


def test_submit_action_broadcast_queues_event():
    rec = make_recorder([JUDGE_BREAK_GLASS])
    result = rec.submit_action("maeve", "把酒杯摔在地上")
    assert result["broadcast_level"] == "location"
    assert rec._pending_actions[0]["event_summary"]


def test_submit_action_invalid_json_retries_then_degrades():
    rec = make_recorder(["不是JSON", "还不是JSON"])
    result = rec.submit_action("teddy", "推开后门")
    assert result["permission"] is True          # 降级：允许
    assert result["private_feedback"] == ""      # 降级：无反馈
    assert result["broadcast_level"] == "none"   # 降级：不广播
    assert len(rec.llm.calls) == 2               # 重试了一次


UPDATE_OK = json.dumps({
    "dynamic_objects": "地上有酒杯碎片。",
    "present_agents": "maeve、teddy",
    "recent_events": ["有人打碎了一只酒杯。"],
}, ensure_ascii=False)


def test_tick_update_merges_pending_and_clears_queue():
    rec = make_recorder([JUDGE_BREAK_GLASS, UPDATE_OK])
    rec.submit_action("maeve", "把酒杯摔在地上")
    rec.tick_update(tick=3)
    assert "碎片" in rec.chunks["dynamic_objects"]
    assert rec.chunks["recent_events"] == ["有人打碎了一只酒杯。"]
    assert rec._pending_actions == []
    assert len(rec.llm.calls) == 2          # 裁决 1 次 + 更新 1 次


def test_tick_update_no_pending_skips_llm():
    rec = make_recorder()
    rec.tick_update(tick=1)
    assert rec.llm.calls == []


def test_tick_update_failure_keeps_old_state():
    rec = make_recorder([JUDGE_BREAK_GLASS, "坏输出", "又坏"])
    rec.submit_action("maeve", "把酒杯摔在地上")
    before = dict(rec.chunks)
    rec.tick_update(tick=3)
    assert rec.chunks["dynamic_objects"] == before["dynamic_objects"]   # 保留旧状态
    assert rec._pending_actions == []                                   # 队列仍清空


def test_recent_events_rolling_window():
    rec = make_recorder()
    rec.chunks["recent_events"] = [f"事件{i}" for i in range(10)]
    update = json.dumps({"dynamic_objects": "x", "present_agents": "y",
                         "recent_events": [f"事件{i}" for i in range(10)] + ["新事件"]}, ensure_ascii=False)
    rec.llm = type(rec.llm)([JUDGE_BREAK_GLASS, update])
    rec.submit_action("maeve", "把酒杯摔在地上")
    rec.tick_update(tick=4)
    assert len(rec.chunks["recent_events"]) == 10
    assert rec.chunks["recent_events"][-1] == "新事件"
