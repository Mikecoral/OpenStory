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
