import json

from examples.west_world_test.eval.run_archived_comparison import TraceArchive, _write_reports
from examples.west_world_test.core.schema import Event, Probe


def test_trace_archive_saves_full_text_request_and_response(tmp_path):
    trace = TraceArchive(tmp_path / "model_traces" / "all_calls.jsonl")
    trace({"call_type": "text_chat", "prompt": "完整请求", "response": "完整输出"})
    row = json.loads((tmp_path / "model_traces" / "all_calls.jsonl").read_text(encoding="utf-8"))
    assert row["prompt"] == "完整请求"
    assert row["response"] == "完整输出"
    assert row["sequence"] == 1


def test_global_report_separates_visual_and_hidden_scores(tmp_path):
    event = Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})
    probes = [
        Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled", "score_group": "visual_physical"}),
        Probe.from_dict({"id": "q8", "kind": "visibility", "text": "x", "fact_event_id": "e1", "score_group": "hidden_knowledge"}),
    ]
    records = []
    for method in ("text", "image"):
        records.extend([
            {"tick": 1, "method": method, "probe_id": "q9", "correct": True, "score_group": "visual_physical", "had_relevant_event": True},
            {"tick": 1, "method": method, "probe_id": "q8", "correct": False, "score_group": "hidden_knowledge", "had_relevant_event": False},
        ])
    summary = {
        method: {"accuracy": 0.5, "drift_slope": 0.0, "contradictions": 0}
        for method in ("text", "image")
    }
    _write_reports(tmp_path, [event], probes, {"records": records, "summary": summary})
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Visual physical" in report
    assert "Hidden knowledge" in report
    assert (tmp_path / "event_by_event_summary.csv").exists()
