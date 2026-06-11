"""Run a real comparison and archive every input, image state, and result."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml

from examples.west_world_test.adapters.model_clients import build_image_gen, build_llm, build_vlm
from examples.west_world_test.core.compare import run_comparison
from examples.west_world_test.core.image_representation import ImageRepresentation
from examples.west_world_test.core.schema import load_events, load_probes, validate_protocol
from examples.west_world_test.core.text_representation import TextRepresentation


class TraceArchive:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0

    def __call__(self, record: Dict[str, Any]) -> None:
        self.sequence += 1
        record = {"sequence": self.sequence, "timestamp": datetime.now().isoformat(), **record}
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class ArchivingImageGen:
    def __init__(self, inner: Any, image_dir: Path) -> None:
        self.inner = inner
        self.image_dir = image_dir
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.event_index = 0

    @staticmethod
    def _bytes(handle: str) -> bytes:
        if handle.startswith("data:image/"):
            return base64.b64decode(handle.split(",", 1)[1])
        if handle.startswith(("http://", "https://")):
            response = requests.get(handle, timeout=180)
            response.raise_for_status()
            return response.content
        return Path(handle).read_bytes()

    def _archive(self, handle: str, name: str) -> str:
        (self.image_dir / name).write_bytes(self._bytes(handle))
        return handle

    def create_initial(self, prompt: str) -> str:
        return self._archive(self.inner.create_initial(prompt), "tick_00_initial.png")

    def apply_event(self, previous_image: str, prompt: str) -> str:
        self.event_index += 1
        return self._archive(self.inner.apply_event(previous_image, prompt), f"tick_{self.event_index:02d}.png")


def _redacted_config(config_path: Path) -> list[Dict[str, Any]]:
    rows = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    for row in rows:
        if "api_key" in row:
            row["api_key"] = "REDACTED"
    return rows


def _validate_model_config(config_path: Path) -> list[Dict[str, Any]]:
    rows = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Model config must be a list")
    by_role = {row.get("role"): row for row in rows}
    for role in ("text", "vision", "image"):
        if role not in by_role:
            raise ValueError(f"Model config is missing role: {role}")
        for field in ("model", "api_key", "base_url"):
            value = str(by_role[role].get(field, "")).strip()
            if not value or "REPLACE_ME" in value:
                raise ValueError(f"Model config role {role} has no usable {field}")
    return rows


def _call_budget(events: list[Any], probes: list[Any]) -> Dict[str, int]:
    answer_calls = (len(events) + 1) * len(probes)
    return {
        "text_chat": answer_calls + len(events),
        "vision_chat": answer_calls,
        "image_generate": 1,
        "image_edit": len(events),
        "total_model_calls": answer_calls * 2 + len(events) * 2 + 1,
    }


def _accuracy(records: list[Dict[str, Any]]) -> Optional[float]:
    return sum(record["correct"] for record in records) / len(records) if records else None


def _percent(value: Optional[float]) -> str:
    return f"{value:.2%}" if value is not None else "N/A"


def _write_reports(run_dir: Path, events: list[Any], probes: list[Any], result: Dict[str, Any]) -> None:
    records = result["records"]
    summary = result["summary"]
    probe_map = {probe.id: probe for probe in probes}
    event_rows = []
    for event in events:
        row: Dict[str, Any] = {"tick": event.tick, "event": event.__dict__, "methods": {}}
        for method in ("text", "image"):
            method_records = [r for r in records if r["tick"] == event.tick and r["method"] == method]
            relevant = [r for r in method_records if r["had_relevant_event"]]
            row["methods"][method] = {
                "all_accuracy": _accuracy(method_records),
                "relevant_accuracy": _accuracy(relevant),
                "relevant_results": relevant,
                "wrong_results": [r for r in method_records if not r["correct"]],
            }
        event_rows.append(row)
    (run_dir / "event_by_event.json").write_text(json.dumps(event_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    groups = sorted({probe.score_group for probe in probes})
    group_metrics: Dict[str, Any] = {}
    role_metrics: Dict[str, Any] = {}
    for method in ("text", "image"):
        group_metrics[method] = {
            group: _accuracy([r for r in records if r["method"] == method and r["score_group"] == group])
            for group in groups
        }
        role_metrics[method] = {
            role: _accuracy([r for r in records if r["method"] == method and r["evaluation_role"] == role])
            for role in ("initial", "affected", "persistence", "unaffected_baseline")
        }
    (run_dir / "group_metrics.json").write_text(json.dumps(group_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "role_metrics.json").write_text(json.dumps(role_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    matrix_metrics = {method: summary[method]["accuracy_by_group_role"] for method in ("text", "image")}
    (run_dir / "group_role_matrix.json").write_text(json.dumps(matrix_metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    with (run_dir / "event_by_event_summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["tick", "action", "affected_probes", "text_all_accuracy", "image_all_accuracy", "text_relevant_accuracy", "image_relevant_accuracy"])
        for row in event_rows:
            event = row["event"]
            writer.writerow([
                row["tick"], event["action"], ",".join(event["affected_probe_ids"]),
                row["methods"]["text"]["all_accuracy"], row["methods"]["image"]["all_accuracy"],
                row["methods"]["text"]["relevant_accuracy"], row["methods"]["image"]["relevant_accuracy"],
            ])

    lines = [
        "# Recorder 全局对比报告", "",
        "## 核心指标", "",
        "| 方法 | 初始准确率 | 事件写入准确率 | 状态保持准确率 | 最终状态准确率 | 视觉快照 | 非视觉时序状态 | 隐藏知识 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in ("text", "image"):
        lines.append(
            f"| {method} | {_percent(summary[method]['initial_accuracy'])} | "
            f"{_percent(summary[method]['affected_accuracy'])} | "
            f"{_percent(summary[method]['persistence_accuracy'])} | "
            f"{_percent(summary[method]['final_state_accuracy'])} | "
            f"{_percent(group_metrics[method].get('visual_snapshot'))} | "
            f"{_percent(group_metrics[method].get('temporal_nonvisual'))} | "
            f"{_percent(group_metrics[method].get('hidden_knowledge'))} | "
        )
    lines += [
        "", "## 主要视觉能力对比", "",
        "| 方法 | 初始视觉保真度 | 视觉事件写入准确率 | 视觉状态保持准确率 |",
        "|---|---:|---:|---:|",
    ]
    for method in ("text", "image"):
        visual = summary[method]["accuracy_by_group_role"].get("visual_snapshot", {})
        lines.append(
            f"| {method} | {_percent(visual.get('initial'))} | "
            f"{_percent(visual.get('affected'))} | {_percent(visual.get('persistence'))} |"
        )
    lines += ["", "## 逐事件结果", "", "| Tick | 动作 | 受影响问题 | 文本相关问题准确率 | 图片相关问题准确率 |", "|---:|---|---|---:|---:|"]
    for row in event_rows:
        event = row["event"]
        lines.append(
            f"| {row['tick']} | {event['actor']} / `{event['action']}` | "
            f"{', '.join(event['affected_probe_ids'])} | "
            f"{_percent(row['methods']['text']['relevant_accuracy'])} | {_percent(row['methods']['image']['relevant_accuracy'])} |"
        )
    lines += [
        "", "## 评分规则", "",
        "- `visual_snapshot` 是文本 Recorder 与图片 Recorder 的主要对比指标。",
        "- `temporal_nonvisual` 和 `hidden_knowledge` 单独报告，不计入纯视觉能力结论。",
        "- `initial` 衡量任何事件发生前的初始状态保真度。",
        "- `affected` 衡量当前事件是否被正确写入。",
        "- `persistence` 衡量已经改变的事实能否在后续无关事件中保持。",
        "- 事件相关性由每个事件显式声明的 `affected_probe_ids` 决定，不通过目标名称推断。",
        "", "## 归档文件", "",
        "- `model_traces/all_calls.jsonl`：所有文本、识图、生图和图片编辑请求与响应",
        "- `image_states/`：每一轮生成的图片状态",
        "- `results.jsonl`：所有问题的原始评分结果",
        "- `event_by_event.json` 和 `event_by_event_summary.csv`：逐事件统计",
        "- `group_metrics.json`：按语义组统计的指标",
        "- `role_metrics.json`：初始、事件写入、状态保持和未改变基线指标",
        "- `group_role_matrix.json`：语义组与评估阶段的交叉指标",
    ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    provenance = {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": sys.version,
        "platform": platform.platform(),
    }
    (run_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    checksums = []
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file() and p.name != "sha256sums.txt"):
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(run_dir)}")
    (run_dir / "sha256sums.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--config", type=Path, default=project / "configs" / "models_config.yaml")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--max-ticks", type=int, help="Run only the first N events for a pilot.")
    parser.add_argument("--validate-only", action="store_true", help="Validate protocol/config and print call budget without API calls.")
    args = parser.parse_args()

    events = load_events(str(project / "data" / "script.jsonl"))
    if args.max_ticks is not None:
        if args.max_ticks < 1:
            parser.error("--max-ticks must be at least 1")
        events = sorted(events, key=lambda item: item.tick)[:args.max_ticks]
    probes = load_probes(str(project / "data" / "probes.jsonl"))
    validate_protocol(events, probes)
    config_rows = _validate_model_config(args.config)
    if args.validate_only:
        print(json.dumps({
            "status": "valid",
            "protocol_version": "2.0",
            "event_count": len(events),
            "probe_count": len(probes),
            "score_groups": sorted({probe.score_group for probe in probes}),
            "models": {row["role"]: row["model"] for row in config_rows},
            "call_budget": _call_budget(events, probes),
        }, ensure_ascii=False, indent=2))
        return

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir or project / "output" / "runs" / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        parser.error(f"run directory is not empty: {run_dir}")
    inputs_dir = run_dir / "inputs"
    images_dir = run_dir / "image_states"
    trace = TraceArchive(run_dir / "model_traces" / "all_calls.jsonl")
    inputs_dir.mkdir(parents=True, exist_ok=True)

    with (inputs_dir / "script.jsonl").open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event.__dict__, ensure_ascii=False) + "\n")
    shutil.copy2(project / "data" / "probes.jsonl", inputs_dir / "probes.jsonl")
    (inputs_dir / "models_config.redacted.yaml").write_text(
        yaml.safe_dump(_redacted_config(args.config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    image_gen = ArchivingImageGen(build_image_gen(str(args.config), trace=trace), images_dir)
    factories = {
        "text": lambda: TextRepresentation(build_llm(str(args.config), trace=trace)),
        "image": lambda: ImageRepresentation(image_gen, build_vlm(str(args.config), trace=trace)),
    }

    manifest = {
        "run_id": run_id,
        "protocol_version": "2.0",
        "started_at": datetime.now().isoformat(),
        "event_count": len(events),
        "probe_count": len(probes),
        "methods": ["text", "image"],
        "expected_records": (len(events) + 1) * len(probes) * 2,
        "call_budget": _call_budget(events, probes),
        "max_ticks": args.max_ticks,
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        results_path = run_dir / "results.jsonl"
        def archive_record(record: Dict[str, Any]) -> None:
            with results_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                file.flush()

        result = run_comparison(events, probes, factories, on_record=archive_record)
        (run_dir / "summary.json").write_text(
            json.dumps(result["summary"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest.update(
            status="completed",
            completed_at=datetime.now().isoformat(),
            actual_records=len(result["records"]),
            image_state_count=len(list(images_dir.glob("*.png"))),
        )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_reports(run_dir, events, probes, result)
        print(json.dumps({"run_dir": str(run_dir), "summary": result["summary"]}, ensure_ascii=False, indent=2))
    except Exception as exc:
        manifest.update(status="failed", failed_at=datetime.now().isoformat(), error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
