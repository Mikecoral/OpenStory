"""Profile plugin: holds an agent's static character profile.

Generic port of story_of_the_stone's BasicProfilePlugin. Profile data comes
from the Stage3 adapter (id/name/role/personality/goals/memories/...).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.agent.base.plugin_base import ProfilePlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)


class BasicProfilePlugin(ProfilePlugin):
    """Container for an agent's profile, with cross-agent lookup via controller."""

    def __init__(self, redis: Any = None, profile_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.redis = redis
        # profile_data may arrive as a config-key string before real injection.
        self.profile_data: Dict[str, Any] = profile_data if isinstance(profile_data, dict) else {}
        self.agent_id = self.profile_data.get("id", "Unknown")
        self.long_memories: List[str] = []
        self.controller = None

    async def init(self) -> None:
        if getattr(self, "_component", None):
            self.controller = self._component.agent.controller
            # Sync agent_id with the framework-assigned id if profile lacked one.
            if self.agent_id == "Unknown":
                self.agent_id = self._component.agent.agent_id

    async def execute(self, current_tick: int) -> None:
        return None

    async def set_profile(self, key: str, value: Any) -> None:
        self.profile_data[key] = value

    async def get_profile(self, key: str) -> Any:
        return self.profile_data.get(key)

    def get_agent_profile(self) -> Dict[str, Any]:
        return self.profile_data

    def update_agent_profile(self, key: str, value: Any) -> None:
        self.profile_data[key] = value

    def get_callable_profiles(self) -> Dict[str, Any]:
        return {k: v for k, v in self.profile_data.items() if v}

    def add_long_memory(self, content: str) -> None:
        self.long_memories.append(content)

    async def get_agent_profile_by_id(self, target_agent_id: str) -> Optional[Dict[str, Any]]:
        if not self.controller:
            return None
        try:
            return await self.controller.run_agent_method(
                target_agent_id, "profile", "get_agent_profile"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to retrieve profile of %s: %s", target_agent_id, exc)
            return None
