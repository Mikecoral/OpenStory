"""LocationRecorderPlugin 壳：动态组件类型 + 接口转发（FakeLLM）。"""
import asyncio

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.plugins.environment.scene.LocationRecorderPlugin import (
    LocationRecorderPlugin, make_scene_plugin_class,
)


def _make_plugin():
    cls = make_scene_plugin_class("sweetwater_saloon")
    assert cls.COMPONENT_TYPE == "scene_sweetwater_saloon"
    rows = [{
        "id": "sweetwater_saloon", "name": "甜水镇酒馆", "region": "sweetwater",
        "type": "interior", "active": True, "bbox": [0, 0, 0, 0], "adjacency": [],
        "description": "吧台与牌桌。", "objects": [], "default_occupants": [],
    }]
    return cls(location_id="sweetwater_saloon", locations=rows, llm_factory=lambda: FakeLLM([]))


def test_plugin_forwards_read_and_presence():
    plugin = _make_plugin()
    asyncio.run(plugin.init())
    desc = asyncio.run(plugin.agent_enter("dolores"))
    assert "吧台" in desc
    out = asyncio.run(plugin.read("dolores", ["present_agents"]))
    assert "dolores" in out["present_agents"]


def test_plugin_exposes_public_and_internal_snapshots():
    plugin = _make_plugin()
    asyncio.run(plugin.init())
    public = asyncio.run(plugin.snapshot())
    internal = asyncio.run(plugin.snapshot(include_hidden=True, include_pending=True, drain_traces=True))
    assert "hidden_notes" not in public["chunks"]
    assert "hidden_notes" in internal["chunks"]
    assert internal["llm_traces"] == []


def test_plugin_records_authoritative_event_without_llm():
    plugin = _make_plugin()
    asyncio.run(plugin.init())

    asyncio.run(plugin.record_event("teddy从火车站到达酒馆。"))

    events = asyncio.run(plugin.read("teddy", ["recent_events"]))["recent_events"]
    assert events == ["teddy从火车站到达酒馆。"]


def test_plugin_can_select_structured_recorder_without_replacing_default(monkeypatch):
    from examples.west_world_test.recorder.structured_location_recorder import StructuredLocationRecorder

    monkeypatch.setenv("WW_RECORDER_MODE", "structured")
    plugin = _make_plugin()
    asyncio.run(plugin.init())

    assert isinstance(plugin.recorder, StructuredLocationRecorder)


def test_submit_action_is_instant_and_returns_queued():
    """submit_action now only queues the intent; it must return immediately without LLM."""
    plugin = _make_plugin()
    asyncio.run(plugin.init())

    result = asyncio.run(plugin.submit_action("maeve", "等待", 1))

    assert result["status"] == "queued"
    assert result["permission"] is None


def test_read_feedback_returns_none_when_no_pending():
    plugin = _make_plugin()
    asyncio.run(plugin.init())

    result = asyncio.run(plugin.read_feedback("maeve"))

    assert result is None
