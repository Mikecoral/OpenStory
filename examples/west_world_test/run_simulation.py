"""西部世界正式仿真入口（M2 骨架版）。

用法（仓库根目录，需 Redis 在线）：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \\
        python -m examples.west_world_test.run_simulation
"""
from __future__ import annotations

import asyncio
import os

import ray

from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.registry_sim import RESOURCES_MAPS

logger = get_logger(__name__)
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
TICK_DURATION = 0.1  # seconds per tick for smoke test


async def main() -> None:
    ray.init(ignore_reinit_error=True)
    builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
    pod_manager, system = await builder.init()
    max_ticks = builder._config.simulation.max_ticks
    logger.info("Simulation starting: max_ticks=%s", max_ticks)
    try:
        for i in range(max_ticks):
            tick = await system.run("timer", "get_tick")
            logger.info("===== tick %s =====", tick)
            await pod_manager.step_agent.remote()
            await system.run("messager", "dispatch_messages")
            await system.run("timer", "add_tick", duration_seconds=TICK_DURATION)
    finally:
        await pod_manager.close.remote()
        ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
