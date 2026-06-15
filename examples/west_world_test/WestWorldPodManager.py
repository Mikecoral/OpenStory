"""A2 pod manager: one world pod (pods[0], agents=[], full environment) + N agent pods.

scene_* components and WorldObjectRegistry live only in the world pod.
Agent pods have environment=None; their controllers forward environment calls
via pod_manager → world pod (see controller.run_environment forwarding patch).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional

import ray

from agentkernel_distributed.mas.pod import PodManagerImpl
from agentkernel_distributed.mas.pod.mas_pod import MasPod
from agentkernel_distributed.types.configs import Config, PodConfig

logger = logging.getLogger(__name__)

_WORLD_POD_ID = "pod_world"


@ray.remote
class WestWorldPodManager(PodManagerImpl):
    """A2 pattern: world pod holds environment; agent pods hold only agents."""

    async def init(
        self,
        configs: Config,
        resource_maps: Dict[str, Any],
        model_router_config: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._resource_maps = resource_maps
        self._configs = configs
        self._model_router_config = model_router_config

        from agentkernel_distributed.toolkit.models.router import ModelRouter, AsyncModelRouter
        if model_router_config:
            model_backend = AsyncModelRouter(models_configs=model_router_config)
            self._model_router = ModelRouter(model_backend)

        await self._init_adapters()

        # ── 1. 世界 pod：无 agent，持有完整 environment ──────────────────────
        world_cfg = PodConfig(
            agent_templates=configs.agent_templates,
            agents=[],
            actions=configs.actions,
            environment=configs.environment,
            database=configs.database,
        )
        world_pod = MasPod.remote(
            pod_id=_WORLD_POD_ID,
            pod_config=world_cfg,
            resource_maps=resource_maps,
            controller_class=self._controller_class,
        )

        # ── 2. Agent pods：持有 agent，environment=None ───────────────────────
        all_agents = configs.agents or []
        agent_batches = [
            all_agents[i: i + self._pod_size]
            for i in range(0, len(all_agents), self._pod_size)
        ] if all_agents else []

        agent_pod_handles: Dict[str, MasPod] = {}
        for idx, batch in enumerate(agent_batches):
            pod_id = f"pod_{idx}"
            pod_cfg = PodConfig(
                agent_templates=configs.agent_templates,
                agents=batch,
                actions=configs.actions,
                environment=None,   # no local environment — forward to world pod
                database=configs.database,
            )
            handle = MasPod.remote(
                pod_id=pod_id,
                pod_config=pod_cfg,
                resource_maps=resource_maps,
                controller_class=self._controller_class,
            )
            agent_pod_handles[pod_id] = handle

        # world pod 放 pods[0]，与内核 save_to_db("all") 约定一致
        self._pod_id_to_pod = {_WORLD_POD_ID: world_pod, **agent_pod_handles}

        # ── 3. 初始化所有 pod ────────────────────────────────────────────────
        all_handles = list(self._pod_id_to_pod.values())
        for batch_start in range(0, len(all_handles), self._init_batch_size):
            batch = all_handles[batch_start: batch_start + self._init_batch_size]
            await asyncio.gather(
                *[h.init.remote(model_router_config=self._model_router_config) for h in batch]
            )
            logger.info("Initialized WestWorld pod batch %d", batch_start // self._init_batch_size + 1)

        # ── 4. 建立 agent_id → pod 映射 ─────────────────────────────────────
        agent_id_to_pod: Dict[str, MasPod] = {}
        for pod_handle in agent_pod_handles.values():
            ids = await pod_handle.forward.remote("get_agent_ids")
            for agent_id in ids:
                agent_id_to_pod[agent_id] = pod_handle
        self._agent_id_to_pod = agent_id_to_pod

        await self.save_to_db(scope="all")

    # ── 环境路由：始终转发到世界 pod ─────────────────────────────────────────
    async def run_environment(
        self, component_name: str, method_name: str, *args: Any, **kwargs: Any
    ) -> Any:
        world_pod = self._pod_id_to_pod.get(_WORLD_POD_ID)
        if world_pod is None:
            raise RuntimeError("World pod is not initialized")
        return await world_pod.forward.remote(
            "run_environment", component_name, method_name, *args, **kwargs
        )

    # ── tick 推进：barrier 让 reflect 看到 tick_update 结果 ─────────────────
    async def step_agent(self) -> None:
        agent_pods = [p for pid, p in self._pod_id_to_pod.items() if pid != _WORLD_POD_ID]
        if not agent_pods:
            return

        # pre-reflect 阶段：perceive / plan / invoke / state（含 recorder enqueue）
        await asyncio.gather(*[p.forward.remote("step_pre_reflect") for p in agent_pods])

        # tick_update 栅栏：世界 pod 批量裁决本 tick 所有排队动作，写入 recorder 状态
        current_tick = await self._system_handle.run("timer", "get_tick")
        world_pod = self._pod_id_to_pod[_WORLD_POD_ID]
        scene_components: List[str] = await world_pod.forward.remote("list_environment_components")
        scene_ids = [c for c in scene_components if c.startswith("scene_")]
        await asyncio.gather(*[
            world_pod.forward.remote("run_environment", scene, "execute", current_tick)
            for scene in scene_ids
        ])

        # reflect 阶段：agent 读到最新裁决结果后总结
        await asyncio.gather(*[p.forward.remote("step_reflect") for p in agent_pods])

    # ── add_agent：加入空闲 agent pod（不动世界 pod）──────────────────────
    async def add_agent(self, agent_id: str, template_name: str, data: Dict[str, Any]) -> bool:
        if agent_id in self._agent_id_to_pod:
            logger.error("Agent '%s' already exists", agent_id)
            return False

        # 找有空位的 agent pod
        target_pod: Optional[MasPod] = None
        for pid, pod in self._pod_id_to_pod.items():
            if pid == _WORLD_POD_ID:
                continue
            count = await pod.forward.remote("get_agent_count")
            if count < self._pod_size:
                target_pod = pod
                break

        if target_pod is None:
            # 新建 agent pod
            pod_id = f"pod_{len(self._pod_id_to_pod) - 1}"  # -1 for world pod
            pod_cfg = PodConfig(
                agent_templates=self._configs.agent_templates,
                agents=[],
                actions=self._configs.actions,
                environment=None,
                database=self._configs.database,
            )
            target_pod = MasPod.remote(
                pod_id=pod_id,
                pod_config=pod_cfg,
                resource_maps=self._resource_maps,
                controller_class=self._controller_class,
            )
            await target_pod.init.remote(model_router_config=self._model_router_config)
            await target_pod.post_init.remote(self._system_handle, self._self_handle)
            self._pod_id_to_pod[pod_id] = target_pod

        success = await target_pod.forward.remote("add_agent", agent_id, template_name, data)
        if success:
            self._agent_id_to_pod[agent_id] = target_pod
        return success
