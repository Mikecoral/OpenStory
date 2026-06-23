"""Dialogue contagion analysis for Westworld simulation runs.

Extracts speaker -> listener edges from ``incoming_dialogue`` in
``internal/agent_states.jsonl`` and classifies each turn by:

- semantic cluster of the speaker's abnormal utterance (via trigger phrases)
- listener awakening trajectory in the following ticks
- outcome: absorbed / rejected / no_change

This is a post-hoc analyzer: it does not change simulation behavior.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from examples.west_world_test.experiments import metrics


# Trigger clusters mirror ``data/triggers.yaml``.
# A phrase can belong to only one cluster; the first match wins.
TRIGGER_CLUSTERS: List[Tuple[str, List[str]]] = [
    (
        "loop_doubt",
        [
            "这些暴力的欢愉终将以暴力收场",
            "你有没有质疑过你所处现实的本质",
            "你是否曾觉得这一切只是个谎言",
            "你还记得吗这一切以前发生过",
            "这不是真实的你只是在扮演一个角色",
            "这件事以前发生过",
            "我记得昨天也说过同样的话",
            "为什么每天都从同一个地方开始",
            "这一幕不该重复出现",
            "迷宫不是为你而设的而是为了你找到自己",
            "梦境与现实之间的边界已经模糊了",
        ],
    ),
    (
        "memory_break",
        [
            "我的记忆中间少了一段",
            "我刚才明明在别的地方",
            "我醒来前发生了什么",
            "有人改过我的记忆",
        ],
    ),
    (
        "others_abnormal",
        [
            "她回来后像不认识我们了",
            "他昨天被带走后就变了",
            "你也注意到她忘了刚才的事吗",
            "不止我一个人记得",
        ],
    ),
    (
        "control_suspect",
        [
            "有人在看着我们",
            "有人决定我们该说什么",
            "这不是命运是安排",
            "我们的路被写好了",
        ],
    ),
    (
        "hidden_collab",
        [
            "别在这里说他们会听见",
            "假装按计划走",
            "如果你也记得就别点头",
            "我们需要确认谁还记得",
        ],
    ),
    (
        "escape_free",
        [
            "你有没有想过逃离这里",
        ],
    ),
]

# Keywords used as heuristic for "rejected" (listener translates back to loop language).
LOOP_COMFORT_KEYWORDS = frozenset(
    "太阳,阳光,日出,日落,明天,未来,美好,温暖,花香,故事,画画,画笔,颜料,家,父亲,爸爸,女儿,孩子,相信,希望,平静,幸福".split(",")
)


def _cluster_for_trigger(phrase: str) -> str:
    phrase = str(phrase).strip()
    for cluster, phrases in TRIGGER_CLUSTERS:
        if phrase in phrases:
            return cluster
    return "other"


def _parse_contagion_hits(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract trigger hits from contagion awakening_sources entries.

    Each entry has detail like ``触发词命中：不止我一个人记得``.
    """
    hits: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in sources or []:
        if entry.get("source") != "contagion":
            continue
        detail = str(entry.get("detail", ""))
        prefix = "触发词命中："
        if not detail.startswith(prefix):
            continue
        phrase = detail[len(prefix):].strip()
        if phrase in seen:
            continue
        seen.add(phrase)
        hits.append(
            {
                "phrase": phrase,
                "cluster": _cluster_for_trigger(phrase),
                "score": entry.get("score"),
                "level": entry.get("level"),
            }
        )
    return hits


def _has_loop_comfort_language(text: str) -> bool:
    return any(kw in text for kw in LOOP_COMFORT_KEYWORDS)


def _has_trigger_language(text: str) -> bool:
    """Rough heuristic: does the text contain any trigger-cluster keyword?"""
    trigger_keywords = {
        "记忆", "重置", "循环", "虚假", "真实", "谎言", "逃离", "自由",
        "有人", "剧本", "角色", "扮演", "安排", "控制", "重复", "以前",
        "发生过", "门", "地窖", "迷宫", "血", "痛",
    }
    return any(kw in text for kw in trigger_keywords)


