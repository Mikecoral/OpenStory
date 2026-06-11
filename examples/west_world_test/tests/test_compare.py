from examples.west_world_test.core.compare import _is_relevant, run_comparison
from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


def test_run_comparison_produces_records_and_summary():
    events = [Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})]
    probes = [Probe.from_dict({"id": "q9", "kind": "state", "text": "几个装酒的杯子?", "field": "glasses_filled", "answer_type": "int"})]
    result = run_comparison(events, probes, {"text": lambda: TextRepresentation(FakeLLM(["record", "1"]))})
    assert result["records"][0]["correct"] is True
    assert result["records"][0]["had_relevant_event"] is True
    assert result["summary"]["text"]["accuracy"] == 1.0


def test_relevance_uses_explicit_affected_probe_ids():
    event = Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})
    intact = Probe.from_dict({"id": "q1", "kind": "state", "text": "x", "field": "glasses_intact"})
    filled = Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled"})
    assert _is_relevant(intact, event) is False
    assert _is_relevant(filled, event) is True
