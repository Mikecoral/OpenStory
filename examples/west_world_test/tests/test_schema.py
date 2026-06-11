import json
import os

from examples.west_world_test.core.oracle import OracleState
from examples.west_world_test.core.schema import Event, Probe, load_events, load_probes


def test_event_from_dict_defaults_visibility_public():
    event = Event.from_dict({"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"})
    assert event.tick == 1
    assert event.actor == "酒保"
    assert event.action == "pour_whiskey"
    assert event.target == "glass"
    assert event.visibility == "public"


def test_event_keeps_hidden_visibility():
    event = Event.from_dict(
        {"tick": 2, "actor": "黑衣人", "action": "pick_up_photo", "target": "photo", "visibility": "hidden", "id": "e2"}
    )
    assert event.visibility == "hidden"
    assert event.id == "e2"


def test_event_and_probe_keep_explicit_evaluation_metadata():
    event = Event.from_dict({"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})
    probe = Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled", "score_group": "visual_physical"})
    assert event.affected_probe_ids == ("q9",)
    assert probe.score_group == "visual_physical"


def test_probe_from_dict_state_kind():
    probe = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?", "field": "glasses_intact", "answer_type": "int"})
    assert probe.kind == "state"
    assert probe.field == "glasses_intact"
    assert probe.answer_type == "int"
    assert probe.equals is None


def test_load_events_and_probes_from_jsonl(tmp_path):
    events_path = tmp_path / "script.jsonl"
    events_path.write_text(json.dumps({"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}) + "\n", encoding="utf-8")
    probes_path = tmp_path / "probes.jsonl"
    probes_path.write_text(json.dumps({"id": "q1", "kind": "state", "text": "x", "field": "piano", "answer_type": "str"}) + "\n", encoding="utf-8")
    events = load_events(str(events_path))
    probes = load_probes(str(probes_path))
    assert len(events) == 1 and events[0].action == "pour_whiskey"
    assert len(probes) == 1 and probes[0].id == "q1"


def test_real_data_files_load_and_are_consistent():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    events = load_events(os.path.join(data_dir, "script.jsonl"))
    probes = load_probes(os.path.join(data_dir, "probes.jsonl"))
    assert len(events) >= 8
    assert len(probes) >= 8
    oracle = OracleState()
    for event in sorted(events, key=lambda item: item.tick):
        oracle.apply(event)
    event_ids = {event.id for event in events if event.id}
    probe_ids = {probe.id for probe in probes}
    for probe in probes:
        assert probe.score_group in {"visual_physical", "hidden_knowledge"}
        if probe.kind == "state":
            oracle.answer(probe)
        else:
            assert probe.fact_event_id in event_ids
    for event in events:
        assert event.affected_probe_ids
        assert set(event.affected_probe_ids) <= probe_ids
