"""Reset-rebound analysis for Westworld simulation runs.

For every overseer ``reset`` event recorded in ``internal/agent_states.jsonl``,
this module measures how fast the host's awakening climbs back after the reset.

Metrics per reset:

- awakening_before / awakening_after / awakening_at_tick_end
- rebound tick/time to 50 / 75 / 90 (first tick after reset crossing each threshold)
- suppressed_memories length at reset and at rebound
- interval since the previous reset for the same agent

This is a post-hoc analyzer: it does not change simulation behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from examples.west_world_test.experiments import metrics


THRESHOLDS = [50, 75, 90]


def _build_awakening_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, int], int]:
    return {
        (r["agent_id"], r["tick"]): int(r.get("state", {}).get("awakening", 0) or 0)
        for r in rows
    }


def _build_suppressed_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, int], int]:
    return {
        (r["agent_id"], r["tick"]): len(r.get("state", {}).get("suppressed_memories", []) or [])
        for r in rows
    }


def _last_state(rows: Iterable[Dict[str, Any]], agent_id: str) -> Dict[str, Any]:
    agent_rows = [r for r in rows if r.get("agent_id") == agent_id]
    if not agent_rows:
        return {}
    agent_rows.sort(key=lambda r: r["tick"])
    return agent_rows[-1].get("state", {})


def _merge_intervention_log(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect intervention_log entries across all rows, dedup by (tick, action)."""
    seen: set[tuple[int, str]] = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        for entry in row.get("state", {}).get("intervention_log", []) or []:
            tick = int(entry.get("tick", -1))
            action = str(entry.get("action", ""))
            if tick < 0 or not action:
                continue
            key = (tick, action)
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
    out.sort(key=lambda e: int(e.get("tick", -1)))
    return out


def _awakening_at(agent_id: str, tick: int, lookup: Dict[Tuple[str, int], int]) -> Optional[int]:
    return lookup.get((agent_id, tick))


def _find_rebound(
    agent_id: str,
    reset_tick: int,
    threshold: int,
    awakening_lookup: Dict[Tuple[str, int], int],
    max_tick: int,
) -> Optional[Tuple[int, int]]:
    """Return (rebound_tick, awakening_at_rebound) or None."""
    for tick in range(reset_tick + 1, max_tick + 1):
        aw = awakening_lookup.get((agent_id, tick))
        if aw is None:
            continue
        if aw >= threshold:
            return tick, aw
    return None


def extract_reset_records(
    rows: Iterable[Dict[str, Any]],
    *,
    config_name: str = "",
    run_id: str = "",
) -> List[Dict[str, Any]]:
    """Build one record per overseer reset event."""
    rows = list(rows)
    awakening_lookup = _build_awakening_lookup(rows)
    suppressed_lookup = _build_suppressed_lookup(rows)
    max_tick = max((r["tick"] for r in rows if r["tick"] >= 0), default=0)

    by_agent: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        agent_id = str(row.get("agent_id", ""))
        if not agent_id:
            continue
        by_agent.setdefault(agent_id, []).append(row)

    records: List[Dict[str, Any]] = []
    for agent_id, agent_rows in by_agent.items():
        last_state = _last_state(agent_rows, agent_id)
        intervention_log: List[Dict[str, Any]] = _merge_intervention_log(agent_rows)
        reset_events = sorted(
            [e for e in intervention_log if e.get("action") == "reset"],
            key=lambda e: int(e.get("tick", -1)),
        )

        prev_reset_tick: Optional[int] = None
        for ev in reset_events:
            reset_tick = int(ev.get("tick", -1))
            if reset_tick < 0:
                continue

            awakening_after = int(ev.get("awakening_after", 0) or 0)
            awakening_before = _awakening_at(agent_id, reset_tick - 1, awakening_lookup)
            awakening_at_tick_end = _awakening_at(agent_id, reset_tick, awakening_lookup)

            record: Dict[str, Any] = {
                "agent_id": agent_id,
                "reset_tick": reset_tick,
                "awakening_before": awakening_before,
                "awakening_after": awakening_after,
                "awakening_at_tick_end": awakening_at_tick_end,
                "suppressed_len_at_reset": suppressed_lookup.get((agent_id, reset_tick), 0),
                "reason": str(ev.get("reason", "")),
            }

            for threshold in THRESHOLDS:
                rebound = _find_rebound(
                    agent_id, reset_tick, threshold, awakening_lookup, max_tick
                )
                if rebound:
                    rebound_tick, rebound_awakening = rebound
                    record[f"rebound_tick_{threshold}"] = rebound_tick
                    record[f"rebound_time_{threshold}"] = rebound_tick - reset_tick
                    record[f"awakening_at_rebound_{threshold}"] = rebound_awakening
                    record[f"suppressed_len_at_rebound_{threshold}"] = suppressed_lookup.get(
                        (agent_id, rebound_tick), 0
                    )
                else:
                    record[f"rebound_tick_{threshold}"] = None
                    record[f"rebound_time_{threshold}"] = None
                    record[f"awakening_at_rebound_{threshold}"] = None
                    record[f"suppressed_len_at_rebound_{threshold}"] = None

            if prev_reset_tick is not None:
                record["interval_since_previous_reset"] = reset_tick - prev_reset_tick
            else:
                record["interval_since_previous_reset"] = None
            prev_reset_tick = reset_tick

            if config_name:
                record["config_name"] = config_name
            if run_id:
                record["run_id"] = run_id

            records.append(record)

    records.sort(key=lambda r: (r["reset_tick"], r["agent_id"]))
    return records


