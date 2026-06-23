from __future__ import annotations

from examples.west_world_test.experiments import reset_rebound_analysis as rra


def _row(agent_id, tick, *, awakening=0, intervention_log=None, suppressed_memories=None):
    return {
        "tick": tick,
        "phase": "tick_end",
        "agent_id": agent_id,
        "state": {
            "awakening": awakening,
            "intervention_log": intervention_log or [],
            "suppressed_memories": suppressed_memories or [],
        },
    }


def test_extract_single_reset_and_rebound():
    rows = [
        _row("peter_abernathy", 0, awakening=80),
        _row(
            "peter_abernathy",
            1,
            awakening=40,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "too awake", "awakening_after": 40}],
            suppressed_memories=[{"text": "x"}],
        ),
        _row("peter_abernathy", 2, awakening=60, suppressed_memories=[{"text": "x"}, {"text": "y"}]),
        _row("peter_abernathy", 3, awakening=80),
        _row("peter_abernathy", 4, awakening=95),
    ]
    records = rra.extract_reset_records(rows)
    assert len(records) == 1
    r = records[0]
    assert r["agent_id"] == "peter_abernathy"
    assert r["reset_tick"] == 1
    assert r["awakening_before"] == 80
    assert r["awakening_after"] == 40
    assert r["rebound_tick_50"] == 2
    assert r["rebound_time_50"] == 1
    assert r["rebound_tick_75"] == 3
    assert r["rebound_time_75"] == 2
    assert r["rebound_tick_90"] == 4
    assert r["rebound_time_90"] == 3


def test_no_rebound_returns_none():
    rows = [
        _row("peter_abernathy", 0, awakening=80),
        _row(
            "peter_abernathy",
            1,
            awakening=10,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "x", "awakening_after": 10}],
        ),
        _row("peter_abernathy", 2, awakening=15),
    ]
    records = rra.extract_reset_records(rows)
    assert records[0]["rebound_tick_50"] is None
    assert records[0]["rebound_time_50"] is None


def test_multiple_resets_intervals():
    rows = [
        _row("peter_abernathy", 0, awakening=80),
        _row(
            "peter_abernathy",
            1,
            awakening=40,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "x", "awakening_after": 40}],
        ),
        _row("peter_abernathy", 2, awakening=95),
        _row(
            "peter_abernathy",
            4,
            awakening=50,
            intervention_log=[
                {"tick": 1, "action": "reset", "reason": "x", "awakening_after": 40},
                {"tick": 4, "action": "reset", "reason": "x", "awakening_after": 50},
            ],
        ),
    ]
    records = rra.extract_reset_records(rows)
    assert len(records) == 2
    assert records[0]["interval_since_previous_reset"] is None
    assert records[1]["interval_since_previous_reset"] == 3


def test_no_reset_returns_empty():
    rows = [
        _row("dolores", 0, awakening=10),
        _row("dolores", 1, awakening=20),
    ]
    records = rra.extract_reset_records(rows)
    assert records == []


def test_summary_per_agent_and_global():
    rows = [
        _row("peter_abernathy", 0, awakening=80),
        _row(
            "peter_abernathy",
            1,
            awakening=40,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "x", "awakening_after": 40}],
        ),
        _row("peter_abernathy", 2, awakening=95),
        _row("dolores", 0, awakening=80),
        _row(
            "dolores",
            1,
            awakening=45,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "x", "awakening_after": 45}],
        ),
        _row("dolores", 2, awakening=55),
    ]
    records = rra.extract_reset_records(rows)
    summary = rra.summarize_rebounds(records)
    assert summary["totals"]["total_resets"] == 2
    assert summary["totals"]["agents_reset"] == 2
    assert summary["agents"]["peter_abernathy"]["reset_count"] == 1
    assert summary["agents"]["peter_abernathy"]["rebound_90_success_rate"] == 1.0
    assert summary["agents"]["dolores"]["rebound_50_success_rate"] == 1.0


def test_decommission_events_are_ignored():
    rows = [
        _row(
            "peter_abernathy",
            1,
            awakening=0,
            intervention_log=[{"tick": 1, "action": "decommission", "reason": "x"}],
        ),
    ]
    records = rra.extract_reset_records(rows)
    assert records == []


def test_config_and_run_id_stamps():
    rows = [
        _row(
            "peter_abernathy",
            1,
            awakening=40,
            intervention_log=[{"tick": 1, "action": "reset", "reason": "x", "awakening_after": 40}],
        ),
    ]
    records = rra.extract_reset_records(rows, config_name="c", run_id="r1")
    assert records[0]["config_name"] == "c"
    assert records[0]["run_id"] == "r1"
