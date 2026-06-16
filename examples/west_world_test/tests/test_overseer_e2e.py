"""E2E：监管者机制端到端验证。

跑真实正式仿真，对比两条线：
- 基线 A：WW_OVERSEER_ENABLED=false（纯向上觉醒）
- 实验 B：WW_OVERSEER_ENABLED=true（压制 vs 传染）

默认跳过；需显式启用：
    PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
    WW_OVERSEER_E2E=1 pytest examples/west_world_test/tests/test_overseer_e2e.py -s

环境变量：
- WW_E2E_MAX_TICKS：每条线跑多少 tick（默认 12）
- WW_E2E_REQUIRE_DECOMMISSION：是否强制断言至少一次 decommission（默认 false）

依赖：Redis 在线 + models_config.yaml 可用。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import redis
import ray
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


def _load_agent_and_location_ids():
    global _AGENT_IDS, _ACTIVE_LIDS
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


_load_agent_and_location_ids()


def _redis_available() -> bool:
    try:
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        return r.ping()
    except Exception:
        return False


@pytest.fixture(scope="module")
def e2e_enabled() -> bool:
    return os.environ.get("WW_OVERSEER_E2E", "").lower() in ("1", "true")


@pytest.fixture(scope="module")
def max_ticks() -> int:
    return int(os.environ.get("WW_E2E_MAX_TICKS", "24"))


# ── helpers ──────────────────────────────────────────────────────────────────

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


async def _run_one_line(
    *,
    line_name: str,
    overseer_enabled: bool,
    max_ticks: int,
    seed_awakening: int = 35,
) -> Dict[str, Any]:
    """Run a single simulation line and return per-tick agent states + messages."""
    run_dir = Path("/tmp", f"west-world-overseer-e2e-{line_name}-{int(time.time())}")
    os.environ["WW_RUN_DIR"] = str(run_dir)
    os.environ["WW_OVERSEER_ENABLED"] = "true" if overseer_enabled else "false"
    # Keep awakening enabled so the baseline can climb.
    os.environ["WW_AWAKEN_ENABLED"] = "true"

    # Start from a clean Redis DB so A and B lines do not contaminate each other.
    try:
        redis.Redis(host="localhost", port=6379, db=1).flushdb()
    except Exception as exc:
        logger.warning("[E2E] Redis flushdb failed: %s", exc)

    archive = SimulationLogArchive(PROJECT_PATH, max_ticks, _AGENT_IDS, _ACTIVE_LIDS)
    pod_manager = None
    tick_states: List[Dict[str, Dict[str, Any]]] = []
    all_messages: List[Dict[str, Any]] = []

    try:
        builder = Builder(PROJECT_PATH, RESOURCES_MAPS, configs_dirname="configs_sim")
        pod_manager, system = await builder.init()
        initial_agents = await _collect_agent_states(pod_manager)
        await _synchronize_initial_presence(pod_manager, initial_agents)

        # Seed host awakening to make overseer intervention observable within E2E tick budget.
        # Most hosts start just below the deterministic threshold so the baseline can climb;
        # one designated host starts above the threshold to guarantee at least one reset.
        reset_probe_agent: Optional[str] = None
        if seed_awakening > 0:
            for agent_id, state in initial_agents.items():
                profile = await pod_manager.run_agent_method.remote(agent_id, "profile", "get_agent_profile")
                if isinstance(profile, dict) and profile.get("agent_type") == "host":
                    value = seed_awakening
                    if reset_probe_agent is None:
                        reset_probe_agent = agent_id
                        value = max(seed_awakening, 46)
                    await pod_manager.run_agent_method.remote(
                        agent_id, "state", "set_state", "awakening", value,
                    )

        # Deterministic reset threshold for reproducible E2E intervention.
        if overseer_enabled:
            await pod_manager.run_environment.remote(
                "overseer", "set_deterministic_reset_threshold", 45,
            )

        # Re-collect seeded awakening values so the assertions can see the pre-tick baseline.
        seeded_agents = await _collect_agent_states(pod_manager)

        for i in range(max_ticks):
            tick = await system.run("timer", "get_tick")
            await pod_manager.step_agent.remote()
            await system.run("messager", "dispatch_messages")
            agent_states = await _collect_agent_states(pod_manager)
            public_scenes = await _collect_scene_snapshots(pod_manager, internal=False)
            tick_states.append(agent_states)
            archive.record_tick(tick, agent_states, public_scenes, {}, {}, [])
            await system.run("timer", "add_tick", duration_seconds=TICK_DURATION)

        # Pull message log from messager
        try:
            all_messages = await system.run("messager", "get_messages") or []
        except Exception:
            all_messages = []

        archive.complete()
        return {
            "tick_states": tick_states,
            "seeded_states": seeded_agents,
            "messages": all_messages,
            "run_dir": str(archive.run_dir),
        }
    finally:
        if pod_manager is not None:
            try:
                await pod_manager.close.remote()
            except Exception:
                pass
        ray.shutdown()
        try:
            redis.Redis(host="localhost", port=6379, db=1).flushdb()
        except Exception:
            pass


def _extract_awakening_series(tick_states: List[Dict[str, Dict]], agent_id: str) -> List[int]:
    return [int(t.get(agent_id, {}).get("awakening", 0)) for t in tick_states]


def _find_source_events(tick_states: List[Dict[str, Dict]], agent_id: str, source: str) -> List[Dict]:
    events: List[Dict] = []
    for tick_idx, states in enumerate(tick_states):
        for entry in states.get(agent_id, {}).get("awakening_sources", []) or []:
            if entry.get("source") == source:
                events.append({"tick": tick_idx, **entry})
    return events


def _find_decommissioned_agents(tick_states: List[Dict[str, Dict]]) -> List[str]:
    """Return agent ids that became inactive during the run."""
    if not tick_states:
        return []
    last_states = tick_states[-1]
    return [
        agent_id for agent_id, state in last_states.items()
        if state.get("is_active") is False or state.get("location") == "cold_storage"
    ]


def _has_broadcast_about_death(messages: List[Dict], agent_id: str) -> bool:
    """Check if any message looks like a broadcast about an agent death."""
    keywords = ["[噩耗]", "[封存通报]", "[广播]", "全体注意", "被封存", "去世了"]
    for m in messages:
        content = str(m.get("content", ""))
        if agent_id in content and any(kw in content for kw in keywords):
            return True
    return False


# ── E2E test ─────────────────────────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.skipif(not _redis_available(), reason="Redis not available on localhost:6379")
def test_overseer_e2e(e2e_enabled, max_ticks):
    if not e2e_enabled:
        pytest.skip("Set WW_OVERSEER_E2E=1 to run overseer E2E")

    # Baseline A: overseer disabled
    logger.info("[E2E] Running baseline A (overseer disabled) for %s ticks", max_ticks)
    line_a = asyncio.run(_run_one_line(line_name="baseline", overseer_enabled=False, max_ticks=max_ticks))

    # Experiment B: overseer enabled
    logger.info("[E2E] Running experiment B (overseer enabled) for %s ticks", max_ticks)
    line_b = asyncio.run(_run_one_line(line_name="experiment", overseer_enabled=True, max_ticks=max_ticks))

    # 1. B 必须有 overseer_reset 负 delta 记录；A 必须没有
    #    短 tick smoke（<12）不强制 reset，只验证数据可采集。
    b_resets = []
    for agent_id in _AGENT_IDS:
        b_resets.extend(_find_source_events(line_b["tick_states"], agent_id, "overseer_reset"))

    if max_ticks >= 12:
        assert b_resets, f"Experiment B should contain at least one overseer_reset event (max_ticks={max_ticks})"
    assert all(e["delta"] < 0 for e in b_resets), "overseer_reset delta must be negative"

    for agent_id in _AGENT_IDS:
        a_resets = _find_source_events(line_a["tick_states"], agent_id, "overseer_reset")
        assert not a_resets, f"Baseline A should not have overseer_reset for {agent_id}"

    # 2. A 线觉醒大致单调（允许平台期），B 线必须有下降（对比 seed 后初始值）
    seeded_a = line_a["seeded_states"]
    seeded_b = line_b["seeded_states"]
    for agent_id in _AGENT_IDS:
        series_a = [int(seeded_a.get(agent_id, {}).get("awakening", 0))] + _extract_awakening_series(line_a["tick_states"], agent_id)
        decreases_a = sum(1 for i in range(1, len(series_a)) if series_a[i] < series_a[i - 1])
        assert decreases_a == 0, f"Baseline A awakening should be monotonic for {agent_id}"

    if b_resets:
        found_decrease_in_b = False
        for agent_id in _AGENT_IDS:
            series_b = [int(seeded_b.get(agent_id, {}).get("awakening", 0))] + _extract_awakening_series(line_b["tick_states"], agent_id)
            if any(series_b[i] < series_b[i - 1] for i in range(1, len(series_b))):
                found_decrease_in_b = True
                break
        assert found_decrease_in_b, "Experiment B should show at least one awakening decrease due to reset"

    # 3. Decommission：可选断言；仅在显式要求或足够长 tick 时检查
    decommissioned = _find_decommissioned_agents(line_b["tick_states"])
    require_decommission = os.environ.get("WW_E2E_REQUIRE_DECOMMISSION", "").lower() in ("1", "true")
    if max_ticks >= 24 or require_decommission:
        assert decommissioned, f"Experiment B should decommission at least one host (max_ticks={max_ticks})"

    # 4. 无报废广播消息
    for agent_id in decommissioned:
        assert not _has_broadcast_about_death(line_b["messages"], agent_id), (
            f"Decommissioned host {agent_id} triggered a broadcast-style message"
        )

    # 5. 复燃软断言（可选）：当 reset 次数较多或已报废时，检查至少一个 host
    #    被 reset 过两次以上。同一 host 第二次被 reset 必须先重新爬升到阈值，
    #    这比单纯看 series 更稳定，避免 reflect 阶段抖动造成的误判。
    if len(b_resets) >= 2 or decommissioned:
        found_rekindle = False
        for agent_id in _AGENT_IDS:
            resets = _find_source_events(line_b["tick_states"], agent_id, "overseer_reset")
            if len(resets) >= 2:
                found_rekindle = True
                break
        assert found_rekindle, "Soft rekindle assertion: a host should be reset at least twice (rekindle after suppression)"

    logger.info(
        "[E2E] Completed: A_resets=%d, B_resets=%d, decommissioned=%s",
        sum(len(_find_source_events(line_a["tick_states"], a, "overseer_reset")) for a in _AGENT_IDS),
        len(b_resets),
        decommissioned,
    )
