"""Invoke plugin: executes the current hour's plan."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.agent.base.plugin_base import InvokePlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

_SOLO_TARGETS = {"自己", "无", "None", "", None, "鑷繁", "鏃?"}
_DIALOGUE_IMPORTANCE_THRESHOLD = 7


class BasicInvokePlugin(InvokePlugin):
    """Executes hourly plans, resolves movement, and records memory."""

    def __init__(self, redis: Any = None) -> None:
        super().__init__()
        self.redis = redis
        self.model = None
        self.agent_id = None
        self.controller = None

    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        self.controller = self._component.agent.controller
        logger.info("[%s][N/A] BasicInvokePlugin initialization completed", self.agent_id)

    async def execute(self, current_tick: int) -> None:
        try:
            state_plugin = self._component.agent.get_component("state").get_plugin()
            profile_plugin = self._component.agent.get_component("profile").get_plugin()

            if not await state_plugin.is_active():
                return

            current_day = (current_tick // 12) + 1
            current_hour = current_tick % 12
            hourly_plans = await state_plugin.get_hourly_plans(day=current_day)
            current_plan = self._select_current_plan(hourly_plans, current_hour)

            if not current_plan:
                description = f"{self.agent_id} 当前没有具体计划，暂作休整。"
                await state_plugin.set_state("current_plan", None)
                await state_plugin.set_state("occupied_by", None)
                await state_plugin.set_state("current_action", description)
                await state_plugin.add_short_term_memory(description, tick=current_tick)
                return

            await state_plugin.set_state("current_plan", current_plan)
            action, _time, target, location, importance = current_plan[:5]

            if importance < _DIALOGUE_IMPORTANCE_THRESHOLD:
                await asyncio.sleep(2)

            occupation_info = await self._get_occupation(current_tick, self.agent_id)
            if occupation_info:
                occupier = occupation_info.get("occupier")
                occ_importance = occupation_info.get("importance", 0)
                if occupier != self.agent_id and occ_importance > importance:
                    busy = f"正在配合 {occupier} 进行：{occupation_info.get('action', '某事')}。"
                    await state_plugin.set_state("occupied_by", occupation_info)
                    await state_plugin.add_short_term_memory(busy, tick=current_tick)
                    await state_plugin.set_state("current_action", busy)
                    return

            await state_plugin.set_state("occupied_by", None)
            if not await self._occupy(current_tick, importance, action, location):
                return

            moved, move_note = await self._try_move(location, current_tick)
            if not moved:
                note = move_note or f"无法进入计划地点：{location}"
                await state_plugin.set_state("current_plan_note", note)
                await state_plugin.set_state("current_action", note)
                await state_plugin.add_short_term_memory(note, tick=current_tick)
                await self._request_replan(current_tick, note)
                return

            await state_plugin.set_state("current_plan_note", None)
            self_profile = profile_plugin.get_agent_profile()
            target_profile = None
            plan_note = None
            target_participated = False

            if target not in _SOLO_TARGETS:
                target_profile = await profile_plugin.get_agent_profile_by_id(target)
                if target_profile and await self._try_occupy_target(current_tick, target, importance, action):
                    target_participated = True
                else:
                    plan_note = f"注意：{target} 当前被占用或无法配合。"
                    await state_plugin.set_state("current_plan_note", plan_note)

            location_profile = await self._get_location_profile(location)
            relation = await self._get_relation(target)

            if importance >= _DIALOGUE_IMPORTANCE_THRESHOLD:
                desc_data = await self._generate_execution_description(
                    current_tick,
                    action,
                    target,
                    location,
                    importance,
                    self_profile,
                    target_profile,
                    plan_note,
                    location_profile,
                    relation,
                )
                description = desc_data.get("summary", "")
                dialogue_history = desc_data.get("history", [])
                if dialogue_history:
                    await state_plugin.add_dialogue(current_tick, dialogue_history)
            else:
                description = self._simple_description(self_profile, action, location, location_profile, plan_note)
                dialogue_history = []

            await state_plugin.add_short_term_memory(description, tick=current_tick)
            await state_plugin.set_state("current_action", description)

            if target_participated:
                await self._propagate_to_target(
                    target, current_tick, action, _time, location, importance, description, dialogue_history
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s][%s] Error executing InvokePlugin: %s", self.agent_id, current_tick, exc)

    @staticmethod
    def _select_current_plan(hourly_plans: Any, current_hour: int) -> list[Any] | None:
        if isinstance(hourly_plans, dict):
            if hourly_plans and all(isinstance(v, list) for v in hourly_plans.values()):
                flattened = []
                for value in hourly_plans.values():
                    flattened.extend(value if value and isinstance(value[0], list) else [value])
                hourly_plans = flattened
        if not isinstance(hourly_plans, list):
            return None
        for plan in hourly_plans:
            if isinstance(plan, list) and len(plan) >= 5 and plan[1] == current_hour:
                return plan
        return None

    async def _try_move(self, location: str, current_tick: int) -> tuple[bool, str | None]:
        if not self.controller or not location:
            return (True, None)
        try:
            result = await self.controller.run_action(
                "move", "move_to", agent_id=self.agent_id, location=location
            )
            if hasattr(result, "is_successful") and not result.is_successful():
                return (False, getattr(result, "message", "move failed"))
            if isinstance(result, dict) and result.get("status") == "error":
                return (False, str(result.get("message") or "move failed"))
            return (True, None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s][%s] move_to failed: %s", self.agent_id, current_tick, exc)
            return (False, str(exc))

    async def _request_replan(self, current_tick: int, reason: str) -> None:
        try:
            state = self._component.agent.get_component("state").get_plugin()
            profile = self._component.agent.get_component("profile").get_plugin().get_agent_profile()
            long_task = await state.get_long_task()
            plan_component = self._component.agent.get_component("plan")
            if not plan_component:
                return
            await plan_component.get_plugin().replan_remaining_plans(
                agent_id=self.agent_id,
                current_tick=current_tick,
                profile=profile,
                long_task=long_task,
                start_hour=(current_tick % 12) + 1,
            )
            await state.add_replan_event(
                tick=current_tick,
                reason=reason,
                day=(current_tick // 12) + 1,
                from_hour=(current_tick % 12) + 1,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] replan request failed: %s", self.agent_id, current_tick, exc)

    async def _get_location_profile(self, location: str) -> dict[str, Any] | None:
        if not self.controller or not location:
            return None
        try:
            return await self.controller.run_environment("space", "get_location_profile", location)
        except Exception:
            return None

    async def _get_relation(self, target: str) -> dict[str, Any] | None:
        if not self.controller or target in _SOLO_TARGETS:
            return None
        try:
            return await self.controller.run_environment("relation", "get_relation_between", self.agent_id, target)
        except Exception:
            return None

    def _simple_description(
        self,
        profile: dict[str, Any],
        action: str,
        location: str,
        location_profile: dict[str, Any] | None,
        plan_note: str | None,
    ) -> str:
        name = profile.get("name") or profile.get("id") or self.agent_id
        loc_name = (location_profile or {}).get("name") or location
        mood = (location_profile or {}).get("symbolic_meaning") or (location_profile or {}).get("description", "")
        suffix = f"这里带有{mood}的意味。" if mood else ""
        note = f" {plan_note}" if plan_note else ""
        return f"{name}正在{loc_name}执行：{action}。{suffix}{note}".strip()

    async def _get_occupation(self, tick: int, target_id: str) -> dict | None:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(f"occupation:{tick}:{target_id}")
            if isinstance(data, str):
                data = json.loads(data)
            return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] get_occupation failed: %s", self.agent_id, tick, exc)
            return None

    async def _occupy(self, tick: int, importance: int, action: str, location: str = "") -> bool:
        if not self.redis:
            return True
        try:
            key = f"occupation:{tick}:{self.agent_id}"
            existing = await self.redis.get(key)
            if existing:
                if isinstance(existing, str):
                    existing = json.loads(existing)
                if existing.get("occupier") != self.agent_id and existing.get("importance", 0) > importance:
                    return False
            await self.redis.set(
                key,
                json.dumps(
                    {"occupier": self.agent_id, "importance": importance, "action": action, "location": location},
                    ensure_ascii=False,
                ),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] occupy failed: %s", self.agent_id, tick, exc)
            return False

    async def _try_occupy_target(self, tick: int, target_id: str, my_importance: int, action: str) -> bool:
        if not self.redis:
            return True
        try:
            key = f"occupation:{tick}:{target_id}"
            occ = await self._get_occupation(tick, target_id)
            if not occ:
                await self.redis.set(
                    key,
                    json.dumps({"occupier": self.agent_id, "importance": my_importance, "action": action}, ensure_ascii=False),
                )
                return True
            occupier = occ.get("occupier")
            occ_importance = occ.get("importance", 0)
            if occupier == self.agent_id:
                return True
            if my_importance > occ_importance:
                await self.redis.set(
                    key,
                    json.dumps({"occupier": self.agent_id, "importance": my_importance, "action": action}, ensure_ascii=False),
                )
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] try_occupy_target failed: %s", self.agent_id, tick, exc)
            return False

    async def _get_agent_memory(self, agent_id: str) -> str:
        if not self.controller:
            return "无记忆"
        try:
            short_memory = await self.controller.run_agent_method(agent_id, "state", "get_short_term_memory")
            long_memory = await self.controller.run_agent_method(agent_id, "state", "get_long_term_memory")
            text = ""
            if long_memory:
                text += "[长期记忆]\n" + "\n".join(f"- {m['content']}" for m in long_memory) + "\n\n"
            if short_memory:
                text += "[近期记忆]\n" + "\n".join(f"- {m.get('content', m)}" for m in short_memory[-5:])
            return text.strip() or "无记忆"
        except Exception:
            return "无记忆"

    async def _generate_execution_description(
        self,
        current_tick: int,
        action: str,
        target: str,
        location: str,
        importance: int,
        self_profile: Dict[str, Any],
        target_profile: Dict[str, Any] | None,
        plan_note: str | None,
        location_profile: Dict[str, Any] | None,
        relation: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        self_name = self_profile.get("name") or self_profile.get("id") or self.agent_id
        default = {"summary": self._simple_description(self_profile, action, location, location_profile, plan_note), "history": []}
        if not self.model:
            return default

        participants = [self.agent_id]
        absent = []
        if target not in _SOLO_TARGETS:
            (absent if plan_note else participants).append(target)
        if len(participants) == 1:
            if absent:
                return {"summary": f"{self_name}准备在{location}执行：{action}，但{'、'.join(absent)}未到场。", "history": []}
            return default

        try:
            from plugins.agent.plan.BasicPlanPlugin import BasicPlanPlugin

            world_context = BasicPlanPlugin._world_context
        except Exception:
            world_context = "一个开放的模拟世界"

        loc_context = json.dumps(location_profile or {}, ensure_ascii=False)[:1200]
        relation_context = json.dumps(relation or {}, ensure_ascii=False)
        dialogue_history: list[str] = []
        speaker_idx = 0
        for _round_num in range(8):
            speaker_id = participants[speaker_idx]
            sp_profile = self_profile if speaker_id == self.agent_id else (target_profile or {})
            sp_name = sp_profile.get("name") or sp_profile.get("id") or speaker_id
            sp_personality = sp_profile.get("personality", {}) or {}
            sp_memory = await self._get_agent_memory(speaker_id)

            prompt = f"""请扮演 {sp_name}，在当前场景中说一句话或做一个动作。

