"""论文级长 tick 仿真实验编排器。

观测「自然觉醒 → overseer 压制 → 残痕复燃」的动力学曲线，输出可统计、可画图的数据。
**不是 pytest 硬断言**——是数据收集与现象观察工具。

设计：
- 一个「参数矩阵」= 若干 named config，每个 config 是一组 env 覆盖。
- 每个 config 用**独立子进程**跑 `run_simulation`（Ray 干净启停，一个 run 崩不影响其他）。
- 跑完从该 run 的 `internal/agent_states.jsonl` 提取动力学指标（见 metrics.py）。
- 聚合写出 records.jsonl（tidy）/ events.jsonl / summary.json，供 notebook 画图。

默认矩阵小而可配置（overseer on/off，~30 tick）。论文级完整矩阵（多阈值/长 tick）
由 `--matrix` 指向的 yaml 驱动。

用法（仓库根目录，需 Redis 在线 + 真实 LLM）：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \\
        python -m examples.west_world_test.experiments.overseer_dynamics --ticks 30

    # 指定完整矩阵 + 输出目录
    python -m examples.west_world_test.experiments.overseer_dynamics \\
        --matrix examples/west_world_test/experiments/configs/full_matrix.yaml \\
        --ticks 80 --out /tmp/ww-exp

    # 只跑矩阵里某几个 config
    python -m examples.west_world_test.experiments.overseer_dynamics --select overseer_on,overseer_off

    # 干跑：只打印将要执行的 config，不真跑
    python -m examples.west_world_test.experiments.overseer_dynamics --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from examples.west_world_test.experiments import metrics

# experiments/ → west_world_test → examples → OpenStory
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
_DEFAULT_MATRIX = _THIS_DIR / "configs" / "default_matrix.yaml"


def _load_matrix(path: Path) -> List[Dict[str, Any]]:
    """矩阵 yaml 结构：{configs: [{name, env: {KEY: VAL, ...}}, ...]}。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    configs = data.get("configs", []) if isinstance(data, dict) else data
    out: List[Dict[str, Any]] = []
    for entry in configs:
        name = entry["name"]
        env = {str(k): str(v) for k, v in (entry.get("env") or {}).items()}
        out.append({"name": name, "env": env})
    return out


def _build_env(config_env: Dict[str, str], run_dir: Path, ticks: int, recorder_mode: str) -> Dict[str, str]:
    """父环境 + 实验固定项 + config 覆盖。config env 优先级最高。"""
    env = os.environ.copy()
    pythonpath = os.pathsep.join([
        str(_REPO_ROOT),
        str(_REPO_ROOT / "packages" / "agentkernel-distributed"),
        env.get("PYTHONPATH", ""),
    ]).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    env["WW_MAX_TICKS"] = str(ticks)
    env["WW_RUN_DIR"] = str(run_dir)
    env.setdefault("WW_RECORDER_MODE", recorder_mode)
    env.update(config_env)  # config 覆盖最后生效
    return env


