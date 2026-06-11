from examples.west_world_test.core.compare import run_comparison
from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


def test_run_comparison_produces_records_and_summary():
    events = [Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"})]
    probes = [Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?", "field": "glasses_intact", "answer_type": "int"})]
    result = run_comparison(events, probes, {"text": lambda: TextRepresentation(FakeLLM(["record", "2"]))})
    assert result["records"][0]["correct"] is True
    assert result["records"][0]["had_relevant_event"] is True
    assert result["summary"]["text"]["accuracy"] == 1.0