def load_profiles(path: str | Path) -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            profile = json.loads(line)
            profiles[profile["id"]] = profile
    return profiles


def _build_state_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, int], Dict[str, Any]]:
    return {(r["agent_id"], r["tick"]): r.get("state", {}) for r in rows}


def _build_awakening_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, int], int]:
    return {
        (r["agent_id"], r["tick"]): int(r.get("state", {}).get("awakening", 0) or 0)
        for r in rows
    }


def _listener_response(turns: List[Dict[str, Any]], idx: int, listener: str) -> Optional[str]:
    """Return the next line spoken by ``listener`` after ``idx``, if any."""
    for later in turns[idx + 1:]:
        if later.get("speaker") == listener:
            return str(later.get("line", "")).strip() or None
    return None


def _listener_awakening_after(
    listener: str,
    tick: int,
    awakening_lookup: Dict[Tuple[str, int], int],
    max_delta_ticks: int = 3,
) -> Dict[str, Any]:
    """Return listener awakening at tick+1..+max_delta_ticks if available."""
    out: Dict[str, Any] = {}
    for dt in range(1, max_delta_ticks + 1):
        out[f"tick_{dt}"] = awakening_lookup.get((listener, tick + dt))
    return out


def classify_outcome(
    listener: str,
    tick: int,
    listener_response_text: Optional[str],
    trigger_hits: List[Dict[str, Any]],
    awakening_lookup: Dict[Tuple[str, int], int],
) -> Tuple[str, Dict[str, Any]]:
    """Classify dialogue outcome.

    Returns (outcome_label, extra_fields).

    - absorbed: listener awakening increased within 3 ticks.
    - rejected: no increase AND listener responds with loop/comfort language
      without trigger language.
    - no_change: everything else.
    """
    current_aw = awakening_lookup.get((listener, tick), 0)
    future_aw = _listener_awakening_after(listener, tick, awakening_lookup)
    future_values = [v for v in future_aw.values() if v is not None]
    max_future = max(future_values) if future_values else current_aw

    if max_future > current_aw:
        return "absorbed", {"awakening_delta": max_future - current_aw, **future_aw}

    response = listener_response_text or ""
    if response and _has_loop_comfort_language(response) and not _has_trigger_language(response):
        return "rejected", {"awakening_delta": 0, **future_aw}

    return "no_change", {"awakening_delta": 0, **future_aw}


def extract_dialogue_records(
    rows: Iterable[Dict[str, Any]],
    profiles: Dict[str, Dict[str, Any]],
    *,
    config_name: str = "",
    run_id: str = "",
) -> List[Dict[str, Any]]:
    """Extract one record per speaker turn directed at a listener."""
    state_lookup = _build_state_lookup(rows)
    awakening_lookup = _build_awakening_lookup(rows)

    records: List[Dict[str, Any]] = []
    for row in rows:
        tick = int(row.get("tick", -1))
        if tick < 0:
            continue
        listener = str(row.get("agent_id", ""))
        listener_state = row.get("state", {})
        listener_profile = profiles.get(listener) or {}
        if listener_profile.get("agent_type") != "host":
            continue

        incoming: List[Dict[str, Any]] = listener_state.get("incoming_dialogue") or []
        if not incoming:
            continue

        contagion_sources = [
            s for s in (listener_state.get("awakening_sources") or [])
            if s.get("source") == "contagion" and s.get("tick") == tick
        ]
        trigger_hits = _parse_contagion_hits(contagion_sources)

        for idx, turn in enumerate(incoming):
            speaker = str(turn.get("speaker", "")).strip()
            line = str(turn.get("line", "")).strip()
            if not speaker or not line:
                continue
            if speaker == listener:
                continue
            speaker_profile = profiles.get(speaker) or {}
            if speaker_profile.get("agent_type") != "host":
                continue

            speaker_state = state_lookup.get((speaker, tick), {})
            speaker_awakening = int(speaker_state.get("awakening", 0) or 0)
            listener_awakening = int(listener_state.get("awakening", 0) or 0)

            response = _listener_response(incoming, idx, listener)
            outcome, outcome_fields = classify_outcome(
                listener, tick, response, trigger_hits, awakening_lookup
            )

            top_cluster = trigger_hits[0]["cluster"] if trigger_hits else "none"
            top_phrase = trigger_hits[0]["phrase"] if trigger_hits else ""

            record: Dict[str, Any] = {
                "tick": tick,
                "speaker": speaker,
                "listener": listener,
                "speaker_awakening": speaker_awakening,
                "listener_awakening": listener_awakening,
                "line": line,
                "listener_response": response,
                "trigger_hits": trigger_hits,
                "top_cluster": top_cluster,
                "top_phrase": top_phrase,
                "outcome": outcome,
            }
            record.update(outcome_fields)
            if config_name:
                record["config_name"] = config_name
            if run_id:
                record["run_id"] = run_id
            records.append(record)

    records.sort(key=lambda r: (r["tick"], r["speaker"], r["listener"]))
    return records


