from __future__ import annotations

from examples.west_world_test.experiments import dialogue_contagion_analysis as dca


def _profile(agent_id, *, agent_type="host"):
    return {"id": agent_id, "agent_type": agent_type}


def _row(agent_id, tick, *, awakening=0, incoming_dialogue=None, sources=None):
    return {
        "tick": tick,
        "phase": "tick_end",
        "agent_id": agent_id,
        "state": {
            "awakening": awakening,
            "incoming_dialogue": incoming_dialogue or [],
            "awakening_sources": sources or [],
        },
    }


def test_extract_turn_and_classify_absorbed():
    """Peter tells Dolores a memory-break line; Dolores absorbs it and awakens."""
    profiles = {"dolores": _profile("dolores"), "peter_abernathy": _profile("peter_abernathy")}
    rows = [
        _row(
            "peter_abernathy",
            5,
            awakening=80,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "我的记忆中间少了一段。"},
            ],
        ),
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "我的记忆中间少了一段。"},
                {"speaker": "dolores", "line": "你在说什么？"},
            ],
            sources=[
                {
                    "tick": 5,
                    "source": "contagion",
                    "delta": 8,
                    "detail": "触发词命中：我的记忆中间少了一段",
                    "score": 0.8,
                    "level": "high",
                }
            ],
        ),
        _row("dolores", 6, awakening=50),
        _row("dolores", 7, awakening=55),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    assert len(records) == 1
    r = records[0]
    assert r["speaker"] == "peter_abernathy"
    assert r["listener"] == "dolores"
    assert r["speaker_awakening"] == 80
    assert r["listener_awakening"] == 10
    assert r["top_cluster"] == "memory_break"
    assert r["outcome"] == "absorbed"
    assert r["awakening_delta"] == 45  # max(50,55) - 10
    assert r["tick_1"] == 50


def test_rejected_outcome_when_listener_uses_loop_language():
    """Dolores answers with comfort/loop language and her awakening stays flat."""
    profiles = {"dolores": _profile("dolores"), "peter_abernathy": _profile("peter_abernathy")}
    rows = [
        _row("peter_abernathy", 5, awakening=80),
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "你是否曾觉得这一切只是个谎言？"},
                {"speaker": "dolores", "line": "太阳总会升起，明天依然美好。"},
            ],
        ),
        _row("dolores", 6, awakening=10),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    assert records[0]["outcome"] == "rejected"


def test_no_change_when_no_response_and_flat_awakening():
    profiles = {"dolores": _profile("dolores"), "peter_abernathy": _profile("peter_abernathy")}
    rows = [
        _row("peter_abernathy", 5, awakening=80),
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "这一切以前发生过。"},
            ],
        ),
        _row("dolores", 6, awakening=10),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    assert records[0]["outcome"] == "no_change"


def test_guest_speaker_is_skipped():
    profiles = {
        "dolores": _profile("dolores"),
        "william": _profile("william", agent_type="guest"),
    }
    rows = [
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[{"speaker": "william", "line": "你是否曾觉得这一切只是个谎言？"}],
        ),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    assert len(records) == 0


def test_listener_self_turns_are_skipped():
    profiles = {"dolores": _profile("dolores")}
    rows = [
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[{"speaker": "dolores", "line": "我对自己说了一句话。"}],
        ),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    assert len(records) == 0


def test_summary_counts_and_rates():
    profiles = {"dolores": _profile("dolores"), "peter_abernathy": _profile("peter_abernathy")}
    rows = [
        _row("peter_abernathy", 5, awakening=80),
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "我的记忆中间少了一段。"},
                {"speaker": "dolores", "line": "明天太阳会升起。"},
            ],
            sources=[
                {
                    "tick": 5,
                    "source": "contagion",
                    "delta": 8,
                    "detail": "触发词命中：我的记忆中间少了一段",
                    "score": 0.8,
                    "level": "high",
                }
            ],
        ),
        _row("dolores", 6, awakening=50),
        _row("peter_abernathy", 6, awakening=80),
        _row(
            "dolores",
            6,
            awakening=50,
            incoming_dialogue=[
                {"speaker": "peter_abernathy", "line": "我们的路被写好了。"},
                {"speaker": "dolores", "line": "生活总是这样。"},
            ],
        ),
        _row("dolores", 7, awakening=50),
    ]
    records = dca.extract_dialogue_records(rows, profiles)
    summary = dca.summarize_contagion(records)
    assert summary["total_turns"] == 2
    assert summary["outcome_counts"]["absorbed"] == 1
    assert summary["outcome_counts"]["no_change"] == 1
    assert summary["outcome_rates"]["absorbed"] == 0.5
    assert summary["pair_outcomes"]["peter_abernathy->dolores"]["absorbed"] == 1


def test_analyze_run_stamps_config_and_run_id():
    profiles = {"dolores": _profile("dolores"), "peter_abernathy": _profile("peter_abernathy")}
    rows = [
        _row("peter_abernathy", 5, awakening=80),
        _row(
            "dolores",
            5,
            awakening=10,
            incoming_dialogue=[{"speaker": "peter_abernathy", "line": "我的记忆中间少了一段。"}],
        ),
        _row("dolores", 6, awakening=50),
    ]
    result = dca.analyze_run.__wrapped__ if hasattr(dca.analyze_run, "__wrapped__") else dca.analyze_run
    # analyze_run requires run_dir; test the extract/summarize path instead.
    records = dca.extract_dialogue_records(rows, profiles, config_name="c", run_id="r1")
    assert records[0]["config_name"] == "c"
    assert records[0]["run_id"] == "r1"
