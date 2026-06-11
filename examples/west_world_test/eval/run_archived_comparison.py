"""Run a real comparison and archive every input, image state, and result."""
from __future__ import annotations

import argparse
import base64
import json
import shutil
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
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for name in ("script.jsonl", "probes.jsonl"):
        shutil.copy2(project / "data" / name, inputs_dir / name)
    (inputs_dir / "models_config.redacted.yaml").write_text(
        yaml.safe_dump(_redacted_config(args.config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    events = load_events(str(project / "data" / "script.jsonl"))
    probes = load_probes(str(project / "data" / "probes.jsonl"))
    image_gen = ArchivingImageGen(build_image_gen(str(args.config)), images_dir)
    factories = {
        "text": lambda: TextRepresentation(build_llm(str(args.config))),
        "image": lambda: ImageRepresentation(image_gen, build_vlm(str(args.config))),
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
        print(json.dumps({"run_dir": str(run_dir), "summary": result["summary"]}, ensure_ascii=False, indent=2))
    except Exception as exc:
        manifest.update(status="failed", failed_at=datetime.now().isoformat(), error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