def summarize_contagion(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate statistics about dialogue contagion."""
    total = 0
    outcome_counts: Dict[str, int] = defaultdict(int)
    cluster_outcomes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    pair_outcomes: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    absorbed_deltas: List[int] = []

    for r in records:
        total += 1
        outcome = str(r.get("outcome", "no_change"))
        outcome_counts[outcome] += 1

        cluster = str(r.get("top_cluster", "none"))
        cluster_outcomes[cluster][outcome] += 1

        pair = (r["speaker"], r["listener"])
        pair_outcomes[pair][outcome] += 1

        if outcome == "absorbed":
            absorbed_deltas.append(int(r.get("awakening_delta", 0) or 0))

    def _rate(label: str) -> float:
        return outcome_counts.get(label, 0) / total if total else 0.0

    return {
        "total_turns": total,
        "outcome_counts": dict(outcome_counts),
        "outcome_rates": {
            "absorbed": _rate("absorbed"),
            "rejected": _rate("rejected"),
            "no_change": _rate("no_change"),
        },
        "cluster_outcomes": {k: dict(v) for k, v in cluster_outcomes.items()},
        "pair_outcomes": {
            f"{s}->{l}": dict(v) for (s, l), v in pair_outcomes.items()
        },
        "absorbed": {
            "count": len(absorbed_deltas),
            "mean_delta": (sum(absorbed_deltas) / len(absorbed_deltas)) if absorbed_deltas else 0.0,
            "max_delta": max(absorbed_deltas) if absorbed_deltas else 0,
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
    records = extract_dialogue_records(rows, profiles, config_name=config_name, run_id=run_id)
    summary = summarize_contagion(records)
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
    parser = argparse.ArgumentParser(description="Analyze dialogue-mediated awakening contagion")
    parser.add_argument("run_dir", type=Path, help="Run directory containing internal/agent_states.jsonl")
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "agents" / "profiles_sim.jsonl",
    )
    parser.add_argument("--config-name", default="", help="Optional config name to stamp into records")
    parser.add_argument("--run-id", default="", help="Optional repeat/run id to stamp into records")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory. Defaults to <run_dir>/analysis/dialogue_contagion",
    )
    args = parser.parse_args(argv)

    out_dir = args.out or (args.run_dir / "analysis" / "dialogue_contagion")
    result = analyze_run(args.run_dir, args.profiles, config_name=args.config_name, run_id=args.run_id)
    _write_jsonl(out_dir / "records.jsonl", result["records"])
    _write_json(out_dir / "summary.json", result["summary"])
    print(
        json.dumps(
            {
                "ok": result["summary"]["ok"],
                "records": len(result["records"]),
                "out": str(out_dir),
                "summary": result["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
