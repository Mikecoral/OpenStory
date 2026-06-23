from __future__ import annotations

from typing import Any, List

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.controller.controller import ControllerImpl


class WKController(ControllerImpl):
    async def get_all_agent_ids(self) -> List[str]:
        if self._pod_manager:
            return await self._pod_manager.get_all_agent_ids.remote()
        return self.get_agent_ids()

    async def update_agents_status(self) -> None:
        return None

    async def get_available_actions(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if not self._action:
            return {}
        available: dict[str, Any] = {}
        for component_name in self._action.list_components():
            method_names = self._action.list_comp_methods_names(component_name)
            available[component_name] = await self._action.get_agent_call_methods(component_name, method_names)
        return available
