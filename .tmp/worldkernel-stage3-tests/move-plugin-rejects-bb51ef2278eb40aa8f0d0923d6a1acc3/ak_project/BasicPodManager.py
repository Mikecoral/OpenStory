
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import ray
from agentkernel_distributed.mas.pod import PodManagerImpl


@ray.remote
class WKPodManager(PodManagerImpl):
    def get_all_agent_ids(self) -> List[str]:
        return list(self._agent_id_to_pod.keys())

    async def collect_agents_data(self) -> Dict[str, Any]:
        async def fetch_one(agent_id: str):
            pod = self._agent_id_to_pod[agent_id]

            async def call(component: str, method: str, *args):
                try:
                    return await pod.forward.remote("run_agent_method", agent_id, component, method, *args)
                except Exception:
                    return None

            long_task, current_plan, current_action, profile, state, memories = await asyncio.gather(
                call("state", "get_long_task"),
                call("state", "get_state", "current_plan"),
                call("state", "get_state", "current_action"),
                call("profile", "get_agent_profile"),
                call("state", "get_state"),
                call("state", "get_short_term_memory"),
            )
            return agent_id, {
                "long_task": long_task,
                "current_plan": current_plan,
                "current_action": current_action,
                "profile": profile,
                "state": state,
                "short_term_memory": memories,
                "current_location": (state or {}).get("current_location"),
            }

        results = await asyncio.gather(*(fetch_one(agent_id) for agent_id in self._agent_id_to_pod))
        return dict(results)
