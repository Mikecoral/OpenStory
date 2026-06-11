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
from typing import Any, Dict

import requests
import yaml

from examples.west_world_test.adapters.model_clients import build_image_gen, build_llm, build_vlm
from examples.west_world_test.core.compare import run_comparison
from examples.west_world_test.core.image_representation import ImageRepresentation
from examples.west_world_test.core.schema import load_events, load_probes
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


def _accuracy(records: list[Dict[str, Any]]) -> float:
    return sum(record["correct"] for record in records) / len(records) if records else 0.0


def _write_reports(run_dir: Path, events: list[Any], probes: list[Any], result: Dict[str, Any]) -> None:
    records = result["records"]
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
    for method in ("text", "image"):
        group_metrics[method] = {
            group: _accuracy([r for r in records if r["method"] == method and r["score_group"] == group])
            for group in groups
        }
    (run_dir / "group_metrics.json").write_text(json.dumps(group_metrics, ensure_ascii=False, indent=2), encoding="utf-8")

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

    summary = result["summary"]
    lines = [
        "# Global Recorder Comparison Report", "",
        "## Overall", "",
        "| Method | Overall accuracy | Visual physical | Hidden knowledge | Drift slope | Contradictions |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in ("text", "image"):
        lines.append(
            f"| {method} | {summary[method]['accuracy']:.2%} | "
            f"{group_metrics[method].get('visual_physical', 0):.2%} | "
            f"{group_metrics[method].get('hidden_knowledge', 0):.2%} | "
            f"{summary[method]['drift_slope']:.4f} | {summary[method]['contradictions']} |"
        )
    lines += ["", "## Event-by-Event", "", "| Tick | Action | Affected probes | Text relevant | Image relevant |", "|---:|---|---|---:|---:|"]
    for row in event_rows:
        event = row["event"]
        lines.append(
            f"| {row['tick']} | {event['actor']} / `{event['action']}` | "
            f"{', '.join(event['affected_probe_ids'])} | "
            f"{row['methods']['text']['relevant_accuracy']:.2%} | {row['methods']['image']['relevant_accuracy']:.2%} |"
        )
    lines += [
        "", "## Scoring Policy", "",
        "- `visual_physical` is the primary score for comparing Text and Image Recorders.",
        "- `hidden_knowledge` is reported separately and is not included in the pure visual capability conclusion.",
        "- Event relevance comes from each event's explicit `affected_probe_ids`; it is not inferred from target names.",
        "", "## Archived Outputs", "",
        "- `model_traces/all_calls.jsonl`: every text, vision, image-generate, and image-edit request/response trace",
        "- `image_states/`: every generated image state",
        "- `results.jsonl`: every scored probe answer",
        "- `event_by_event.json` and `event_by_event_summary.csv`: exact event-level statistics",
        "- `group_metrics.json`: visual and hidden-knowledge scores",
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
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir or project / "output" / "runs" / run_id
    inputs_dir = run_dir / "inputs"
    images_dir = run_dir / "image_states"
    trace = TraceArchive(run_dir / "model_traces" / "all_calls.jsonl")
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for name in ("script.jsonl", "probes.jsonl"):
        shutil.copy2(project / "data" / name, inputs_dir / name)
    (inputs_dir / "models_config.redacted.yaml").write_text(
        yaml.safe_dump(_redacted_config(args.config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    events = load_events(str(project / "data" / "script.jsonl"))
    probes = load_probes(str(project / "data" / "probes.jsonl"))
    image_gen = ArchivingImageGen(build_image_gen(str(args.config), trace=trace), images_dir)
    factories = {
        "text": lambda: TextRepresentation(build_llm(str(args.config), trace=trace)),
        "image": lambda: ImageRepresentation(image_gen, build_vlm(str(args.config), trace=trace)),
    }

    manifest = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "event_count": len(events),
        "probe_count": len(probes),
        "methods": ["text", "image"],
        "expected_records": len(events) * len(probes) * 2,
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        result = run_comparison(events, probes, factories)
        with (run_dir / "results.jsonl").open("w", encoding="utf-8") as file:
            for record in result["records"]:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
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
