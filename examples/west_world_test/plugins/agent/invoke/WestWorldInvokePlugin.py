"""执行插件：落实 plan 决策。M2 只处理 move/stay；M3 追加 Recorder 联动。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from agentkernel_distributed.mas.agent.base.plugin_base import InvokePlugin

from examples.west_world_test.worldmap.loader import WorldMap


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

    def __init__(self, world: Optional[WorldMap] = None, **_: Any) -> None:
        super().__init__()
        self._world = world

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        if self._world is None or self.agent is None:
            return
        state_component = self.agent.get_component("state")
        state_plugin = state_component.get_plugin()

        decision = await state_plugin.get_state("plan_decision") or {}
        action = decision.get("action", "stay")
        target = decision.get("target", "")

        if action == "move" and target:
            location = await state_plugin.get_state("location")
            known_map = await state_plugin.get_state("known_map") or []
            current_state = {"location": location, "known_map": known_map}

            new_state, ok, reason = apply_move(self._world, current_state, target)
            if ok:
                await state_plugin.set_state("location", new_state["location"])
                await state_plugin.set_state("known_map", new_state["known_map"])
            # If move failed, stay in place silently

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
