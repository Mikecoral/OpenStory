"""Narrative Loop E2E：验证 host 按 daily_loop 移动并在天边界回原点。

默认跳过；需显式启用：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
    WW_NARRATIVE_LOOP_E2E=1 pytest examples/west_world_test/tests/test_narrative_loop_e2e.py -s

环境变量：
- WW_NL_E2E_MAX_TICKS：跑多少 tick（默认 12）

依赖：Redis 在线 + models_config.yaml 可用。
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import redis
import yaml

from agentkernel_distributed.mas.builder import Builder
from agentkernel_distributed.toolkit.logger import get_logger
from examples.west_world_test.registry_sim import RESOURCES_MAPS
from examples.west_world_test.simulation_logging import SimulationLogArchive

logger = get_logger(__name__)
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK_DURATION = 0.05

_AGENT_IDS: List[str] = []
_ACTIVE_LIDS: List[str] = []
_HOST_LOOP_ORIGIN: Dict[str, str] = {}


def _load_data():
    global _AGENT_IDS, _ACTIVE_LIDS, _HOST_LOOP_ORIGIN
    locations_path = Path(PROJECT_PATH, "data/map/locations.yaml")
    _ACTIVE_LIDS = sorted(
        loc["id"] for loc in yaml.safe_load(locations_path.read_text(encoding="utf-8"))
        if loc.get("active")
    )
    states_path = Path(PROJECT_PATH, "data/agents/states_sim.jsonl")
    _AGENT_IDS = sorted(
        json.loads(line)["id"]
        for line in states_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    profiles_path = Path(PROJECT_PATH, "data/agents/profiles_sim.jsonl")
    for line in profiles_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        if p.get("agent_type") == "host" and p.get("daily_loop"):
            _HOST_LOOP_ORIGIN[p["id"]] = p["daily_loop"][0]["location"]


_load_data()


def _redis_available() -> bool:
    try:
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        return r.ping()
    except Exception:
        return False


@pytest.fixture(scope="module")
def e2e_enabled() -> bool:
    return os.environ.get("WW_NARRATIVE_LOOP_E2E", "").lower() in ("1", "true")


@pytest.fixture(scope="module")
def max_ticks() -> int:
    return int(os.environ.get("WW_NL_E2E_MAX_TICKS", "12"))


async def _collect_agent_states(pod_manager) -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    for agent_id in _AGENT_IDS:
        state = await pod_manager.run_agent_method.remote(agent_id, "state", "get_state")
        states[agent_id] = state or {}
    return states


async def _synchronize_initial_presence(pod_manager, agent_states) -> None:
    by_location: Dict[str, List[str]] = {location_id: [] for location_id in _ACTIVE_LIDS}
    for agent_id, state in agent_states.items():
        location = state.get("location")
        if location not in by_location:
            raise ValueError(f"agent {agent_id} has unknown initial location: {location}")
        by_location[location].append(agent_id)
    for location_id, agent_ids in by_location.items():
        await pod_manager.run_environment.remote(
            f"scene_{location_id}", "set_present_agents", agent_ids,
        )


async def _run_narrative_loop_e2e(*, max_ticks: int) -> Dict[str, Any]:
    """Run a single narrative-loop E2E line and return per-tick agent states."""
    run_dir = Path("/tmp", f"west-world-narrative-loop-e2e-{int(time.time())}")
    os.environ["WW_RUN_DIR"] = str(run_dir)
    # Disable overseer/awakening so the test focuses purely on narrative movement.
    os.environ["WW_OVERSEER_ENABLED"] = "false"
    os.environ["WW_AWAKEN_ENABLED"] = "false"

    try:
        redis.Redis(host="localhost", port=6379, db=2).flushdb()
    except Exception as exc:
        logger.warning("[NL-E2E] Redis flushdb failed: %s", exc)

    archive = SimulationLogArchive(PROJECT_PATH, max_ticks, _AGENT_IDS, _ACTIVE_LIDS)
    pod_manager = None
    tick_states: List[Dict[str, Dict[str, Any]]] = []

    try:
        builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
        pod_manager, system = await builder.init()
        initial_agents = await _collect_agent_states(pod_manager)
        await _synchronize_initial_presence(pod_manager, initial_agents)

        for i in range(max_ticks):
            tick = await system.run("timer", "get_tick")
            await pod_manager.step_agent.remote()
            await system.run("messager", "dispatch_messages")
            agent_states = await _collect_agent_states(pod_manager)
            tick_states.append(agent_states)
            archive.record_tick(tick, agent_states, {}, {}, {}, [])
            await system.run("timer", "add_tick", duration_seconds=TICK_DURATION)

        archive.complete()
        return {"tick_states": tick_states, "run_dir": str(archive.run_dir)}
    finally:
        if pod_manager is not None:
            try:
                await pod_manager.close.remote()
            except Exception:
                pass
        import ray
        ray.shutdown()
        try:
            redis.Redis(host="localhost", port=6379, db=2).flushdb()
        except Exception:
            pass


@pytest.mark.slow
@pytest.mark.skipif(not _redis_available(), reason="Redis not available on localhost:6379")
def test_narrative_loop_e2e(e2e_enabled, max_ticks):
    if not e2e_enabled:
        pytest.skip("Set WW_NARRATIVE_LOOP_E2E=1 to run narrative loop E2E")

    logger.info("[NL-E2E] Running narrative loop validation for %s ticks", max_ticks)
    result = asyncio.run(_run_narrative_loop_e2e(max_ticks=max_ticks))

    tick_states = result["tick_states"]
    assert tick_states, "No tick states collected"

    # Build per-agent trajectories.
    trajectories: Dict[str, List[str]] = {agent_id: [] for agent_id in _AGENT_IDS}
    for states in tick_states:
        for agent_id in _AGENT_IDS:
            trajectories[agent_id].append(states.get(agent_id, {}).get("location", ""))

    # 1. Overall movement: someone must move.
    total_moves = sum(
        1
        for agent_id in _AGENT_IDS
        for i in range(1, len(trajectories[agent_id]))
        if trajectories[agent_id][i] and trajectories[agent_id][i] != trajectories[agent_id][i - 1]
    )
    assert total_moves > 0, f"No agent moved during {max_ticks} ticks"

    # 2. Hosts must move: at least one host changes location.
    host_moves = sum(
        1
        for agent_id in _HOST_LOOP_ORIGIN
        for i in range(1, len(trajectories[agent_id]))
        if trajectories[agent_id][i] and trajectories[agent_id][i] != trajectories[agent_id][i - 1]
    )
    assert host_moves > 0, "No host moved during the run"

    # 3. Day-boundary return: at tick 6 (start of next daily_loop cycle) most hosts
    #    should be back at their loop origin. We allow a relaxed threshold because
    #    movement along the loop can spill across the boundary.
    if max_ticks >= 6:
        boundary_idx = 5  # tick_states[5] corresponds to tick 6 (0-based)
        at_origin = sum(
            1
            for agent_id, origin in _HOST_LOOP_ORIGIN.items()
            if trajectories[agent_id][boundary_idx] == origin
        )
        threshold = float(os.environ.get("WW_NL_E2E_ORIGIN_THRESHOLD", "0.6"))
        ratio = at_origin / len(_HOST_LOOP_ORIGIN)
        assert ratio >= threshold, (
            f"Only {at_origin}/{len(_HOST_LOOP_ORIGIN)} hosts at loop origin at tick 6 "
            f"(ratio {ratio:.2f} < {threshold})"
        )

    logger.info(
        "[NL-E2E] Passed: total_moves=%d, host_moves=%d, at_origin_tick6=%d/%d",
        total_moves, host_moves, at_origin if max_ticks >= 6 else 0, len(_HOST_LOOP_ORIGIN),
    )
