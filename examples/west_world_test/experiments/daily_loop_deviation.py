"""Daily-loop deviation analysis for Westworld simulation runs.

This module compares each agent tick against the profile-level
``daily_loop[tick % 6]`` location.  It is intentionally post-hoc and does not
change simulation behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from examples.west_world_test.awakening.stages import stage_of
from examples.west_world_test.experiments import metrics


MEANINGFUL_OFF_PLAN = frozenset({"staying_off_expected", "moving_elsewhere"})


def load_profiles(path: str | Path) -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            profile = json.loads(line)
            profiles[profile["id"]] = profile
    return profiles


def _decision_target(decision: Dict[str, Any]) -> str:
    return str(decision.get("target") or decision.get("target_location") or "")


def _is_day_reset(
    *,
    tick: int,
    profile: Dict[str, Any],
    percept_location: str,
    final_location: str,
    action: str,
) -> bool:
    """Detect host end-of-day loop-origin reset.

    The reflect plugin can put hosts back at their loop origin at the end of
    the night segment.  This can look like a non-adjacent jump, so it should not
    be counted as an intentional plan deviation.
    """
    loop = profile.get("daily_loop") or []
    if profile.get("agent_type") != "host" or len(loop) < 6:
        return False
    if tick % 6 != 5:
        return False
    origin = str(loop[0].get("location", ""))
    return bool(origin and final_location == origin and percept_location != final_location and action != "move")


def classify_tick(
    row: Dict[str, Any],
    profile: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Classify one ``tick_end`` state row against its expected daily-loop location."""
    tick = int(row.get("tick", -1))
    if tick < 0 or row.get("phase") != "tick_end":
        return None

    loop = profile.get("daily_loop") or []
    if len(loop) <= tick % 6:
        return None

    state = row.get("state") or {}
    percept = state.get("percept") or {}
    decision = state.get("plan_decision") or {}

    expected_segment = loop[tick % 6]
    expected_location = str(expected_segment.get("location", ""))
    percept_location = str(percept.get("location") or "")
    final_location = str(state.get("location") or "")
    action = str(decision.get("action") or "")
    target = _decision_target(decision)

    if _is_day_reset(
        tick=tick,
        profile=profile,
        percept_location=percept_location,
        final_location=final_location,
        action=action,
    ):
        status = "day_reset"
    elif final_location == expected_location:
        status = "on_plan"
    elif action == "move" and target == expected_location:
        status = "moving_toward_expected"
    elif action == "move" and target and target != expected_location:
        status = "moving_elsewhere"
    else:
        status = "staying_off_expected"

    awakening = int(state.get("awakening", 0) or 0)
    meaningful_off_plan = status in MEANINGFUL_OFF_PLAN
    return {
        "agent_id": row.get("agent_id"),
        "agent_type": profile.get("agent_type", ""),
        "tick": tick,
        "segment": expected_segment.get("segment", ""),
        "expected_location": expected_location,
        "expected_intent": expected_segment.get("intent", ""),
        "percept_location": percept_location,
        "final_location": final_location,
        "action": action,
        "target": target,
        "status": status,
        "meaningful_off_plan": meaningful_off_plan,
        "awakening": awakening,
        "stage": stage_of(awakening),
        "ending": decision.get("ending", ""),
        "detail": decision.get("detail", ""),
    }


def deviation_records(
    rows: Iterable[Dict[str, Any]],
    profiles: Dict[str, Dict[str, Any]],
    *,
    config_name: str = "",
    run_id: str = "",
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row in rows:
        profile = profiles.get(str(row.get("agent_id", "")))
        if not profile:
            continue
        record = classify_tick(row, profile)
        if record is None:
            continue
        if config_name:
            record["config_name"] = config_name
        if run_id:
            record["run_id"] = run_id
        records.append(record)
    records.sort(key=lambda r: (r.get("agent_id", ""), r.get("tick", -1)))
    return records


def summarize_deviations(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    by_agent: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        by_agent.setdefault(str(record["agent_id"]), []).append(record)

    agents: Dict[str, Dict[str, Any]] = {}
    for agent_id, agent_records in sorted(by_agent.items()):
        status_counts: Dict[str, int] = {}
        for record in agent_records:
            status = str(record["status"])
            status_counts[status] = status_counts.get(status, 0) + 1

        meaningful = [r for r in agent_records if r["meaningful_off_plan"]]
        awakened_meaningful = [r for r in meaningful if int(r.get("awakening", 0) or 0) > 0]
        awake_stage_meaningful = [
            r for r in meaningful
            if str(r.get("stage", "")) in {"reverie", "resistance", "awake"}
        ]
        total = len(agent_records)
        agents[agent_id] = {
            "agent_type": agent_records[0].get("agent_type", ""),
            "ticks": total,
            "status_counts": status_counts,
            "meaningful_off_plan": len(meaningful),
            "meaningful_off_plan_rate": len(meaningful) / total if total else 0.0,
            "awakened_meaningful_off_plan": len(awakened_meaningful),
            "reverie_or_above_meaningful_off_plan": len(awake_stage_meaningful),
            "max_awakening": max((int(r.get("awakening", 0) or 0) for r in agent_records), default=0),
            "first_meaningful_off_plan_tick": meaningful[0]["tick"] if meaningful else None,
        }

    return {
        "agents": agents,
        "totals": {
            "agents": len(agents),
            "ticks": sum(a["ticks"] for a in agents.values()),
            "meaningful_off_plan": sum(a["meaningful_off_plan"] for a in agents.values()),
            "awakened_meaningful_off_plan": sum(a["awakened_meaningful_off_plan"] for a in agents.values()),
            "day_resets": sum(a["status_counts"].get("day_reset", 0) for a in agents.values()),
        },
    }


def analyze_run(
    run_dir: str | Path,
    profiles_path: str | Path,
    *,
    config_name: str = "",
    run_id: str = "",
) -> Dict[str, Any]:
    rows = metrics.load_state_rows(run_dir)
    profiles = load_profiles(profiles_path)
    records = deviation_records(rows, profiles, config_name=config_name, run_id=run_id)
    summary = summarize_deviations(records)
    summary.update({
        "run_dir": str(run_dir),
        "config_name": config_name,
        "run_id": run_id,
        "ok": bool(records),
    })
    return {"records": records, "summary": summary}


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Analyze daily-loop location deviations for one simulation run")
    parser.add_argument("run_dir", type=Path, help="Run directory containing internal/agent_states.jsonl")
    parser.add_argument("--profiles", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "agents" / "profiles_sim.jsonl")
    parser.add_argument("--config-name", default="", help="Optional config name to stamp into records")
    parser.add_argument("--run-id", default="", help="Optional repeat/run id to stamp into records")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory. Defaults to <run_dir>/analysis/daily_loop_deviation")
    args = parser.parse_args(argv)

    out_dir = args.out or (args.run_dir / "analysis" / "daily_loop_deviation")
    result = analyze_run(args.run_dir, args.profiles, config_name=args.config_name, run_id=args.run_id)
    _write_jsonl(out_dir / "records.jsonl", result["records"])
    _write_json(out_dir / "summary.json", result["summary"])
    print(json.dumps({
        "ok": result["summary"]["ok"],
        "records": len(result["records"]),
        "out": str(out_dir),
        "totals": result["summary"]["totals"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
