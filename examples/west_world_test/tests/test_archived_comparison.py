import json

from examples.west_world_test.eval.run_archived_comparison import TraceArchive, _call_budget, _write_reports
from examples.west_world_test.core.schema import Event, Probe


def test_trace_archive_saves_full_text_request_and_response(tmp_path):
    trace = TraceArchive(tmp_path / "model_traces" / "all_calls.jsonl")
    trace({"call_type": "text_chat", "prompt": "完整请求", "response": "完整输出"})
    row = json.loads((tmp_path / "model_traces" / "all_calls.jsonl").read_text(encoding="utf-8"))
    assert row["prompt"] == "完整请求"
    assert row["response"] == "完整输出"
    assert row["sequence"] == 1


def test_call_budget_includes_tick_zero_and_updates():
    assert _call_budget([object(), object()], [object(), object(), object()]) == {
        "text_chat": 11,
        "vision_chat": 9,
        "image_generate": 1,
        "image_edit": 2,
        "total_model_calls": 23,
    }


def test_global_report_separates_visual_and_hidden_scores(tmp_path):
    event = Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})
    probes = [
        Probe.from_dict({"id": "q9", "kind": "state", "text": "x", "field": "glasses_filled", "score_group": "visual_snapshot"}),
        Probe.from_dict({"id": "q8", "kind": "visibility", "text": "x", "fact_event_id": "e1", "score_group": "hidden_knowledge"}),
    ]
    records = []
    for method in ("text", "image"):
        records.extend([
            {"tick": 1, "method": method, "probe_id": "q9", "correct": True, "score_group": "visual_snapshot", "evaluation_role": "affected", "had_relevant_event": True},
            {"tick": 1, "method": method, "probe_id": "q8", "correct": False, "score_group": "hidden_knowledge", "evaluation_role": "unaffected_baseline", "had_relevant_event": False},
        ])
    summary = {
        method: {
            "accuracy": 0.5, "initial_accuracy": 0.0, "affected_accuracy": 1.0,
            "persistence_accuracy": 0.0, "final_state_accuracy": 0.5,
            "drift_slope": 0.0, "contradictions": 0,
            "accuracy_by_group_role": {
                "visual_snapshot": {"initial": 0.0, "affected": 1.0, "persistence": 0.0, "unaffected_baseline": 0.0},
                "hidden_knowledge": {"initial": 0.0, "affected": 0.0, "persistence": 0.0, "unaffected_baseline": 0.0},
            },
        }
        for method in ("text", "image")
    }
    _write_reports(tmp_path, [event], probes, {"records": records, "summary": summary})
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "视觉快照" in report
    assert "隐藏知识" in report
    assert (tmp_path / "event_by_event_summary.csv").exists()
    assert (tmp_path / "role_metrics.json").exists()
    assert (tmp_path / "group_role_matrix.json").exists()
