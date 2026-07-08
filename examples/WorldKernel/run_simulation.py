from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = PROJECT_PATH.parents[1]
PACKAGES_ROOT = PROJECT_ROOT / "packages"


def _ensure_paths() -> None:
    for path in [PROJECT_ROOT, PROJECT_PATH]:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    if PACKAGES_ROOT.exists():
        for child in PACKAGES_ROOT.iterdir():
            if child.is_dir():
                child_str = str(child)
                if child_str not in sys.path:
                    sys.path.insert(0, child_str)


_ensure_paths()

os.environ["MAS_PROJECT_ABS_PATH"] = str(PROJECT_PATH)
os.environ["MAS_PROJECT_REL_PATH"] = "examples.WorldKernel"

import ray
from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger
from registry import RESOURCES_MAPS

logger = get_logger(__name__)


async def main(max_ticks: int | None = None) -> None:
    pod_manager = None
    system = None
    try:
        if not ray.is_initialized():
            ray.init(
                runtime_env={
                    "working_dir": str(PROJECT_PATH),
                    "env_vars": {"PYTHONPATH": os.pathsep.join(sys.path)},
                    "excludes": ["*.pyc", "__pycache__"],
                }
            )

        builder = Builder(project_path=str(PROJECT_PATH), resource_maps=RESOURCES_MAPS)
        pod_manager, system = await builder.init()
        ticks = max_ticks if max_ticks is not None else builder.config.simulation.max_ticks
        total_duration = 0.0

        for _ in range(ticks):
            started = time.time()
            await pod_manager.step_agent.remote()
            await system.run("messager", "dispatch_messages")
            current_tick = await system.run("timer", "get_tick")
            duration = time.time() - started
            total_duration += duration
            await pod_manager.update_agents_status.remote()
            await system.run("timer", "add_tick", duration_seconds=duration)
            logger.info("WorldKernel tick %s finished in %.3fs", current_tick, duration)

            agents_data = await pod_manager.collect_agents_data.remote()
            logger.info("WorldKernel tick %s collected %s agents", current_tick, len(agents_data))

        if ticks:
            logger.info("WorldKernel simulation finished. avg_tick=%.3fs", total_duration / ticks)
    finally:
        if pod_manager:
            await pod_manager.close.remote()
        if system:
            await system.close()
        if ray.is_initialized():
            ray.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-ticks", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(max_ticks=args.max_ticks))
