
from __future__ import annotations

import importlib.util
import json
import sys
import types
from typing import Any

if "faker" not in sys.modules and importlib.util.find_spec("faker") is None:
    faker_stub = types.ModuleType("faker")
    faker_stub.Faker = type("Faker", (), {})
    sys.modules["faker"] = faker_stub
if "redis" not in sys.modules and importlib.util.find_spec("redis") is None:
    redis_stub = types.ModuleType("redis")
    redis_asyncio_stub = types.ModuleType("redis.asyncio")
    redis_asyncio_stub.ConnectionPool = type("ConnectionPool", (), {"from_url": classmethod(lambda cls, *a, **k: cls())})
    redis_asyncio_stub.StrictRedis = type("StrictRedis", (), {"__init__": lambda self, *a, **k: None, "ping": lambda self: True})
    redis_asyncio_stub.Redis = redis_asyncio_stub.StrictRedis
    redis_stub.asyncio = redis_asyncio_stub
    sys.modules["redis"] = redis_stub
    sys.modules["redis.asyncio"] = redis_asyncio_stub

from agentkernel_distributed.mas.agent.base.plugin_base import (
    InvokePlugin,
    PerceivePlugin,
    PlanPlugin,
    ProfilePlugin,
    ReflectPlugin,
    StatePlugin,
)
from agentkernel_distributed.mas.agent.components import StateComponent
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)


