"""感知插件：M2 用地图静态信息占位；M3 在 execute 中追加 Recorder read。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agentkernel_distributed.mas.agent.base.plugin_base import PerceivePlugin
from agentkernel_distributed.types.schemas.message import Message

from examples.west_world_test.worldmap.loader import WorldMap


def build_percept(world: WorldMap, agent_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    here = world.get(state["location"])
    return {
        "location": here.id,
        "here_description": here.description,
        "neighbors": world.neighbors(here.id, active_only=True),
        "known_map": list(state.get("known_map", [])),
    }


def _rows(locations: Any) -> list:
    if isinstance(locations, dict):
        return list(locations.values())
    return list(locations or [])


class WestWorldPerceivePlugin(PerceivePlugin):
    """M2 感知插件：从地图静态信息构建 percept，写入 state。"""

    def __init__(self, world: Optional[WorldMap] = None, **_: Any) -> None:
        super().__init__()
        self._world = world
        self._messages: List[Message] = []

    async def init(self) -> None:
        pass

    async def add_message(self, message: Message) -> None:
        self._messages.append(message)

    async def execute(self, current_tick: int) -> None:
        if self._world is None or self.agent is None:
            return
        state_component = self.agent.get_component("state")
        state_plugin = state_component.get_plugin()

        location = await state_plugin.get_state("location")
        known_map = await state_plugin.get_state("known_map") or []
        current_state = {"location": location, "known_map": known_map}

        percept = build_percept(self._world, self.agent.agent_id, current_state)
        await state_plugin.set_state("percept", percept)

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