def _run_one(config: Dict[str, Any], run_dir: Path, ticks: int, recorder_mode: str) -> Dict[str, Any]:
    """子进程跑一次 run_simulation。返回执行元数据（不含指标）。"""
    env = _build_env(config["env"], run_dir, ticks, recorder_mode)
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "examples.west_world_test.run_simulation"],
        cwd=str(_REPO_ROOT),
        env=env,
    )
    return {
        "config_name": config["name"],
        "env": config["env"],
        "run_dir": str(run_dir),
        "returncode": proc.returncode,
        "duration_seconds": round(time.perf_counter() - started, 2),
    }


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_experiment(
    matrix: List[Dict[str, Any]],
    out_root: Path,
    ticks: int,
    recorder_mode: str,
) -> Path:
    """跑完整矩阵并落盘聚合结果。返回本次实验目录。"""
    exp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_dir = out_root / exp_id
    runs_dir = exp_dir / "runs"
    exp_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "experiment_id": exp_id,
        "started_at": datetime.now().astimezone().isoformat(),
        "ticks": ticks,
        "recorder_mode": recorder_mode,
        "configs": [c["name"] for c in matrix],
        "runs": [],
    }
    summaries: List[Dict[str, Any]] = []

    for config in matrix:
        run_dir = runs_dir / config["name"]
        print(f"\n===== [experiment] config={config['name']} env={config['env']} ticks={ticks} =====")
        meta = _run_one(config, run_dir, ticks, recorder_mode)
        manifest["runs"].append(meta)
        if meta["returncode"] != 0:
            print(f"[experiment] config {config['name']} 子进程退出码 {meta['returncode']}，仍尝试提取已落盘数据")

        rows = metrics.load_state_rows(run_dir)
        summary = metrics.summarize_run(run_dir, config["name"], env=config["env"], rows=rows)
        summary["returncode"] = meta["returncode"]
        summary["duration_seconds"] = meta["duration_seconds"]
        summaries.append(summary)

        _write_json(exp_dir / "metrics" / f"{config['name']}.json", summary)
        _write_jsonl(exp_dir / "records.jsonl", metrics.tidy_records(run_dir, config["name"], rows=rows))
        _write_jsonl(exp_dir / "events.jsonl", [
            {"config_name": config["name"], **ev} for ev in summary["intervention_events"]
        ])
        _write_jsonl(exp_dir / "events.jsonl", [
            {"config_name": config["name"], "action": "contagion", **ev}
            for ev in metrics.contagion_events(rows)
        ])
        _write_json(exp_dir / "manifest.json", manifest)

    manifest["completed_at"] = datetime.now().astimezone().isoformat()
    _write_json(exp_dir / "manifest.json", manifest)
    _write_json(exp_dir / "summary.json", {
        "experiment_id": exp_id,
        "ticks": ticks,
        "configs": [
            {
                "config_name": s["config_name"],
                "ok": s["ok"],
                "returncode": s["returncode"],
                "totals": s["totals"],
            }
            for s in summaries
        ],
    })
    print(f"\n[experiment] 完成。结果目录：{exp_dir}")
    print(f"[experiment] tidy 记录：{exp_dir / 'records.jsonl'}")
    print(f"[experiment] 干预事件：{exp_dir / 'events.jsonl'}")
    print(f"[experiment] 聚合摘要：{exp_dir / 'summary.json'}")
    return exp_dir


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="West World overseer 动力学长 tick 实验编排器")
    parser.add_argument("--matrix", type=Path, default=_DEFAULT_MATRIX,
                        help="参数矩阵 yaml（默认 configs/default_matrix.yaml）")
    parser.add_argument("--ticks", type=int, default=30, help="每个 config 的 tick 数（默认 30）")
    parser.add_argument("--out", type=Path,
                        default=_THIS_DIR.parent / "output" / "sim_runs",
                        help="实验输出根目录（默认 output/sim_runs，与单次仿真归档同处）")
    parser.add_argument("--recorder-mode", default="structured", help="WW_RECORDER_MODE（默认 structured）")
    parser.add_argument("--select", default="", help="逗号分隔的 config 名子集（默认全跑）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的 config，不真跑")
    args = parser.parse_args(argv)

    matrix = _load_matrix(args.matrix)
    if args.select:
        wanted = {s.strip() for s in args.select.split(",") if s.strip()}
        matrix = [c for c in matrix if c["name"] in wanted]
        if not matrix:
            parser.error(f"--select={args.select} 未匹配到任何 config（矩阵：{args.matrix}）")

    if args.dry_run:
        print(f"[dry-run] 矩阵：{args.matrix}")
        print(f"[dry-run] ticks={args.ticks} recorder_mode={args.recorder_mode} out={args.out}")
        for c in matrix:
            print(f"[dry-run]   config={c['name']} env={c['env']}")
        return

    run_experiment(matrix, args.out, args.ticks, args.recorder_mode)


if __name__ == "__main__":
    main()
