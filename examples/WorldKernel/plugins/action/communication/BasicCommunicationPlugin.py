"""Communication action: send a message from one agent to another."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.action.base.plugin_base import CommunicationPlugin
from agentkernel_distributed.toolkit.utils.annotation import AgentCall
from agentkernel_distributed.types.schemas.action import ActionResult
from agentkernel_distributed.types.schemas.message import Message, MessageKind


def _result(method: str, ok: bool, message: str, data: dict[str, Any] | None = None) -> ActionResult:
    if ok:
        return ActionResult.success(method_name=method, message=message, data=data or {})
    return ActionResult.error(method_name=method, message=message, data=data or {})


class BasicCommunicationPlugin(CommunicationPlugin):
    """Routes an agent-to-agent message through the Messager."""

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
    async def communicate(self, sender: str, receiver: str, content: str) -> ActionResult:
        """Enqueue a FROM_AGENT_TO_AGENT message for delivery."""
        if not getattr(self, "controller", None):
            return _result("communicate", False, "controller unavailable")
        if not receiver:
            return _result("communicate", False, "receiver is required")
        message = Message(
            from_id=sender,
            to_id=receiver,
            kind=MessageKind.FROM_AGENT_TO_AGENT,
            content=content,
        )
        try:
            await self.controller.run_system("messager", "send_message", message)
        except Exception as exc:  # noqa: BLE001
            return _result("communicate", False, f"failed to enqueue message: {exc}")
        return _result(
            "communicate", True, "message enqueued",
            {"sender": sender, "receiver": receiver, "content": content},
        )
