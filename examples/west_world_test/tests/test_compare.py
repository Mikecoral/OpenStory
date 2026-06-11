from examples.west_world_test.core.compare import _is_relevant, run_comparison
from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


def test_run_comparison_produces_records_and_summary():
    events = [Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})]
    probes = [Probe.from_dict({"id": "q9", "kind": "state", "text": "几个装酒的杯子?", "field": "glasses_filled", "answer_type": "int"})]
    result = run_comparison(events, probes, {"text": lambda: TextRepresentation(FakeLLM(["0", "record", "1"]))})
    assert result["records"][0]["tick"] == 0
    assert result["records"][0]["evaluation_role"] == "initial"
    assert result["records"][1]["correct"] is True
    assert result["records"][1]["had_relevant_event"] is True
    assert result["summary"]["text"]["accuracy"] == 1.0
    assert result["summary"]["text"]["initial_accuracy"] == 1.0
    assert result["summary"]["text"]["affected_accuracy"] == 1.0


def test_relevance_uses_explicit_affected_probe_ids():
    event = Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})
    intact = Probe.from_dict({"id": "q1", "kind": "state", "text": "x", "field": "glasses_intact"})
    filled = Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled"})
    assert _is_relevant(intact, event) is False
    assert _is_relevant(filled, event) is True


def test_comparison_marks_persistence_after_a_probe_was_affected():
    events = [
        Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]}),
        Event.from_dict({"id": "e2", "tick": 2, "actor": "酒保", "action": "stop_piano", "target": "piano", "affected_probe_ids": ["q5"]}),
    ]
    probes = [Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled", "answer_type": "int"})]
    result = run_comparison(events, probes, {"text": lambda: TextRepresentation(FakeLLM(["0", "s1", "1", "s2", "1"]))})
    assert [record["evaluation_role"] for record in result["records"]] == ["initial", "affected", "persistence"]
    assert result["summary"]["text"]["persistence_accuracy"] == 1.0


def test_comparison_streams_each_record_to_callback():
    streamed = []
    events = [Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})]
    probes = [Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled", "answer_type": "int"})]
    result = run_comparison(events, probes, {"text": lambda: TextRepresentation(FakeLLM(["0", "s1", "1"]))}, on_record=streamed.append)
    assert streamed == result["records"]