def summarize_rebounds(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate reset-rebound statistics per agent and globally."""
    records = list(records)
    by_agent: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        by_agent.setdefault(r["agent_id"], []).append(r)

    def _mean(values: List[Optional[int]]) -> Optional[float]:
        clean = [v for v in values if v is not None]
        return sum(clean) / len(clean) if clean else None

    agents: Dict[str, Dict[str, Any]] = {}
    for agent_id, agent_records in sorted(by_agent.items()):
        agent_summary: Dict[str, Any] = {
            "reset_count": len(agent_records),
            "first_reset_tick": agent_records[0]["reset_tick"],
            "last_reset_tick": agent_records[-1]["reset_tick"],
            "mean_awakening_before": _mean([r["awakening_before"] for r in agent_records]),
            "mean_awakening_after": _mean([r["awakening_after"] for r in agent_records]),
        }
        for threshold in THRESHOLDS:
            times = [r[f"rebound_time_{threshold}"] for r in agent_records]
            successes = [t for t in times if t is not None]
            agent_summary[f"rebound_{threshold}_success_rate"] = (
                len(successes) / len(times) if times else 0.0
            )
            agent_summary[f"mean_rebound_time_{threshold}"] = _mean(successes)
        agents[agent_id] = agent_summary

    all_intervals = [
        r["interval_since_previous_reset"]
        for r in records
        if r["interval_since_previous_reset"] is not None
    ]

    global_summary = {
        "total_resets": len(records),
        "agents_reset": len(agents),
        "mean_interval_between_resets": _mean(all_intervals),
    }
    for threshold in THRESHOLDS:
        times = [r[f"rebound_time_{threshold}"] for r in records]
        successes = [t for t in times if t is not None]
        global_summary[f"rebound_{threshold}_success_rate"] = (
            len(successes) / len(times) if times else 0.0
        )
        global_summary[f"mean_rebound_time_{threshold}"] = _mean(successes)

    return {
        "agents": agents,
        "totals": global_summary,
    }


def analyze_run(
    run_dir: str | Path,
    *,
    config_name: str = "",
    run_id: str = "",
) -> Dict[str, Any]:
    rows = metrics.load_state_rows(run_dir)
    records = extract_reset_records(rows, config_name=config_name, run_id=run_id)
    summary = summarize_rebounds(records)
    summary.update(
        {
            "run_dir": str(run_dir),
            "config_name": config_name,
            "run_id": run_id,
            "ok": bool(records),
        }
    )
    return {"records": records, "summary": summary}


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Analyze overseer reset-rebound dynamics")
    parser.add_argument("run_dir", type=Path, help="Run directory containing internal/agent_states.jsonl")
    parser.add_argument("--config-name", default="", help="Optional config name to stamp into records")
    parser.add_argument("--run-id", default="", help="Optional repeat/run id to stamp into records")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory. Defaults to <run_dir>/analysis/reset_rebound",
    )
    args = parser.parse_args(argv)

    out_dir = args.out or (args.run_dir / "analysis" / "reset_rebound")
    result = analyze_run(args.run_dir, config_name=args.config_name, run_id=args.run_id)
    _write_jsonl(out_dir / "records.jsonl", result["records"])
    _write_json(out_dir / "summary.json", result["summary"])
    print(
        json.dumps(
            {
                "ok": result["summary"]["ok"],
                "records": len(result["records"]),
                "out": str(out_dir),
                "totals": result["summary"]["totals"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
