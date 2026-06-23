
from __future__ import annotations

from typing import Any, List

from agentkernel_distributed.mas.controller.controller import ControllerImpl


class WKController(ControllerImpl):
    async def get_all_agent_ids(self) -> List[str]:
        if self._pod_manager:
            return await self._pod_manager.get_all_agent_ids.remote()
        return self.get_agent_ids()
