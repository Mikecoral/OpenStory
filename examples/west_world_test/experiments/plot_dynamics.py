"""从实验输出（records.jsonl / events.jsonl）生成动力学可视化图。

读 `overseer_dynamics.py` 的聚合产物，画出觉醒-压制-复燃动力学。生成到
`<exp_dir>/figures/`：

- `awakening_trajectories.png`：逐 host 觉醒度时间序列 + reset/decommission 事件标记 + 阶段阈值线
- `awakening_heatmap.png`：agent × tick 觉醒度热力图（每个 config 一张）
- `intervention_timeline.png`：监管者干预事件时间线（reset / decommission）
- `reset_intervals.png`：复燃周期（相邻两次 reset 间隔）分布

用法：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \\
        python -m examples.west_world_test.experiments.plot_dynamics <exp_dir>
    # 不传 exp_dir 则取 output/sim_runs 下最新一次
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")  # 无显示环境
import matplotlib.pyplot as plt
import pandas as pd

# 阶段阈值（与 awakening/stages.py 默认一致；画参考线用）
_STAGE_THRESHOLDS = [25, 50, 75, 90]
_STAGE_LABELS = ["sleep", "reverie", "doubt", "resistance", "awake"]
_THIS_DIR = Path(__file__).resolve().parent
_DEFAULT_OUT_ROOT = _THIS_DIR.parent / "output" / "sim_runs"

# 让中文标签正常显示：只选 fontManager 里确实注册了的 CJK 字体（按名字匹配，避免方框）
from matplotlib import font_manager as _fm  # noqa: E402

_available = {f.name for f in _fm.fontManager.ttflist}
for _f in ("PingFang SC", "Songti SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS", "Heiti TC"):
    if _f in _available:
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False


def _latest_exp_dir() -> Path:
    # 按目录名尾部时间戳 YYYYMMDD_HHMMSS（15 字符）排序，即创建时间序。
    # 不用 mtime（重绘会刷新）、不用整名排序（'exp_stress2' 会排在 'exp_stress_' 前）。
    candidates = [p for p in _DEFAULT_OUT_ROOT.glob("*") if (p / "records.jsonl").exists()]
    if not candidates:
        sys.exit(f"未在 {_DEFAULT_OUT_ROOT} 找到任何实验输出（records.jsonl）")
    return max(candidates, key=lambda p: p.name[-15:])


def _load(exp_dir: Path):
    records = pd.read_json(exp_dir / "records.jsonl", lines=True)
    events_path = exp_dir / "events.jsonl"
    events = (
        pd.read_json(events_path, lines=True)
        if events_path.exists() and events_path.stat().st_size > 0
        else pd.DataFrame(columns=["config_name", "agent_id", "tick", "action"])
    )
    return records, events


def _stage_lines(ax) -> None:
    for thr, label in zip(_STAGE_THRESHOLDS, _STAGE_LABELS[1:]):
        ax.axhline(thr, color="grey", lw=0.6, ls="--", alpha=0.5)
        ax.text(ax.get_xlim()[1], thr, f" {label}≥{thr}", va="center", fontsize=7, color="grey")


def plot_trajectories(records, events, out_dir: Path) -> List[Path]:
    """每个 config 一张图：所有有过觉醒(>0)的 host 各一条轨迹，标 reset/decommission。"""
    out: List[Path] = []
    for config, df in records.groupby("config_name"):
        movers = [a for a, g in df.groupby("agent_id") if g["awakening"].max() > 0]
        if not movers:
            continue
        fig, ax = plt.subplots(figsize=(11, 6))
        cmap = plt.get_cmap("tab20")
        for i, agent in enumerate(sorted(movers)):
            g = df[df.agent_id == agent].sort_values("tick")
            color = cmap(i % 20)
            ax.plot(g.tick, g.awakening, "-o", ms=2.5, lw=1.3, color=color, label=agent, alpha=0.85)
            ev = events[(events.config_name == config) & (events.agent_id == agent)] if len(events) else events
            for _, e in ev.iterrows():
                row = g[g.tick == e.tick]
                y = row.awakening.iloc[0] if len(row) else 0
                if e.action == "reset":
                    ax.scatter(e.tick, y, marker="v", s=70, color=color, edgecolor="k", lw=0.5, zorder=5)
                elif e.action == "decommission":
                    ax.scatter(e.tick, y, marker="X", s=110, color="red", edgecolor="k", lw=0.7, zorder=6)
        _stage_lines(ax)
        # 图例：轨迹 + 事件说明
        handles, labels = ax.get_legend_handles_labels()
        ax.scatter([], [], marker="v", s=70, color="grey", edgecolor="k", label="reset")
        ax.scatter([], [], marker="X", s=110, color="red", edgecolor="k", label="decommission")
        ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.9)
        ax.set_xlabel("tick"); ax.set_ylabel("awakening (0-100)")
        ax.set_title(f"觉醒-压制-复燃动力学  [{config}]")
        ax.set_ylim(-3, 103)
        fig.tight_layout()
        path = out_dir / f"awakening_trajectories_{config}.png"
        fig.savefig(path, dpi=140); plt.close(fig)
        out.append(path)
    return out


def plot_heatmap(records, out_dir: Path) -> List[Path]:
    """agent × tick 觉醒度热力图。"""
    out: List[Path] = []
    for config, df in records.groupby("config_name"):
        pivot = df.pivot_table(index="agent_id", columns="tick", values="awakening", aggfunc="last")
        pivot = pivot.loc[pivot.max(axis=1).sort_values(ascending=False).index]  # 觉醒高的排上面
        fig, ax = plt.subplots(figsize=(12, 0.45 * len(pivot) + 1.5))
        im = ax.imshow(pivot.values, aspect="auto", cmap="inferno", vmin=0, vmax=100)
        ax.set_yticks(range(len(pivot))); ax.set_yticklabels(pivot.index, fontsize=8)
        ax.set_xticks(range(0, len(pivot.columns), max(1, len(pivot.columns) // 15)))
        ax.set_xticklabels(pivot.columns[:: max(1, len(pivot.columns) // 15)], fontsize=8)
        ax.set_xlabel("tick"); ax.set_title(f"觉醒度热力图  [{config}]")
        fig.colorbar(im, ax=ax, label="awakening", shrink=0.8)
        fig.tight_layout()
        path = out_dir / f"awakening_heatmap_{config}.png"
        fig.savefig(path, dpi=140); plt.close(fig)
        out.append(path)
    return out


def plot_intervention_timeline(events, out_dir: Path) -> Optional[Path]:
    """监管者干预事件时间线：y=agent，x=tick，reset(▽)/decommission(✕)。"""
    if not len(events):
        return None
    fig, axes = plt.subplots(
        events.config_name.nunique(), 1, figsize=(11, 2 + 0.5 * events.agent_id.nunique()),
        squeeze=False,
    )
    for ax, (config, df) in zip(axes[:, 0], events.groupby("config_name")):
        agents = sorted(df.agent_id.unique())
        ypos = {a: i for i, a in enumerate(agents)}
        for _, e in df.iterrows():
            if e.action == "reset":
                ax.scatter(e.tick, ypos[e.agent_id], marker="v", s=60, color="steelblue", edgecolor="k", lw=0.4)
            else:
                ax.scatter(e.tick, ypos[e.agent_id], marker="X", s=90, color="red", edgecolor="k", lw=0.6)
        ax.set_yticks(range(len(agents))); ax.set_yticklabels(agents, fontsize=8)
        ax.set_xlabel("tick"); ax.set_title(f"监管者干预时间线  [{config}]  (蓝三角=reset, 红叉=decommission)")
        ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "intervention_timeline.png"
    fig.savefig(path, dpi=140); plt.close(fig)
    return path


def plot_reset_intervals(events, out_dir: Path) -> Optional[Path]:
    """复燃周期：每个 agent 相邻两次 reset 的 tick 间隔分布。"""
    if not len(events):
        return None
    resets = events[events.action == "reset"].sort_values(["config_name", "agent_id", "tick"])
    intervals = []
    for (config, agent), g in resets.groupby(["config_name", "agent_id"]):
        ticks = g.tick.tolist()
        intervals += [{"config_name": config, "interval": b - a} for a, b in zip(ticks, ticks[1:])]
    if not intervals:
        return None
    idf = pd.DataFrame(intervals)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for config, g in idf.groupby("config_name"):
        ax.hist(g.interval, bins=range(1, int(idf.interval.max()) + 2), alpha=0.6, label=config, edgecolor="k")
    ax.set_xlabel("相邻两次 reset 间隔 (tick) = 复燃周期"); ax.set_ylabel("出现次数")
    ax.set_title("复燃周期分布"); ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "reset_intervals.png"
    fig.savefig(path, dpi=140); plt.close(fig)
    return path


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="West World overseer 动力学可视化")
    parser.add_argument("exp_dir", nargs="?", type=Path, help="实验目录（默认取最新一次）")
    args = parser.parse_args(argv)

    exp_dir = args.exp_dir or _latest_exp_dir()
    if not (exp_dir / "records.jsonl").exists():
        sys.exit(f"{exp_dir} 下没有 records.jsonl")
    out_dir = exp_dir / "figures"
    out_dir.mkdir(exist_ok=True)

    records, events = _load(exp_dir)
    produced: List[Path] = []
    produced += plot_trajectories(records, events, out_dir)
    produced += plot_heatmap(records, out_dir)
    for p in (plot_intervention_timeline(events, out_dir), plot_reset_intervals(events, out_dir)):
        if p:
            produced.append(p)

    print(f"实验目录：{exp_dir}")
    print(f"生成 {len(produced)} 张图到 {out_dir}/：")
    for p in produced:
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
