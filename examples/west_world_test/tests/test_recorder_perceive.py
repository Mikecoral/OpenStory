"""Tests for per-agent recorder perception (R phase)."""
from __future__ import annotations

import pytest

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.recorder.structured_location_recorder import StructuredLocationRecorder
from examples.west_world_test.recorder.world_object_registry import (
    WorldObjectRegistry,
    get_object_registry,
    reset_object_registry,
)
from examples.west_world_test.worldmap.loader import Location

_LOC_ID = "sweetwater_saloon"
_LOC = Location(
    id=_LOC_ID, name="酒馆", region="sweetwater", type="interior",
    active=True, bbox=[0, 0, 0, 0], adjacency=[],
    objects=[],
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_object_registry()
    yield
    reset_object_registry()


def _make_recorder(loc=None):
    location = loc or _LOC
    llm = FakeLLM([])
    recorder = StructuredLocationRecorder(location=location, llm=llm)
    return recorder, get_object_registry()


# ─── objects_at_for_viewer (unit tests on WorldObjectRegistry) ────────────────

class TestObjectsAtForViewer:
    def test_visible_object_visible_to_all(self):
        reg = WorldObjectRegistry()
        oid = reg.create("金币堆", _LOC_ID, "system", 0, "seed", {}, hidden=False)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=0)
        assert any(r["object_id"] == oid for r in rows)

    def test_hidden_object_not_visible_by_default(self):
        reg = WorldObjectRegistry()
        oid = reg.create("暗室机关", _LOC_ID, "system", 0, "seed", {}, hidden=True)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=0)
        assert not any(r["object_id"] == oid for r in rows)

    def test_hidden_object_visible_after_discovery(self):
        reg = WorldObjectRegistry()
        oid = reg.create("暗室机关", _LOC_ID, "system", 0, "seed", {}, hidden=True)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered={oid}, viewer_awakening=0)
        assert any(r["object_id"] == oid for r in rows)

    def test_uncanny_not_revealed_below_threshold(self):
        reg = WorldObjectRegistry()
        oid = reg.create("钢琴", _LOC_ID, "system", 0, "seed", {"secret": "隐藏的悲伤"}, hidden=False)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=29)
        assert not any(r.get("_uncanny") for r in rows)

    def test_uncanny_revealed_at_threshold(self):
        reg = WorldObjectRegistry()
        oid = reg.create("钢琴", _LOC_ID, "system", 0, "seed", {"secret": "隐藏的悲伤"}, hidden=False)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=30)
        matches = [r for r in rows if r["object_id"] == oid]
        assert matches and matches[0].get("_uncanny") == "隐藏的悲伤"

    def test_destroyed_objects_excluded(self):
        reg = WorldObjectRegistry()
        oid = reg.create("旧椅子", _LOC_ID, "system", 0, "seed", {})
        reg.destroy(oid, "test", 1)
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=0)
        assert not any(r["object_id"] == oid for r in rows)

    def test_objects_from_other_locations_excluded(self):
        reg = WorldObjectRegistry()
        oid = reg.create("马鞍", "other_loc", "system", 0, "seed", {})
        rows = reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=0)
        assert not any(r["object_id"] == oid for r in rows)

    def test_does_not_mutate_registry(self):
        reg = WorldObjectRegistry()
        oid = reg.create("钢琴", _LOC_ID, "system", 0, "seed", {"secret": "秘密"}, hidden=False)
        reg.objects_at_for_viewer(_LOC_ID, viewer_discovered=set(), viewer_awakening=50)
        assert "_uncanny" not in reg.get(oid)


# ─── StructuredLocationRecorder.perceive (integration via process singleton) ──

class TestStructuredPerceive:
    def test_perceive_returns_present_agents(self):
        recorder, _ = _make_recorder()
        recorder.chunks["present_agents"] = "泰迪、梅芙"
        result = recorder.perceive("dolores", {"focus": ["present_agents"]})
        assert result.get("present_agents") == "泰迪、梅芙"

    def test_perceive_dynamic_objects_hidden_from_undiscovered_viewer(self):
        recorder, reg = _make_recorder()
        oid = reg.create("暗门", _LOC_ID, "system", 0, "seed", {}, hidden=True)
        result_no = recorder.perceive("dolores", {"discovered_ids": [], "awakening": 0})
        assert "暗门" not in result_no.get("dynamic_objects", "")

    def test_perceive_dynamic_objects_shown_after_discovery(self):
        recorder, reg = _make_recorder()
        oid = reg.create("暗门", _LOC_ID, "system", 0, "seed", {}, hidden=True)
        result_yes = recorder.perceive("maeve", {"discovered_ids": [oid], "awakening": 0})
        assert "暗门" in result_yes.get("dynamic_objects", "")

    def test_perceive_uncanny_controlled_by_awakening(self):
        recorder, reg = _make_recorder()
        reg.create("镜子", _LOC_ID, "system", 0, "seed",
                   {"secret": "映出另一个自己"}, hidden=False)
        result_low = recorder.perceive("agent_a", {"discovered_ids": [], "awakening": 10})
        result_high = recorder.perceive("agent_b", {"discovered_ids": [], "awakening": 40})
        assert "映出另一个自己" not in result_low.get("dynamic_objects", "")
        assert "映出另一个自己" in result_high.get("dynamic_objects", "")

    def test_perceive_focus_controls_returned_chunks(self):
        recorder, _ = _make_recorder()
        recorder.chunks["static_facilities"] = "酒馆设施描述"
        result = recorder.perceive("agent", {"focus": ["static_facilities"]})
        assert "static_facilities" in result
        assert "dynamic_objects" not in result

    def test_perceive_default_chunks_when_no_focus(self):
        recorder, _ = _make_recorder()
        result = recorder.perceive("agent", {})
        assert "present_agents" in result
        assert "dynamic_objects" in result

    def test_perceive_base_info_identical_for_all_agents(self):
        recorder, _ = _make_recorder()
        recorder.chunks["present_agents"] = "威廉"
        res_a = recorder.perceive("agent_a", {"discovered_ids": [], "awakening": 0})
        res_b = recorder.perceive("agent_b", {"discovered_ids": [], "awakening": 0})
        assert res_a["present_agents"] == res_b["present_agents"]