【世界背景】
{world_context}

【行动】
{action}

【地点语义】
{loc_context}

【关系】
{relation_context}

【角色设定】
性格：{sp_personality.get('traits', [])}
说话风格：{sp_personality.get('speech_style', '未知')}

【记忆】
{sp_memory}

【已有对话】
{chr(10).join(dialogue_history) if dialogue_history else '对话刚开始'}

要求：使用中文；符合角色身份和地点氛围；格式为“[动作]台词”；若自然结束，在末尾加 [END]。
"""
            response = str(await self.model.chat(prompt) or "").strip()
            dialogue_history.append(f"{sp_name}：{response}")
            if "[END]" in response or "END" in response:
                break
            speaker_idx = (speaker_idx + 1) % len(participants)

        summary_prompt = f"""请用 50-100 字中文总结这次互动。只返回总结正文。

地点：{location}
行动：{action}
地点语义：{loc_context}
对话：
{chr(10).join(dialogue_history)}
"""
        summary = str(await self.model.chat(summary_prompt) or "").strip()
        return {"summary": summary or default["summary"], "history": dialogue_history}

    async def _propagate_to_target(
        self,
        target: str,
        current_tick: int,
        action: str,
        time: int,
        location: str,
        importance: int,
        description: str,
        dialogue_history: list,
    ) -> None:
        if not self.controller:
            return
        try:
            occ = {"occupier": self.agent_id, "importance": importance, "action": action}
            await self.controller.run_agent_method(target, "state", "set_state", "occupied_by", occ)
            await self.controller.run_agent_method(
                target, "state", "set_state", "current_plan", [action, time, self.agent_id, location, importance]
            )
            await self.controller.run_agent_method(target, "state", "add_short_term_memory", description, current_tick)
            await self.controller.run_agent_method(target, "state", "set_state", "current_action", description)
            if dialogue_history:
                await self.controller.run_agent_method(target, "state", "add_dialogue", current_tick, dialogue_history)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] propagate to %s failed: %s", self.agent_id, current_tick, target, exc)
