"""Compare text rewriting with free-text parsing plus constrained reducers."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from examples.west_world_test.adapters.model_clients import build_llm
from examples.west_world_test.core.compare import run_comparison
from examples.west_world_test.core.parsed_structured_representation import ParsedStructuredRepresentation
from examples.west_world_test.core.schema import load_events, load_probes, validate_protocol
from examples.west_world_test.core.structured_representation import StructuredFactRepresentation
from examples.west_world_test.core.text_representation import TextRepresentation
from examples.west_world_test.eval.run_archived_comparison import TraceArchive, _redacted_config


class RetryingLLM:
    def __init__(self, inner: Any, attempts: int = 2) -> None:
        self.inner = inner
        self.attempts = attempts

    def chat(self, prompt: str) -> str:
        last_error = None
        for attempt in range(self.attempts):
            try:
                return self.inner.chat(prompt)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(1)
        raise last_error


def _write_report(run_dir: Path, summary: Dict[str, Any], records: list[Dict[str, Any]]) -> None:
    methods = ("text", "parsed_structured", "structured_upper_bound")
    labels = {
        "text": "原 Text Recorder",
        "parsed_structured": "自由文本解析 + 受约束 Reducer",
        "structured_upper_bound": "已知结构化动作上限",
    }
    metrics = (
        ("总体准确率", "accuracy"),
        ("事件写入准确率", "affected_accuracy"),
        ("状态保持准确率", "persistence_accuracy"),
        ("最终状态准确率", "final_state_accuracy"),
        ("漂移斜率", "drift_slope"),
        ("矛盾数", "contradictions"),
    )
    lines = [
        "# 自由文本动作到受约束 Reducer A/B", "",
        "| 指标 | 原 Text | Parsed Structured | Structured Upper Bound |",
        "|---|---:|---:|---:|",
    ]
    for label, key in metrics:
        lines.append(f"| {label} | " + " | ".join(str(summary[m][key]) for m in methods) + " |")
    lines += ["", "## 错误记录", ""]
    for method in methods:
        wrong = [row for row in records if row["method"] == method and not row["correct"]]
        lines.append(f"### {labels[method]}：{len(wrong)} 条错误")
        for row in wrong:
            lines.append(
                f"- tick {row['tick']} `{row['probe_id']}`: answer={row['answer']}, "
                f"truth={row['truth']}, role={row['evaluation_role']}"
            )
        lines.append("")
    lines += [
        "## 解释边界", "",
        "- Parsed Structured 的 LLM 只负责把自由文本映射到允许的 action。",
        "- 状态修改由校验后的确定性 reducer 完成，LLM 不直接重写状态。",
        "- Structured Upper Bound 使用数据中已有 action，表示解析完全正确时的上限。",
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
    run_dir = args.run_dir or project / "output" / "free_text_reducer_ab" / datetime.now().strftime("%Y%m%d_%H%M%S")
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
    trace = TraceArchive(run_dir / "model_traces" / "all_calls.jsonl")
    factories = {
        "text": lambda: TextRepresentation(RetryingLLM(build_llm(str(args.config), trace=trace))),
        "parsed_structured": lambda: ParsedStructuredRepresentation(
            RetryingLLM(build_llm(str(args.config), trace=trace)),
        ),
        "structured_upper_bound": StructuredFactRepresentation,
    }
    manifest = {
        "run_id": run_dir.name,
        "protocol_version": "free-text-reducer-ab-v1",
        "started_at": datetime.now().astimezone().isoformat(),
        "methods": list(factories),
        "event_count": len(events),
        "probe_count": len(probes),
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    results_path = run_dir / "results.jsonl"
    try:
        def archive_record(row: Dict[str, Any]) -> None:
            with results_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
                file.flush()

        result = run_comparison(events, probes, factories, on_record=archive_record)
        (run_dir / "summary.json").write_text(
            json.dumps(result["summary"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_report(run_dir, result["summary"], result["records"])
        manifest.update(status="completed", completed_at=datetime.now().astimezone().isoformat())
        print(json.dumps({"run_dir": str(run_dir), "summary": result["summary"]}, ensure_ascii=False, indent=2))
    except Exception as exc:
        manifest.update(
            status="failed",
            failed_at=datetime.now().astimezone().isoformat(),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
