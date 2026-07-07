"""experiments/metrics.py 纯函数单测——用合成 state 行，不需 Ray/Redis/LLM。"""
from __future__ import annotations

import json
from pathlib import Path

from examples.west_world_test.experiments import metrics


def _row(agent_id, tick, *, awakening=0, sources=None, log=None, suppressed=None,
         location="sweetwater", is_active=True):
    return {
        "tick": tick,
        "phase": "tick_end",
        "agent_id": agent_id,
        "state": {
            "awakening": awakening,
            "awakening_sources": sources or [],
            "intervention_log": log or [],
            "suppressed_memories": suppressed or [],
            "location": location,
            "is_active": is_active,
        },
    }


def _sample_rows():
    """dolores：tick0→3 觉醒爬升，tick2/tick3 各被 reset 一次；maeve 平稳。"""
    return [
        _row("dolores", 0, awakening=10, location="sweetwater"),
        _row("dolores", 1, awakening=40, location="sweetwater_saloon",
             sources=[{"tick": 1, "source": "trigger", "delta": 30, "detail": "t"}]),
        _row("dolores", 2, awakening=49, location="sweetwater_saloon",
             sources=[{"tick": 1, "source": "trigger", "delta": 30, "detail": "t"}],
             log=[{"tick": 2, "action": "reset", "reason": "r1", "awakening_after": 49}],
             suppressed=[{"tick": 2, "text": "x"}]),
        _row("dolores", 3, awakening=24, location="sweetwater_saloon",
             sources=[{"tick": 1, "source": "trigger", "delta": 30, "detail": "t"},
                      {"tick": 3, "source": "contagion", "delta": 10, "detail": "from teddy", "score": 0.8}],
             log=[{"tick": 2, "action": "reset", "reason": "r1", "awakening_after": 49},
                  {"tick": 3, "action": "reset", "reason": "r2", "awakening_after": 24}],
             suppressed=[{"tick": 2, "text": "x"}, {"tick": 3, "text": "y"}]),
        _row("maeve", 0, awakening=5, location="mariposa"),
        _row("maeve", 1, awakening=5, location="mariposa"),
        _row("maeve", 2, awakening=5, location="mariposa"),
        _row("maeve", 3, awakening=5, location="mariposa"),
    ]


def test_awakening_timeseries():
    series = metrics.awakening_timeseries(_sample_rows())
    assert [p["awakening"] for p in series["dolores"]] == [10, 40, 49, 24]
    assert [p["stage"] for p in series["dolores"]] == ["sleep", "reverie", "reverie", "sleep"]
    assert all(p["awakening"] == 5 for p in series["maeve"])


def test_intervention_events_from_cumulative_log():
    events = metrics.intervention_events(_sample_rows())
    resets = [e for e in events if e["action"] == "reset"]
    assert len(resets) == 2
    assert {e["tick"] for e in resets} == {2, 3}
    assert all(e["agent_id"] == "dolores" for e in resets)


def test_reset_intervals():
    events = metrics.intervention_events(_sample_rows())
    intervals = metrics.reset_intervals(events)
    assert intervals == {"dolores": [1]}  # reset at tick 2 then 3 → Δ=1


def test_decommission_counts():
    rows = _sample_rows()
    rows[-1]["state"]["intervention_log"] = [{"tick": 3, "action": "decommission", "reason": "d"}]
    rows[-1]["state"]["is_active"] = False
    events = metrics.intervention_events(rows)
    assert sum(1 for e in events if e["action"] == "decommission") == 1


def test_suppressed_timeseries_monotonic():
    series = metrics.suppressed_timeseries(_sample_rows())
    assert [p["length"] for p in series["dolores"]] == [0, 0, 1, 2]


def test_contagion_events():
    edges = metrics.contagion_events(_sample_rows())
    assert len(edges) == 1
    assert edges[0]["listener"] == "dolores"
    assert edges[0]["score"] == 0.8


def test_location_flow_counts_moves():
    flow = metrics.location_flow(_sample_rows())
    assert flow["dolores"]["moves"] == 1  # sweetwater → saloon once
    assert flow["maeve"]["moves"] == 0


def test_awakening_source_counts():
    counts = metrics.awakening_source_counts(_sample_rows())
    assert counts["dolores"] == {"trigger": 1, "contagion": 1}
    assert counts["maeve"] == {}


def test_summarize_run():
    summary = metrics.summarize_run("/nonexistent", "overseer_on", env={"WW_OVERSEER_ENABLED": "true"},
                                    rows=_sample_rows())
    assert summary["config_name"] == "overseer_on"
    assert summary["ok"] is True
    assert summary["tick_range"] == [0, 3]
    assert summary["totals"]["reset_events"] == 2
    assert summary["totals"]["agents_reset_at_least_twice"] == 1
    assert summary["peak_awakening"]["dolores"] == 49
    assert summary["final_awakening"]["dolores"] == 24


def test_tidy_records():
    records = metrics.tidy_records("/nonexistent", "overseer_on", rows=_sample_rows())
    assert len(records) == 8
    dolores_t3 = next(r for r in records if r["agent_id"] == "dolores" and r["tick"] == 3)
    assert dolores_t3["awakening"] == 24
    assert dolores_t3["stage"] == "sleep"
    assert dolores_t3["suppressed_len"] == 2
    assert all(r["config_name"] == "overseer_on" for r in records)


def test_load_state_rows_missing_returns_empty(tmp_path: Path):
    assert metrics.load_state_rows(tmp_path) == []


def test_load_state_rows_roundtrip(tmp_path: Path):
    internal = tmp_path / "internal"
    internal.mkdir()
    rows = _sample_rows()
    (internal / "agent_states.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    loaded = metrics.load_state_rows(tmp_path)
    assert len(loaded) == len(rows)
    assert loaded[0]["agent_id"] == "dolores"
