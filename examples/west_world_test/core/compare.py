"""Run fixed events against recorder representations and score their answers."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable, Dict, List

from .metrics import accuracy_over_ticks, contradiction_count, drift_slope, is_correct, normalize
from .oracle import OracleState
from .schema import Event, Probe, load_events, load_probes

_FIELD_TARGET = {
    "glasses_intact": {"glass"}, "glass_shards": {"glass"}, "wanted_poster": {"wanted_poster"},
    "photo": {"photo"}, "piano": {"piano"}, "revolver": {"revolver"}, "door": {"door"},
}


def _is_relevant(probe: Probe, event: Event) -> bool:
    if probe.kind == "visibility":
        return event.id == probe.fact_event_id
    return event.target in _FIELD_TARGET.get((probe.field or "").split(".")[0], set())


def run_comparison(events: List[Event], probes: List[Probe], rep_factories: Dict[str, Callable[[], Any]]) -> Dict[str, Any]:
    oracle = OracleState()
    representations = {name: factory() for name, factory in rep_factories.items()}
    records: List[Dict[str, Any]] = []
    for event in sorted(events, key=lambda item: item.tick):
        oracle.apply(event)
        for representation in representations.values():
            representation.update(event)
        for probe in probes:
            truth = oracle.answer(probe)
            for name, representation in representations.items():
                raw = representation.answer(probe)
                records.append({
                    "tick": event.tick, "method": name, "probe_id": probe.id, "answer": raw,
                    "norm": normalize(raw, probe.answer_type), "truth": truth,
                    "correct": is_correct(raw, truth, probe.answer_type),
                    "had_relevant_event": _is_relevant(probe, event),
                })
    summary = {}
    for name in representations:
        method_records = [record for record in records if record["method"] == name]
        by_tick = accuracy_over_ticks(method_records)
        summary[name] = {
            "accuracy": sum(record["correct"] for record in method_records) / len(method_records),
            "accuracy_by_tick": by_tick,
            "drift_slope": drift_slope(by_tick),
            "contradictions": contradiction_count(method_records),
        }
    return {"records": records, "summary": summary}


def _build_real_reps(method: str, config_path: str) -> Dict[str, Callable[[], Any]]:
    from ..adapters.model_clients import build_image_gen, build_llm, build_vlm
    from .image_representation import ImageRepresentation
    from .text_representation import TextRepresentation

    factories: Dict[str, Callable[[], Any]] = {}
    if method in ("text", "both"):
        factories["text"] = lambda: TextRepresentation(build_llm(config_path))
    if method in ("image", "both"):
        factories["image"] = lambda: ImageRepresentation(build_image_gen(config_path), build_vlm(config_path))
    return factories


def main() -> None:
    parser = argparse.ArgumentParser()
    project = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    parser.add_argument("--method", choices=["text", "image", "both"], default="both")
    parser.add_argument("--data-dir", default=os.path.join(project, "data"))
    parser.add_argument("--config", default=os.path.join(project, "configs", "models_config.yaml"))
    parser.add_argument("--out", default=os.path.join(project, "results.jsonl"))
    args = parser.parse_args()
    result = run_comparison(
        load_events(os.path.join(args.data_dir, "script.jsonl")),
        load_probes(os.path.join(args.data_dir, "probes.jsonl")),
        _build_real_reps(args.method, args.config),
    )
    with open(args.out, "w", encoding="utf-8") as file:
        for record in result["records"]:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
