"""Pod manager exposing the representative pod environment for the MVE runner."""
from __future__ import annotations

from typing import Any

import ray

from agentkernel_distributed.mas.pod import PodManagerImpl


@ray.remote
class WestWorldPodManager(PodManagerImpl):
    async def run_environment(self, component_name: str, method_name: str, *args: Any, **kwargs: Any) -> Any:
        if not self._pod_id_to_pod:
            raise RuntimeError("No pod is available to host the environment")
        pod = next(iter(self._pod_id_to_pod.values()))
        return await pod.forward.remote("run_environment", component_name, method_name, *args, **kwargs)
