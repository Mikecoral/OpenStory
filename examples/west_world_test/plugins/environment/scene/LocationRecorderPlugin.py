"""把 LocationRecorder 接入内核环境组件体系：每地点一个 scene_<id> 组件。"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Type

from agentkernel_distributed.mas.environment.base.plugin_base import GenericPlugin

from examples.west_world_test.recorder.location_recorder import LocationRecorder
from examples.west_world_test.worldmap.loader import Location, load_world_map

_DEFAULT_MAP_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "map", "locations.yaml"
))

_DEFAULT_MODELS_CONFIG = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "configs", "models_config.yaml"
))


class LocationRecorderPlugin(GenericPlugin):
    COMPONENT_TYPE = "scene"

    def __init__(self, location_id: str, locations: Any = None,
                 llm_factory: Optional[Callable[[], Any]] = None,
                 models_config_path: str = "", **_: Any) -> None:
        super().__init__()
        self._location_id = location_id
        self._llm_factory = llm_factory
        self._models_config_path = models_config_path or _DEFAULT_MODELS_CONFIG
        self.recorder: Optional[LocationRecorder] = None

        # If locations is provided (list of dicts or list of Location), use it.
        # Otherwise fall back to loading from the default data file path.
        # (Builder injects locations per-agent by agent_id, not by location_id,
        #  so when running under the kernel we skip locations and load from file.)
        if locations is not None and isinstance(locations, list) and len(locations) > 0:
            loc = self._find_location(location_id, locations)
        else:
            world = load_world_map(_DEFAULT_MAP_PATH)
            loc = world.get(location_id)
        self._location = loc

    @staticmethod
    def _find_location(location_id: str, locations: list) -> Location:
        for item in locations:
            if isinstance(item, Location):
                if item.id == location_id:
                    return item
            elif isinstance(item, dict):
                if item.get("id") == location_id:
                    return Location(**item)
        raise KeyError(f"location '{location_id}' not found in provided locations list")

    async def init(self) -> None:
        if self._llm_factory is None:
            from examples.west_world_test.recorder.factory import build_llm
            self._llm_factory = lambda: build_llm(self._models_config_path)
        self.recorder = LocationRecorder(location=self._location, llm=self._llm_factory())

    async def execute(self, current_tick: int) -> None:
        if self.recorder:
            self.recorder.tick_update(current_tick)

    async def read(self, agent_id: str, chunks: List[str]) -> Dict[str, Any]:
        return self.recorder.read(agent_id, chunks)

    async def submit_action(self, agent_id: str, action_text: str) -> Dict[str, Any]:
        return self.recorder.submit_action(agent_id, action_text)

    async def agent_enter(self, agent_id: str) -> str:
        return self.recorder.agent_enter(agent_id)

    async def agent_leave(self, agent_id: str) -> None:
        self.recorder.agent_leave(agent_id)

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None


def make_scene_plugin_class(location_id: str) -> Type[LocationRecorderPlugin]:
    """Dynamically create a per-location plugin class with COMPONENT_TYPE = scene_<location_id>."""
    return type(f"Scene_{location_id}_Plugin", (LocationRecorderPlugin,),
                {"COMPONENT_TYPE": f"scene_{location_id}"})
