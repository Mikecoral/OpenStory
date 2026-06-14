"""执行插件：落实 plan 决策。M2 只处理 move/stay；M3 追加 Recorder 联动。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from agentkernel_distributed.mas.agent.base.plugin_base import InvokePlugin
from agentkernel_distributed.toolkit.logger import get_logger

from examples.west_world_test.recorder.world_object_registry import get_object_registry
from examples.west_world_test.worldmap.loader import WorldMap, get_world_map

logger = get_logger(__name__)


def _load_default_world() -> Optional[WorldMap]:
    """缓存的 WorldMap（同一路径全进程只加载一次）。"""
    return get_world_map()


def apply_move(world: WorldMap, state: Dict[str, Any], target: str) -> Tuple[Dict[str, Any], bool, str]:
    ok, reason = world.can_move(state["location"], target)
    if not ok:
        return dict(state), False, reason
    new_state = dict(state)
    new_state["location"] = target
    known = list(state.get("known_map", []))
    if target not in known:
        known.append(target)
    new_state["known_map"] = known
    return new_state, True, ""


class WestWorldInvokePlugin(InvokePlugin):
    """M2 执行插件：读取 plan 决策，落实 move/stay，更新 state。"""

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

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        if self._world is None or self.agent is None:
            return
        state_component = self.agent.get_component("state")
        state_plugin = state_component.get_plugin()

        # 读 plan 决策（state key 为 plan_decision）
        decision = await state_plugin.get_state("plan_decision") or {"action": "stay"}
        controller = self.agent.controller
        location = await state_plugin.get_state("location")
        current_state = {
            "location": location,
            "known_map": await state_plugin.get_state("known_map") or [],
        }

        if decision.get("action") == "move":
            new_state, ok, reason = apply_move(self._world, current_state, decision.get("target", ""))
            if not ok:
                await state_plugin.set_state("feedback", reason)
                return
            # Recorder: leave 旧地点，enter 新地点
            await self._scene_call(controller, location, "agent_leave", self.agent.agent_id)
            first_sight = await self._scene_call(controller, new_state["location"], "agent_enter", self.agent.agent_id)
            # 更新 state
            await state_plugin.set_state("location", new_state["location"])
            await state_plugin.set_state("known_map", new_state["known_map"])
            await state_plugin.set_state("feedback", first_sight or "")
            # 持有物品跟随移动
            get_object_registry().relocate_holdings(self.agent.agent_id, new_state["location"], tick=current_tick)
            logger.info("[%s] tick %s 移动 %s -> %s", self.agent.agent_id, current_tick, location, new_state["location"])
        elif decision.get("action") == "do":
            result = await self._scene_call(controller, location, "submit_action",
                                            self.agent.agent_id, decision.get("detail", ""), current_tick)
            feedback = (result or {}).get("private_feedback", "") if isinstance(result, dict) else ""
            await state_plugin.set_state("feedback", feedback)
        else:
            await state_plugin.set_state("feedback", "")

    async def _scene_call(self, controller, location_id: str, method: str, *args):
        try:
            return await controller.run_environment(f"scene_{location_id}", method, *args)
        except Exception as exc:
            logger.warning("scene_%s.%s 调用失败: %s", location_id, method, exc)
            return None

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
