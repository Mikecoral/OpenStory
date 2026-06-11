import json

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
