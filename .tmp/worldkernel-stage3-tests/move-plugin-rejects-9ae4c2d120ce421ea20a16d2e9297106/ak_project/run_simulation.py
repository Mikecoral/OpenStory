
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
import time
import types
from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parent


def _ensure_paths() -> None:
    if str(PROJECT_PATH) not in sys.path:
        sys.path.insert(0, str(PROJECT_PATH))
    for parent in [PROJECT_PATH, *PROJECT_PATH.parents]:
        packages_root = parent / "packages"
        if packages_root.exists():
            for child in packages_root.iterdir():
                if child.is_dir() and str(child) not in sys.path:
                    sys.path.insert(0, str(child))
            break


_ensure_paths()
if "faker" not in sys.modules and importlib.util.find_spec("faker") is None:
    faker_stub = types.ModuleType("faker")
    faker_stub.Faker = type("Faker", (), {})
    sys.modules["faker"] = faker_stub
if "redis" not in sys.modules and importlib.util.find_spec("redis") is None:
    redis_stub = types.ModuleType("redis")
    redis_asyncio_stub = types.ModuleType("redis.asyncio")
    redis_asyncio_stub.ConnectionPool = type("ConnectionPool", (), {"from_url": classmethod(lambda cls, *a, **k: cls())})
    redis_asyncio_stub.StrictRedis = type("StrictRedis", (), {"__init__": lambda self, *a, **k: None, "ping": lambda self: True})
    redis_asyncio_stub.Redis = redis_asyncio_stub.StrictRedis
    redis_stub.asyncio = redis_asyncio_stub
    sys.modules["redis"] = redis_stub
    sys.modules["redis.asyncio"] = redis_asyncio_stub
os.environ["MAS_PROJECT_ABS_PATH"] = str(PROJECT_PATH)
os.environ.setdefault("MAS_PROJECT_REL_PATH", ".")

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
            ray.init(runtime_env={"working_dir": str(PROJECT_PATH)})
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
            await system.run("timer", "add_tick", duration_seconds=duration)
            logger.info("Tick %s finished in %.3fs", current_tick, duration)
        if ticks:
            logger.info("Simulation finished. avg_tick=%.3fs", total_duration / ticks)
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