class WKProfilePlugin(ProfilePlugin):
    def __init__(self, profile_data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.profile_data = profile_data or {}
        self.agent_id = self.profile_data.get("id", "Unknown")

    async def init(self) -> None:
        self.controller = self._component.agent.controller

    async def execute(self, current_tick: int) -> None:
        return None

    def get_agent_profile(self) -> dict[str, Any]:
        return self.profile_data

    def get_callable_profiles(self) -> dict[str, Any]:
        return {k: v for k, v in self.profile_data.items() if v and k != "raw"}

    async def get_profile(self, key: str) -> Any:
        return self.profile_data.get(key)

    async def set_profile(self, key: str, value: Any) -> None:
        self.profile_data[key] = value

    async def get_agent_profile_by_id(self, target_agent_id: str) -> dict[str, Any] | None:
        try:
            return await self.controller.run_agent_method(target_agent_id, "profile", "get_agent_profile")
        except Exception:
            return None


class WKStatePlugin(StatePlugin):
    def __init__(self, state_data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.state_data = state_data or {}
        self.agent_id = self.state_data.get("id", "Unknown")
        self.state_data.setdefault("current_tick", 0)
        self.state_data.setdefault("long_task", None)
        self.state_data.setdefault("hourly_plans", {})
        self.state_data.setdefault("short_term_memory", {})
        self.state_data.setdefault("long_term_memory", [])
        self.state_data.setdefault("dialogues", {})
        self.state_data.setdefault("is_active", True)
        self.state_data.setdefault("inactive_reason", "")
        self.state_data.setdefault("replan_log", [])
        self.state_data.setdefault("long_task_adj_log", [])

    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.state_data["id"] = self.agent_id

    async def execute(self, current_tick: int) -> None:
        self.state_data["current_tick"] = current_tick

    async def get_state(self, key: str | None = None, default: Any = None) -> Any:
        if key is None:
            return self.state_data
        return self.state_data.get(key, default)

    async def set_state(self, key: str, value: Any) -> None:
        self.state_data[key] = value

    async def set_state_batch(self, state: dict[str, Any]) -> None:
        self.state_data.update(state)

    async def get_long_task(self) -> str | None:
        return self.state_data.get("long_task")

    async def set_long_task(self, long_task: str | None) -> None:
        self.state_data["long_task"] = long_task

    async def get_hourly_plans(self, day: int | None = None) -> Any:
        plans = self.state_data.get("hourly_plans", {})
        if day is None:
            return plans
        return plans.get(str(day)) or plans.get(day)

    async def set_hourly_plans(self, hourly_plans: list, tick: int | None = None) -> None:
        effective_tick = tick if tick is not None else self.state_data.get("current_tick", 0)
        day = (effective_tick // 12) + 1
        self.state_data.setdefault("hourly_plans", {})[str(day)] = hourly_plans

    async def add_short_term_memory(self, memory: str, tick: int | None = None) -> None:
        tick = self.state_data.get("current_tick", 0) if tick is None else tick
        self.state_data.setdefault("short_term_memory", {})[str(tick)] = memory

    async def get_short_term_memory(self) -> list[dict[str, Any]]:
        memories = self.state_data.get("short_term_memory", {})
        if isinstance(memories, list):
            return [{"tick": i, "content": item} for i, item in enumerate(memories)]
        return [{"tick": int(k), "content": v} for k, v in sorted(memories.items(), key=lambda item: int(item[0]))]

    async def clear_short_term_memory(self) -> None:
        self.state_data["short_term_memory"] = {}

    async def add_long_term_memory(self, memory: str) -> None:
        self.state_data.setdefault("long_term_memory", []).append(
            {"tick": self.state_data.get("current_tick", 0), "content": memory}
        )

    async def get_long_term_memory(self) -> list[dict[str, Any]]:
        return self.state_data.get("long_term_memory", [])

    async def add_dialogue(self, tick: int, history: list) -> None:
        self.state_data.setdefault("dialogues", {})[str(tick)] = history

    async def get_dialogues(self) -> dict:
        return self.state_data.get("dialogues", {})

    async def is_active(self) -> bool:
        return bool(self.state_data.get("is_active", True))

    async def set_active_status(self, is_active: bool, reason: str = "") -> None:
        self.state_data["is_active"] = is_active
        self.state_data["inactive_reason"] = reason

    async def get_inactive_reason(self) -> str:
        return self.state_data.get("inactive_reason", "")

    async def add_replan_event(self, tick: int, reason: str, day: int, from_hour: int) -> None:
        self.state_data.setdefault("replan_log", []).append(
            {"tick": tick, "reason": reason, "day": day, "from_hour": from_hour}
        )

    async def get_replan_log(self) -> list:
        return self.state_data.get("replan_log", [])

    async def add_long_task_adjustment(self, tick: int, from_day: int) -> None:
        self.state_data.setdefault("long_task_adj_log", []).append({"tick": tick, "from_day": from_day})

    async def get_long_task_adjustment_log(self) -> list:
        return self.state_data.get("long_task_adj_log", [])

    async def restore_state(self, snapshot: dict[str, Any]) -> None:
        self.state_data.update(snapshot)


class WKStateComponent(StateComponent):
    async def get_long_task(self):
        return await self._plugin.get_long_task() if self._plugin else None

    async def get_state(self, key: str = None, default: Any = None):
        return await self._plugin.get_state(key, default) if self._plugin else default

    async def set_state(self, key: str, value: Any):
        if self._plugin:
            return await self._plugin.set_state(key, value)

    async def get_dialogues(self):
        return await self._plugin.get_dialogues() if self._plugin else {}

    async def get_long_term_memory(self):
        return await self._plugin.get_long_term_memory() if self._plugin else []

    async def get_short_term_memory(self):
        return await self._plugin.get_short_term_memory() if self._plugin else []

    async def get_hourly_plans(self, day: int = None):
        return await self._plugin.get_hourly_plans(day) if self._plugin else None

    async def is_active(self):
        return await self._plugin.is_active() if self._plugin else True

    async def get_inactive_reason(self):
        return await self._plugin.get_inactive_reason() if self._plugin else ""

    async def add_dialogue(self, tick: int, dialogue: list):
        if self._plugin:
            return await self._plugin.add_dialogue(tick, dialogue)

    async def add_long_term_memory(self, memory: str):
        if self._plugin:
            return await self._plugin.add_long_term_memory(memory)

    async def add_replan_event(self, tick: int, reason: str, day: int, from_hour: int):
        if self._plugin:
            return await self._plugin.add_replan_event(tick, reason, day, from_hour)

    async def get_replan_log(self):
        return await self._plugin.get_replan_log() if self._plugin else []

    async def add_long_task_adjustment(self, tick: int, from_day: int):
        if self._plugin:
            return await self._plugin.add_long_task_adjustment(tick, from_day)

    async def get_long_task_adjustment_log(self):
        return await self._plugin.get_long_task_adjustment_log() if self._plugin else []

    async def restore_state(self, snapshot: dict[str, Any]):
        if self._plugin:
            return await self._plugin.restore_state(snapshot)


class WKPerceivePlugin(PerceivePlugin):
    async def init(self) -> None:
        return None

    async def execute(self, current_tick: int) -> None:
        return None

    async def add_message(self, message) -> None:
        return None


class WKPlanPlugin(PlanPlugin):
    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        self.controller = self._component.agent.controller

    async def execute(self, current_tick: int) -> None:
        state = self._component.agent.get_component("state").get_plugin()
        profile = self._component.agent.get_component("profile").get_plugin().get_agent_profile()
        if not await state.is_active():
            return
        if not await state.get_long_task():
            await state.set_long_task(self._fallback_long_task(profile))
        if current_tick % 12 == 0:
            plans = await self.generate_hourly_plans(profile, current_tick)
            await state.set_hourly_plans(plans, tick=current_tick)

    async def generate_hourly_plans(self, profile: dict[str, Any], current_tick: int) -> list[list[Any]]:
        locations = await self.controller.run_environment("space", "list_accessible_locations", profile, current_tick)
        if not locations:
            locations = await self.controller.run_environment("space", "list_locations")
        cards = [self._location_card(loc) for loc in locations[:8]]
        prompt = self._build_prompt(profile, cards)
        try:
            if self.model:
                response = await self.model.chat(prompt)
                parsed = self._parse_plan_response(response)
                if parsed:
                    return self._normalize_plans(parsed, locations)
        except Exception as exc:
            logger.warning("[%s] LLM plan generation failed, using fallback: %s", self.agent_id, exc)
        return self._fallback_plans(profile, locations)

    def _build_prompt(self, profile: dict[str, Any], cards: list[str]) -> str:
        return (
            "Generate 12 tick plans as JSON only. Each item must contain action, time, target, location, importance. "
            "Location must be chosen from the location cards.\n\n"
            f"Agent profile:\n{json.dumps(profile.get('raw', profile), ensure_ascii=False)[:3000]}\n\n"
            f"Location cards:\n" + "\n".join(cards)
        )

    def _location_card(self, loc: dict[str, Any]) -> str:
        access = loc.get("access", {})
        state = loc.get("state", {})
        return (
            f"- {loc.get('name')} | type={loc.get('type')} | access={access.get('access_level')} | "
            f"state={state.get('current_state')} | events={loc.get('key_plot_events')}"
        )[:700]

    def _parse_plan_response(self, response: Any) -> list[dict[str, Any]] | None:
        if isinstance(response, list):
            response = response[0] if response else ""
        if not isinstance(response, str):
            return None
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, list) else None

    def _normalize_plans(self, items: list[dict[str, Any]], locations: list[dict[str, Any]]) -> list[list[Any]]:
        valid_names = {loc.get("name") for loc in locations}
        fallback_location = next(iter(valid_names), "")
        plans = []
        for hour in range(12):
            item = items[hour] if hour < len(items) and isinstance(items[hour], dict) else {}
            location = item.get("location") if item.get("location") in valid_names else fallback_location
            plans.append([
                str(item.get("action") or "observe the world context"),
                hour,
                str(item.get("target") or "self"),
                location,
                int(item.get("importance") or 3),
            ])
        return plans

    def _fallback_long_task(self, profile: dict[str, Any]) -> str:
        goals = profile.get("goals", {})
        return goals.get("long_term_goal") or goals.get("motivation") or "Act consistently with the generated world profile."

    def _fallback_plans(self, profile: dict[str, Any], locations: list[dict[str, Any]]) -> list[list[Any]]:
        if not locations:
            locations = [{"name": profile.get("current_location") or "Unknown", "type": "unknown"}]
        plans = []
        name = profile.get("name") or profile.get("id")
        for hour in range(12):
            loc = locations[hour % len(locations)]
            action = f"{name} uses {loc.get('name')} for {loc.get('type') or 'daily activity'}"
            plans.append([action, hour, "self", loc.get("name", ""), 4])
        return plans


class WKInvokePlugin(InvokePlugin):
    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        self.controller = self._component.agent.controller

    async def execute(self, current_tick: int) -> None:
        state = self._component.agent.get_component("state").get_plugin()
        profile = self._component.agent.get_component("profile").get_plugin().get_agent_profile()
        if not await state.is_active():
            return
        day = (current_tick // 12) + 1
        hour = current_tick % 12
        plans = await state.get_hourly_plans(day=day)
        plan = None
        for item in plans or []:
            if len(item) >= 5 and item[1] == hour:
                plan = item
                break
        if not plan:
            await state.set_state("current_action", None)
            return
        await state.set_state("current_plan", plan)
        action, _, target, location, importance = plan
        move_result = await self.controller.run_action("move", "move_to", agent_id=self.agent_id, location=location)
        if not move_result.is_successful():
            note = getattr(move_result, "message", "move failed")
            await state.set_state("current_plan_note", note)
            await state.add_replan_event(current_tick, note, day, hour)
            await state.add_short_term_memory(f"Could not enter {location}: {note}", current_tick)
            return
        location_profile = await self.controller.run_environment("space", "get_location_profile", location)
        description = self._describe_action(profile, action, target, location_profile, importance)
        await state.set_state("current_plan_note", None)
        await state.set_state("current_action", description)
        await state.add_short_term_memory(description, current_tick)

    def _describe_action(
        self,
        profile: dict[str, Any],
        action: str,
        target: str,
        location_profile: dict[str, Any] | None,
        importance: int,
    ) -> str:
        loc = location_profile or {}
        name = profile.get("name") or profile.get("id")
        atmosphere = loc.get("symbolic_meaning") or loc.get("description") or loc.get("type", "")
        return f"{name} at {loc.get('name', 'Unknown')} performs: {action}. Target: {target}. Context: {atmosphere[:180]}"


class WKReflectPlugin(ReflectPlugin):
    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id

    async def execute(self, current_tick: int) -> None:
        if (current_tick + 1) % 12 != 0:
            return
        state = self._component.agent.get_component("state").get_plugin()
        memories = await state.get_short_term_memory()
        if not memories:
            return
        summary = "; ".join(str(m.get("content", "")) for m in memories[-6:])
        await state.add_long_term_memory(f"Day summary: {summary[:500]}")
        await state.clear_short_term_memory()
