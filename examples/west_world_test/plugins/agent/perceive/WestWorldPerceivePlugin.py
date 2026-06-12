"""感知插件：M2 用地图静态信息占位；M3 在 execute 中追加 Recorder read。"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from agentkernel_distributed.mas.agent.base.plugin_base import PerceivePlugin
from agentkernel_distributed.toolkit.logger import get_logger
from agentkernel_distributed.types.schemas.message import Message

from examples.west_world_test.worldmap.loader import WorldMap, load_world_map

logger = get_logger(__name__)

_DEFAULT_MAP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "map", "locations.yaml"
)


def build_percept(world: WorldMap, agent_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    here = world.get(state["location"])
    return {
        "location": here.id,
        "here_description": here.description,
        "neighbors": world.neighbors(here.id, active_only=True),
        "known_map": list(state.get("known_map", [])),
    }


def _load_default_world() -> Optional[WorldMap]:
    """从默认数据文件路径加载 WorldMap。"""
    path = os.path.normpath(_DEFAULT_MAP_PATH)
    if os.path.exists(path):
        return load_world_map(path)
    return None


class WestWorldPerceivePlugin(PerceivePlugin):
    """M2 感知插件：从地图静态信息构建 percept，写入 state。"""

    def __init__(
        self,
        world: Optional[WorldMap] = None,
        locations: Any = None,
        **_: Any,
    ) -> None:
        super().__init__()
        # Builder injects locations per-agent (keyed by agent ID) which won't match
        # map location IDs — fall back to loading from the default data file path.
        self._world = world or _load_default_world()
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

        # 追加 Recorder read（M3 新增）
        controller = self.agent.controller
        try:
            # 先看 plan 上一 tick 想读的 chunks；没有则用默认三块
            next_read = await state_plugin.get_state("next_read") or ["present_agents", "recent_events", "dynamic_objects"]
            chunks = await controller.run_environment(
                f"scene_{location}", "read",
                self.agent.agent_id, next_read)
            percept["scene"] = chunks
        except Exception as exc:
            logger.warning("[%s] 读取 scene_%s 失败，使用静态感知: %s",
                           self.agent.agent_id, location, exc)
            percept["scene"] = {}

        await state_plugin.set_state("percept", percept)

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
