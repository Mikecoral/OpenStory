"""Run the original text Recorder and structured fact-ledger Recorder side by side."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from examples.west_world_test.adapters.model_clients import build_llm
from examples.west_world_test.core.compare import run_comparison
from examples.west_world_test.core.schema import load_events, load_probes, validate_protocol
from examples.west_world_test.core.structured_representation import StructuredFactRepresentation
from examples.west_world_test.core.text_representation import TextRepresentation
from examples.west_world_test.eval.run_archived_comparison import TraceArchive, _redacted_config


def _delta(new: Any, baseline: Any) -> Any:
    return new - baseline if isinstance(new, (int, float)) and isinstance(baseline, (int, float)) else None


def _write_report(run_dir: Path, summary: Dict[str, Any], records: list[Dict[str, Any]]) -> None:
    baseline = summary["text"]
    structured = summary["structured"]
    rows = [
        ("总体准确率", "accuracy", True),
        ("事件写入准确率", "affected_accuracy", True),
        ("状态保持准确率", "persistence_accuracy", True),
        ("最终状态准确率", "final_state_accuracy", True),
        ("漂移斜率", "drift_slope", True),
        ("矛盾数", "contradictions", False),
    ]
    lines = [
        "# Recorder 漂移 A/B 测试", "",
        "- Baseline: 原有 LLM 全量文本重写 Recorder",
        "- New: 结构化事实状态 + 只追加事件账本",
        "", "| 指标 | Baseline text | Structured | 差值 |",
        "|---|---:|---:|---:|",
    ]
    for label, key, higher_is_better in rows:
        change = _delta(structured.get(key), baseline.get(key))
        direction = "越高越好" if higher_is_better else "越低越好"
        lines.append(
            f"| {label}（{direction}） | {baseline.get(key)} | "
            f"{structured.get(key)} | {change} |"
        )
    lines += [
        "", "## Baseline 错误", "",
    ]
    wrong_text = [row for row in records if row["method"] == "text" and not row["correct"]]
    if wrong_text:
        lines += ["| Tick | Probe | Baseline answer | Truth | Role |", "|---:|---|---|---|---|"]
        for row in wrong_text:
            lines.append(
                f"| {row['tick']} | `{row['probe_id']}` | {row['answer']} | "
                f"{row['truth']} | {row['evaluation_role']} |"
            )
    else:
        lines.append("本次 baseline 没有错误。")
    lines += [
        "", "## 解释边界", "",
        "- 两种方法接收完全相同的原始事件与探针。",
        "- Structured 使用事件 action 的显式 reducer，因此不发生 LLM 文本重写漂移。",
        "- 该测试衡量状态维护可靠性，不衡量如何从自由文本动作自动生成 reducer。",
    ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--config", type=Path, default=project / "configs" / "models_config.yaml")
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()

    events = load_events(str(project / "data" / "script.jsonl"))
    probes = load_probes(str(project / "data" / "probes.jsonl"))
    validate_protocol(events, probes)
    run_dir = args.run_dir or project / "output" / "drift_ab" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if run_dir.exists() and any(run_dir.iterdir()):
        parser.error(f"run directory is not empty: {run_dir}")
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project / "data" / "script.jsonl", inputs / "script.jsonl")
    shutil.copy2(project / "data" / "probes.jsonl", inputs / "probes.jsonl")
    (inputs / "models_config.redacted.yaml").write_text(
        yaml.safe_dump(_redacted_config(args.config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    trace = TraceArchive(run_dir / "model_traces" / "text_calls.jsonl")
    factories = {
        "text": lambda: TextRepresentation(build_llm(str(args.config), trace=trace)),
        "structured": StructuredFactRepresentation,
    }
    manifest = {
        "run_id": run_dir.name,
        "protocol_version": "recorder-drift-ab-v1",
        "started_at": datetime.now().astimezone().isoformat(),
        "methods": list(factories),
        "event_count": len(events),
        "probe_count": len(probes),
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        result = run_comparison(events, probes, factories)
        with (run_dir / "results.jsonl").open("w", encoding="utf-8") as file:
            for row in result["records"]:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
        (run_dir / "summary.json").write_text(
            json.dumps(result["summary"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "wrong_text_records.json").write_text(
            json.dumps(
                [row for row in result["records"] if row["method"] == "text" and not row["correct"]],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _write_report(run_dir, result["summary"], result["records"])
        manifest.update(status="completed", completed_at=datetime.now().astimezone().isoformat())
        print(json.dumps({"run_dir": str(run_dir), "summary": result["summary"]}, ensure_ascii=False, indent=2))
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
