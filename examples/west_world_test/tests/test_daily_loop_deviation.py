from __future__ import annotations

from examples.west_world_test.experiments import daily_loop_deviation as dld


def _profile(agent_id="dolores", *, agent_type="host"):
    return {
        "id": agent_id,
        "agent_type": agent_type,
        "daily_loop": [
            {"segment": "清晨", "location": "ranch", "intent": "wake"},
            {"segment": "上午", "location": "town", "intent": "go town"},
            {"segment": "正午", "location": "store", "intent": "shop"},
            {"segment": "下午", "location": "town", "intent": "meet"},
            {"segment": "傍晚", "location": "ranch", "intent": "return"},
            {"segment": "夜晚", "location": "ranch", "intent": "night"},
        ],
    }


def _row(agent_id, tick, *, percept, final, action="do", target="", awakening=0):
    return {
        "tick": tick,
        "phase": "tick_end",
        "agent_id": agent_id,
        "state": {
            "location": final,
            "awakening": awakening,
            "percept": {"location": percept},
            "plan_decision": {"action": action, "target": target, "detail": "x"},
        },
    }


def test_classify_on_plan():
    record = dld.classify_tick(_row("dolores", 1, percept="town", final="town"), _profile())
    assert record["status"] == "on_plan"
    assert record["meaningful_off_plan"] is False


def test_classify_moving_toward_expected_is_not_meaningful_off_plan():
    record = dld.classify_tick(
        _row("dolores", 2, percept="town", final="town", action="move", target="store"),
        _profile(),
    )
    assert record["status"] == "moving_toward_expected"
    assert record["meaningful_off_plan"] is False


def test_classify_moving_elsewhere_is_meaningful_off_plan():
    record = dld.classify_tick(
        _row("dolores", 2, percept="town", final="saloon", action="move", target="saloon", awakening=30),
        _profile(),
    )
    assert record["status"] == "moving_elsewhere"
    assert record["meaningful_off_plan"] is True
    assert record["stage"] == "reverie"


def test_classify_staying_off_expected_is_meaningful_off_plan():
    record = dld.classify_tick(_row("dolores", 3, percept="ranch", final="ranch"), _profile())
    assert record["status"] == "staying_off_expected"
    assert record["meaningful_off_plan"] is True


def test_classify_host_day_reset_separately():
    record = dld.classify_tick(_row("dolores", 5, percept="town", final="ranch"), _profile())
    assert record["status"] == "day_reset"
    assert record["meaningful_off_plan"] is False


def test_deviation_summary_counts_awakened_off_plan():
    profiles = {"dolores": _profile(), "maeve": _profile("maeve")}
    records = dld.deviation_records(
        [
            _row("dolores", 1, percept="town", final="town"),
            _row("dolores", 2, percept="town", final="saloon", action="move", target="saloon", awakening=30),
            _row("maeve", 1, percept="ranch", final="ranch"),
        ],
        profiles,
        config_name="c",
        run_id="r1",
    )
    summary = dld.summarize_deviations(records)
    assert summary["agents"]["dolores"]["meaningful_off_plan"] == 1
    assert summary["agents"]["dolores"]["awakened_meaningful_off_plan"] == 1
    assert summary["agents"]["maeve"]["meaningful_off_plan"] == 1
    assert records[0]["config_name"] == "c"
    assert records[0]["run_id"] == "r1"
