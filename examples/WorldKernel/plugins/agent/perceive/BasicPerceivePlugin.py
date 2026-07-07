"""Perceive plugin: receives inbound messages and exposes them each tick.

Messages delivered via the Messager land in ``_incoming`` between ticks. At
``execute`` they are promoted to ``last_tick_messages`` (readable by plan/invoke)
and written into short-term memory, then the incoming buffer is cleared.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Tuple

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.agent.base.plugin_base import PerceivePlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)


class BasicPerceivePlugin(PerceivePlugin):
    """Collects messages the agent receives and surfaces them to other plugins."""

    def __init__(self, redis: Any = None) -> None:
        super().__init__()
        self.redis = redis
        self._incoming: List[Any] = []
        self._last_tick_messages: List[Any] = []
        self.agent_id = None

    async def init(self) -> None:
        if getattr(self, "_component", None):
            self.agent_id = self._component.agent.agent_id

    async def add_message(self, message: Any) -> None:
        self._incoming.append(message)

    async def execute(self, current_tick: int) -> None:
        # Promote messages received since the previous tick.
        self._last_tick_messages = self._incoming
        self._incoming = []

        if not self._last_tick_messages:
            return

        state = self._get_state_plugin()
        if state is None:
            return

        for msg in self._last_tick_messages:
            sender = getattr(msg, "from_id", "?")
            content = getattr(msg, "content", "")
            await state.add_short_term_memory(
                f"收到来自 {sender} 的消息：{content}", current_tick
            )

    def _get_state_plugin(self) -> Any:
        component = getattr(self, "_component", None)
        agent = getattr(component, "agent", None)
        if agent is None:
            return None
        try:
            state_component = agent.get_component("state")
            return state_component.get_plugin() if state_component else None
        except Exception:  # noqa: BLE001
            return None

    @property
    def get_last_tick_messages(self) -> List[Any]:
        return self._last_tick_messages

    async def _get_self_position(self) -> Tuple[int, int] | None:
        state = self._get_state_plugin()
        if state is None:
            return None
        pos = await state.get_state("position")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return (int(pos[0]), int(pos[1]))
        return None
