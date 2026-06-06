"""Other action: generic no-op / catch-all action."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.action.base.plugin_base import OtherActionsPlugin
from agentkernel_distributed.toolkit.utils.annotation import AgentCall
from agentkernel_distributed.types.schemas.action import ActionResult


class BasicOtherActionPlugin(OtherActionsPlugin):
    """Fallback action for activities that need no special handling."""

    def __init__(self, redis: Any = None) -> None:
        super().__init__()
        self.redis = redis
        self.model: Any = None
        self.controller: Any = None

    async def init(self, model_router: Any = None, controller: Any = None) -> None:
        self.model = model_router
        self.controller = controller

    async def _log_action(self, *args: Any, **kwargs: Any) -> None:
        return None

    @AgentCall
    async def noop(self, agent_id: str, reason: str = "") -> ActionResult:
        return ActionResult.success(
            method_name="noop",
            message=reason or "no operation",
            data={"agent_id": agent_id},
        )
