"""动力学指标提取层（纯函数，无 Ray / Redis / LLM 依赖）。

输入是一次 run 的输出目录（`SimulationLogArchive` 写出的结构），核心信号来自
`internal/agent_states.jsonl`——它逐 agent 逐 tick 记录了完整 state，已经包含：

- `awakening`：觉醒度整数（0-100）
- `awakening_sources`：累积来源列表，每条 {tick, source, delta, detail, score?, level?}
- `intervention_log`：累积监管者干预列表，每条 {tick, action, reason, awakening_after?}
- `suppressed_memories`：被压制记忆列表（长度随 reset 单调增）
- `location` / `is_active`：地点与存活状态

所有提取函数都接受「已解析的 state 行列表」或直接接受 run 目录，方便用合成数据单测。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from examples.west_world_test.awakening.stages import stage_of

# internal/agent_states.jsonl 相对 run 目录的位置
_STATE_ROWS_REL = "internal/agent_states.jsonl"


# ── 加载 ──────────────────────────────────────────────────────────────────────

def load_state_rows(run_dir: str | Path) -> List[Dict[str, Any]]:
    """读取 internal/agent_states.jsonl，返回 [{tick, phase, agent_id, state}, ...]。

    文件缺失（run 失败/未跑）时返回空列表，不抛异常——让上层标记 config 失败。
    """
    path = Path(run_dir) / _STATE_ROWS_REL
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _rows_by_agent(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_agent: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_agent.setdefault(row["agent_id"], []).append(row)
    for agent_id in by_agent:
        by_agent[agent_id].sort(key=lambda r: r["tick"])
    return by_agent


def _last_state(agent_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """累积型字段（intervention_log/awakening_sources/suppressed_memories）取最后一 tick。"""
    return agent_rows[-1].get("state", {}) if agent_rows else {}


# ── 时间序列 ──────────────────────────────────────────────────────────────────

def awakening_timeseries(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """每个 agent 的觉醒度时间序列：{agent_id: [{tick, awakening, stage}, ...]}。"""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        series = []
        for row in agent_rows:
            aw = int(row.get("state", {}).get("awakening", 0) or 0)
            series.append({"tick": row["tick"], "awakening": aw, "stage": stage_of(aw)})
        out[agent_id] = series
    return out


def suppressed_timeseries(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """每个 agent 的 suppressed_memories 长度时间序列：{agent_id: [{tick, length}, ...]}。"""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        out[agent_id] = [
            {"tick": row["tick"], "length": len(row.get("state", {}).get("suppressed_memories", []) or [])}
            for row in agent_rows
        ]
    return out


# ── 监管者干预事件 ────────────────────────────────────────────────────────────

def intervention_events(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从每个 agent 最后一 tick 的累积 intervention_log 提取干预事件。

    返回扁平列表 [{agent_id, tick, action, reason, awakening_after?}, ...]，按 (tick, agent) 排序。
    action ∈ {"reset", "decommission"}。
    """
    events: List[Dict[str, Any]] = []
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        log = _last_state(agent_rows).get("intervention_log", []) or []
        for entry in log:
            events.append({"agent_id": agent_id, **entry})
    events.sort(key=lambda e: (e.get("tick", -1), e.get("agent_id", "")))
    return events


def reset_intervals(events: Iterable[Dict[str, Any]]) -> Dict[str, List[int]]:
    """每个 agent 相邻两次 reset 之间的 tick 间隔：{agent_id: [Δtick, ...]}。

    只统计 action == "reset"；不足两次 reset 的 agent 不出现在结果里。
    """
    reset_ticks: Dict[str, List[int]] = {}
    for ev in events:
        if ev.get("action") == "reset":
            reset_ticks.setdefault(ev["agent_id"], []).append(int(ev.get("tick", -1)))
    intervals: Dict[str, List[int]] = {}
    for agent_id, ticks in reset_ticks.items():
        ticks.sort()
        if len(ticks) >= 2:
            intervals[agent_id] = [b - a for a, b in zip(ticks, ticks[1:])]
    return intervals


# ── 觉醒来源 / 传染网络 ───────────────────────────────────────────────────────

def awakening_source_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """每个 agent 各类觉醒来源的累计次数：{agent_id: {source: count}}。"""
    out: Dict[str, Dict[str, int]] = {}
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        counts: Dict[str, int] = {}
        for entry in _last_state(agent_rows).get("awakening_sources", []) or []:
            src = str(entry.get("source", "unknown"))
            counts[src] = counts.get(src, 0) + 1
        out[agent_id] = counts
    return out


