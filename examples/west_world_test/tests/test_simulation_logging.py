import json

from examples.west_world_test.simulation_logging import (
    SimulationLogArchive,
    check_state_consistency,
)
from examples.west_world_test.log_cli import list_runs, query_tick


def _scene(present_agents, hidden="secret"):
    return {
        "location": {"id": "place", "name": "Place"},
        "chunks": {
            "present_agents": present_agents,
            "recent_events": [],
            "hidden_notes": hidden,
        },
    }


def test_consistency_requires_exactly_one_matching_recorder_location():
    agents = {
        "alice": {"location": "a"},
        "bob": {"location": "b"},
    }
    scenes = {
        "a": _scene("alice"),
        "b": _scene("bob"),
    }
    assert check_state_consistency(agents, scenes)["ok"] is True

    scenes["b"]["chunks"]["present_agents"] = "alice、bob"
    result = check_state_consistency(agents, scenes)
    assert result["ok"] is False
    assert result["violations"][0]["agent_id"] == "alice"


def test_archive_writes_complete_tick_and_keeps_hidden_data_internal(tmp_path):
    project = tmp_path / "project"
    (project / "configs_sim").mkdir(parents=True)
    (project / "configs_sim" / "simulation_config.yaml").write_text("simulation: {}\n", encoding="utf-8")
    (project / "data").mkdir()
    (project / "data" / "states.jsonl").write_text('{"id": "alice"}\n', encoding="utf-8")
    run_dir = tmp_path / "run"
    archive = SimulationLogArchive(project, 1, ["alice"], ["a"], run_dir=run_dir)

    agents = {
        "alice": {
            "location": "a",
            "plan_trace": {"prompt": "full prompt", "raw_response": "full response"},
        }
    }
    public = {"a": {
        "location": {"id": "a"},
        "chunks": {"present_agents": "alice", "recent_events": []},
    }}
    internal = {"a": {
        "location": {"id": "a"},
        "chunks": {"present_agents": "alice", "hidden_notes": "secret"},
        "pending_actions": [{"action": "x"}],
        "llm_traces": [{"call_type": "recorder_judge", "prompt": "judge", "raw_response": "{}"}],
    }}
    archive.record_tick(0, agents, public, internal, {"agent_step": 0.1}, [])
    archive.complete()

    timeline = (run_dir / "timeline.jsonl").read_text(encoding="utf-8")
    public_log = (run_dir / "scene_snapshots_public.jsonl").read_text(encoding="utf-8")
    internal_log = (run_dir / "scene_snapshots_internal.jsonl").read_text(encoding="utf-8")
    traces = [
        json.loads(line)
        for line in (run_dir / "model_traces.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert "full prompt" in timeline
    assert "secret" not in public_log
    assert "secret" in internal_log
    assert {trace["source"] for trace in traces} == {"agent_plan", "location_recorder"}
    assert manifest["status"] == "completed"
    assert manifest["completed_ticks"] == 1
    assert manifest["record_counts"]["timeline_snapshots"] == 1
    assert manifest["record_counts"]["agent_state_rows"] == 1
    assert manifest["record_counts"]["model_trace_rows"] == 2
    assert (run_dir / "README.md").exists()


def test_archive_records_failure_in_manifest(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    archive = SimulationLogArchive(project, 3, [], [], run_dir=tmp_path / "run")
    archive.fail(RuntimeError("broken"))
    manifest = json.loads((archive.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "RuntimeError: broken" == manifest["error"]


def test_archive_builds_summary_views_and_queryable_attempt_logs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "runs"
    run_dir = root / "run-1"
    archive = SimulationLogArchive(project, 1, ["alice"], ["a"], run_dir=run_dir)
    agents = {
        "alice": {
            "location": "a",
            "plan_decision": {"action": "do"},
            "plan_trace": {"request_id": "req-1", "prompt": "p", "raw_response": "r"},
        }
    }
    public = {"a": _scene("alice")}
    internal = {"a": {**_scene("alice"), "pending_actions": [], "llm_traces": []}}
    archive.record_tick(0, agents, public, internal, {"agent_step": 1.0}, [])
    archive.record_model_attempts(0, [
        {
            "request_id": "req-1", "attempt_id": "attempt-1", "attempt_number": 1,
            "status": "failed", "duration_ms": 3000, "error_type": "TimeoutError",
        },
        {
            "request_id": "req-1", "attempt_id": "attempt-2", "attempt_number": 2,
            "status": "success", "duration_ms": 1000,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    ])
    archive.complete()
    archive._write_views_and_summary()

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["actions"] == {"do": 1}
    assert summary["llm"]["attempts"] == 2
    assert summary["llm"]["failed_attempts"] == 1
    assert summary["llm"]["retries"] == 1
    assert summary["llm"]["usage"]["total_tokens"] == 15
    assert query_tick(run_dir, 0)["tick"] == 0
    assert list_runs(root)[0]["run_id"] == "run-1"
    assert len((run_dir / "views/agents/alice.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert len((run_dir / "views/slow_requests.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert len((run_dir / "views/failures.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert "attempt-1" in (run_dir / "report/report.md").read_text(encoding="utf-8")
