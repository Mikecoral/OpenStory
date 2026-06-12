"""西部世界正式仿真入口（M3 版：Recorder 联动）。

用法（仓库根目录，需 Redis 在线）：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \\
        python -m examples.west_world_test.run_simulation

支持环境变量：
    WW_MAX_TICKS=5  覆盖 configs 里的 max_ticks（方便快速冒烟）
"""
from __future__ import annotations

import asyncio
import os

import ray
import yaml as _yaml

from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.registry_sim import RESOURCES_MAPS

logger = get_logger(__name__)
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
TICK_DURATION = 0.1  # seconds per tick for smoke test

# 活跃地点 ID 列表（从 locations.yaml 加载）
_ACTIVE_LIDS = sorted(
    loc["id"] for loc in _yaml.safe_load(
        open(os.path.join(PROJECT_PATH, "data/map/locations.yaml"), encoding="utf-8"))
    if loc.get("active")
)


async def main() -> None:
    ray.init(ignore_reinit_error=True)
    builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
    pod_manager, system = await builder.init()
    max_ticks = int(os.environ.get("WW_MAX_TICKS", "") or builder._config.simulation.max_ticks)
    logger.info("Simulation starting: max_ticks=%s, active_lids=%s", max_ticks, _ACTIVE_LIDS)
    try:
        for i in range(max_ticks):
            tick = await system.run("timer", "get_tick")
            logger.info("===== tick %s =====", tick)
            await pod_manager.step_agent.remote()
            await system.run("messager", "dispatch_messages")
            # 每 tick 末显式触发各 scene 组件的 tick_update（环境 execute 不被自动调用）
            for lid in _ACTIVE_LIDS:
                try:
                    await pod_manager.run_environment.remote(f"scene_{lid}", "execute", tick)
                except Exception as exc:
                    logger.warning("scene_%s execute 失败: %s", lid, exc)
            await system.run("timer", "add_tick", duration_seconds=TICK_DURATION)
    finally:
        await pod_manager.close.remote()
        ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
