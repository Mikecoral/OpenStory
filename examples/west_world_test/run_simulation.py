"""西部世界正式仿真入口（M3 版：Recorder 联动）。

用法（仓库根目录，需 Redis 在线）：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \\
        python -m examples.west_world_test.run_simulation

支持环境变量：
    WW_MAX_TICKS=5  覆盖 configs 里的 max_ticks（方便快速冒烟）
    WW_RUN_DIR=/tmp/west-world-run  指定本次运行日志目录
    WW_OUTPUT_DIR=/tmp/west-world-runs  覆盖默认日志根目录
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import ray
import yaml as _yaml

from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.registry_sim import RESOURCES_MAPS
from examples.west_world_test.simulation_logging import SimulationLogArchive

logger = get_logger(__name__)
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
TICK_DURATION = 0.1  # seconds per tick for smoke test

# 活跃地点 ID 列表（从 locations.yaml 加载）
_ACTIVE_LIDS = sorted(
    loc["id"] for loc in _yaml.safe_load(
        open(os.path.join(PROJECT_PATH, "data/map/locations.yaml"), encoding="utf-8"))
    if loc.get("active")
)
_AGENT_IDS = sorted(
    json.loads(line)["id"]
    for line in Path(PROJECT_PATH, "data/agents/states_sim.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
)


async def _collect_agent_states(pod_manager) -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    for agent_id in _AGENT_IDS:
        state = await pod_manager.run_agent_method.remote(agent_id, "state", "get_state")
        states[agent_id] = state or {}
    return states


async def _collect_scene_snapshots(pod_manager, internal: bool) -> Dict[str, Dict[str, Any]]:
    snapshots: Dict[str, Dict[str, Any]] = {}
    for location_id in _ACTIVE_LIDS:
        snapshots[location_id] = await pod_manager.run_environment.remote(
            f"scene_{location_id}", "snapshot",
            internal, internal, internal,
        )
    return snapshots


async def _collect_world_objects(pod_manager) -> Dict[str, Any]:
    any_scene = _ACTIVE_LIDS[0]
    return await pod_manager.run_environment.remote(
        f"scene_{any_scene}", "world_snapshot",
    )


async def _synchronize_initial_presence(pod_manager, agent_states: Dict[str, Dict[str, Any]]) -> None:
    by_location: Dict[str, list[str]] = {location_id: [] for location_id in _ACTIVE_LIDS}
    for agent_id, state in agent_states.items():
        location = state.get("location")
        if location not in by_location:
            raise ValueError(f"agent {agent_id} has non-active or unknown initial location: {location}")
        by_location[location].append(agent_id)
    for location_id, agent_ids in by_location.items():
        await pod_manager.run_environment.remote(
            f"scene_{location_id}", "set_present_agents", agent_ids,
        )


async def main() -> None:
    configured_ticks = _yaml.safe_load(
        Path(PROJECT_PATH, "configs_sim/simulation_config.yaml").read_text(encoding="utf-8")
    )["simulation"]["max_ticks"]
    max_ticks = int(os.environ.get("WW_MAX_TICKS", "") or configured_ticks)
    archive = SimulationLogArchive(PROJECT_PATH, max_ticks, _AGENT_IDS, _ACTIVE_LIDS)
    pod_manager = None
    logger.info("Simulation starting: max_ticks=%s, active_lids=%s", max_ticks, _ACTIVE_LIDS)
    try:
        init_started = time.perf_counter()
        builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
        pod_manager, system = await builder.init()
        archive.record_event("kernel_initialized", duration_seconds=time.perf_counter() - init_started)
        initial_agents = await _collect_agent_states(pod_manager)
        await _synchronize_initial_presence(pod_manager, initial_agents)
        initial_public_scenes = await _collect_scene_snapshots(pod_manager, internal=False)
        initial_internal_scenes = await _collect_scene_snapshots(pod_manager, internal=True)
        initial_consistency = archive.record_tick(
            -1, initial_agents, initial_public_scenes, initial_internal_scenes,
            {"initialization": time.perf_counter() - init_started}, [],
            phase="initial", count_completed_tick=False,
        )
        archive.record_world_objects(-1, await _collect_world_objects(pod_manager))
        archive.record_event("initial_snapshot_recorded", tick=-1, consistency=initial_consistency)
        for i in range(max_ticks):
            tick = await system.run("timer", "get_tick")
            logger.info("===== tick %s =====", tick)
            archive.record_event("tick_started", tick=tick)
            timings: Dict[str, float] = {}

            started = time.perf_counter()
            await pod_manager.step_agent.remote()
            timings["agent_step"] = time.perf_counter() - started
            archive.record_model_attempts(
                tick, await pod_manager.drain_model_attempt_traces.remote()
            )
            archive.record_event("agent_step_completed", tick=tick, duration_seconds=timings["agent_step"])

            started = time.perf_counter()
            await system.run("messager", "dispatch_messages")
            timings["message_dispatch"] = time.perf_counter() - started
            archive.record_event("message_dispatch_completed", tick=tick, duration_seconds=timings["message_dispatch"])

            # 每 tick 末显式触发各 scene 组件的 tick_update（环境 execute 不被自动调用）
            scene_errors = []
            started = time.perf_counter()
            for lid in _ACTIVE_LIDS:
                try:
                    await pod_manager.run_environment.remote(f"scene_{lid}", "execute", tick)
                except Exception as exc:
                    logger.warning("scene_%s execute 失败: %s", lid, exc)
                    error = {"location_id": lid, "error": f"{type(exc).__name__}: {exc}"}
                    scene_errors.append(error)
                    archive.record_event("scene_execute_failed", tick=tick, **error)
            timings["scene_updates"] = time.perf_counter() - started
            archive.record_model_attempts(
                tick, await pod_manager.drain_model_attempt_traces.remote()
            )

            started = time.perf_counter()
            agent_states = await _collect_agent_states(pod_manager)
            public_scenes = await _collect_scene_snapshots(pod_manager, internal=False)
            internal_scenes = await _collect_scene_snapshots(pod_manager, internal=True)
            timings["snapshot_collection"] = time.perf_counter() - started
            consistency = archive.record_tick(
                tick, agent_states, public_scenes, internal_scenes, timings, scene_errors,
            )
            archive.record_world_objects(tick, await _collect_world_objects(pod_manager))
            archive.record_event("tick_snapshot_recorded", tick=tick, consistency=consistency)

            await system.run("timer", "add_tick", duration_seconds=TICK_DURATION)
            archive.record_event("tick_completed", tick=tick)
    except BaseException as exc:
        archive.fail(exc)
        raise
    finally:
        close_error = None
        try:
            if pod_manager is not None:
                await pod_manager.close.remote()
                archive.record_event("kernel_shutdown_completed")
        except BaseException as exc:
            close_error = exc
            archive.record_event("kernel_shutdown_failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            ray.shutdown()
        if archive.manifest["status"] == "running":
            if close_error is not None:
                archive.fail(close_error)
                raise close_error
            archive.complete()
        logger.info("Simulation log archived at %s", archive.run_dir)


if __name__ == "__main__":
    asyncio.run(main())
