"""Distributed-kernel runner for the West World recorder comparison."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Awaitable, Callable, Dict, List

import ray

from agentkernel_distributed.mas.builder import Builder
from examples.west_world_test.core.schema import Event, Probe, load_events, load_probes
from examples.west_world_test.registry import RESOURCES_MAPS

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_PATH, "..", ".."))
PACKAGE_PATH = os.path.join(PROJECT_ROOT, "packages", "agentkernel-distributed")
EnvironmentCall = Callable[[str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


async def run_kernel_loop(events: List[Event], probes: List[Probe], environment_call: EnvironmentCall) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for event in sorted(events, key=lambda item: item.tick):
        await environment_call("scene", "apply_event", event.__dict__)
        for probe in probes:
            result = await environment_call("scene", "probe", probe.__dict__)
            for method, answer in result["answers"].items():
                records.append({
                    "tick": event.tick,
                    "method": method,
                    "probe_id": result["probe_id"],
                    "truth": result["truth"],
                    "had_relevant_event": result["had_relevant_event"],
                    **answer,
                })
    return records


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(PROJECT_PATH, "results.jsonl"))
    args = parser.parse_args()
    events = load_events(os.path.join(PROJECT_PATH, "data", "script.jsonl"))
    probes = load_probes(os.path.join(PROJECT_PATH, "data", "probes.jsonl"))

    python_path = os.pathsep.join([PROJECT_ROOT, PACKAGE_PATH, os.environ.get("PYTHONPATH", "")])
    runtime_env = {"working_dir": PROJECT_PATH, "env_vars": {"PYTHONPATH": python_path}}
    ray.init(runtime_env=runtime_env)
    builder = Builder(PROJECT_PATH, RESOURCES_MAPS)
    pod_manager, _ = await builder.init()

    async def environment_call(component: str, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await pod_manager.run_environment.remote(component, method, payload)

    try:
        records = await run_kernel_loop(events, probes, environment_call)
        with open(args.out, "w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        print(f"wrote {len(records)} records to {args.out}")
    finally:
        await pod_manager.close.remote()
        ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
