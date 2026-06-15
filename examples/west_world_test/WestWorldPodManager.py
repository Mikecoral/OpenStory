"""Pod manager exposing the representative pod environment for the MVE runner."""
from __future__ import annotations

from typing import Any

import ray

from agentkernel_distributed.mas.pod import PodManagerImpl


@ray.remote
class WestWorldPodManager(PodManagerImpl):
    async def init(self, *args: Any, **kwargs: Any) -> None:
        configs = args[0] if args else kwargs.get("configs")
        if configs is not None and len(configs.agents) > self._pod_size:
            raise RuntimeError(
                "west_world_test requires exactly one pod because scene state and "
                "WorldObjectRegistry are process-local"
            )
        await super().init(*args, **kwargs)
        if len(self._pod_id_to_pod) != 1:
            raise RuntimeError(
                "west_world_test requires exactly one pod because scene state and "
                "WorldObjectRegistry are process-local"
            )

    async def run_environment(self, component_name: str, method_name: str, *args: Any, **kwargs: Any) -> Any:
        if not self._pod_id_to_pod:
            raise RuntimeError("No pod is available to host the environment")
        pod = next(iter(self._pod_id_to_pod.values()))
        return await pod.forward.remote("run_environment", component_name, method_name, *args, **kwargs)

    async def add_agent(self, agent_id: str, template_name: str, data: dict) -> bool:
        if not self._pod_id_to_pod:
            raise RuntimeError("No pod is available")
        representative = next(iter(self._pod_id_to_pod.values()))
        if await representative.forward.remote("get_agent_count") >= self._pod_size:
            raise RuntimeError("west_world_test cannot add an agent that would create a second pod")
        return await super().add_agent(agent_id, template_name, data)