def contagion_events(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提取 source == 'contagion' 的觉醒事件（觉醒经对话传染的边）。

    返回 [{listener, tick, detail, score?}, ...]。detail 通常含传染源描述，
    用于后续画对话/传染网络（不强行解析成 from→to 边，保留原始 detail）。
    """
    out: List[Dict[str, Any]] = []
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        for entry in _last_state(agent_rows).get("awakening_sources", []) or []:
            if entry.get("source") == "contagion":
                edge = {"listener": agent_id, "tick": entry.get("tick"), "detail": entry.get("detail")}
                if "score" in entry:
                    edge["score"] = entry["score"]
                out.append(edge)
    out.sort(key=lambda e: (e.get("tick", -1), e.get("listener", "")))
    return out


# ── 地点流动 ──────────────────────────────────────────────────────────────────

def location_flow(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """每个 agent 的地点轨迹与移动次数：{agent_id: {moves, path: [{tick, location}, ...]}}。

    moves = 相邻 tick 间 location 改变的次数。
    """
    out: Dict[str, Dict[str, Any]] = {}
    for agent_id, agent_rows in _rows_by_agent(rows).items():
        path = [{"tick": r["tick"], "location": r.get("state", {}).get("location")} for r in agent_rows]
        moves = sum(1 for a, b in zip(path, path[1:]) if a["location"] != b["location"])
        out[agent_id] = {"moves": moves, "path": path}
    return out


# ── 单 run 汇总 ───────────────────────────────────────────────────────────────

def summarize_run(
    run_dir: str | Path,
    config_name: str,
    *,
    env: Optional[Dict[str, str]] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """把一次 run 的全部动力学指标汇总成一个可序列化 dict。

    rows 可显式传入（便于单测）；否则从 run_dir 加载。
    """
    if rows is None:
        rows = load_state_rows(run_dir)
    aw_series = awakening_timeseries(rows)
    events = intervention_events(rows)
    intervals = reset_intervals(events)

    ticks = sorted({r["tick"] for r in rows})
    reset_count = sum(1 for e in events if e.get("action") == "reset")
    decommission_count = sum(1 for e in events if e.get("action") == "decommission")
    peak_awakening = {
        agent_id: max((p["awakening"] for p in series), default=0)
        for agent_id, series in aw_series.items()
    }
    final_awakening = {
        agent_id: (series[-1]["awakening"] if series else 0)
        for agent_id, series in aw_series.items()
    }
    flat_intervals = [iv for ivs in intervals.values() for iv in ivs]

    return {
        "config_name": config_name,
        "env": env or {},
        "ok": bool(rows),
        "tick_range": [ticks[0], ticks[-1]] if ticks else [],
        "agents": sorted(aw_series.keys()),
        "totals": {
            "reset_events": reset_count,
            "decommission_events": decommission_count,
            "agents_reset_at_least_twice": len(intervals),
            "mean_reset_interval": (sum(flat_intervals) / len(flat_intervals)) if flat_intervals else None,
            "contagion_events": len(contagion_events(rows)),
            "total_moves": sum(v["moves"] for v in location_flow(rows).values()),
        },
        "peak_awakening": peak_awakening,
        "final_awakening": final_awakening,
        "intervention_events": events,
        "reset_intervals": intervals,
        "awakening_source_counts": awakening_source_counts(rows),
    }


def tidy_records(
    run_dir: str | Path,
    config_name: str,
    *,
    rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """长格式（tidy）记录：每 (config, agent, tick) 一行，方便 notebook 直接读成 DataFrame。"""
    if rows is None:
        rows = load_state_rows(run_dir)
    suppressed = suppressed_timeseries(rows)
    sup_lookup = {
        (agent_id, p["tick"]): p["length"]
        for agent_id, series in suppressed.items()
        for p in series
    }
    records: List[Dict[str, Any]] = []
    for row in rows:
        state = row.get("state", {})
        aw = int(state.get("awakening", 0) or 0)
        agent_id, tick = row["agent_id"], row["tick"]
        records.append({
            "config_name": config_name,
            "agent_id": agent_id,
            "tick": tick,
            "awakening": aw,
            "stage": stage_of(aw),
            "location": state.get("location"),
            "is_active": bool(state.get("is_active", True)),
            "suppressed_len": sup_lookup.get((agent_id, tick), 0),
        })
    records.sort(key=lambda r: (r["agent_id"], r["tick"]))
    return records
