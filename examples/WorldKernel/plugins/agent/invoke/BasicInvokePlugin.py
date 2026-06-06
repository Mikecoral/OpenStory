"""Invoke plugin: executes the current hour's plan.

Generic port of story_of_the_stone's BasicInvokePlugin:
- Redis-backed occupancy so high-importance actions can claim participants.
- Multi-agent dialogue generation for high-importance interactions, with
  generic (non-红楼梦) behavioural constraints driven by the world context.
- Movement is delegated to the ``move`` action plugin.
"""

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

_SOLO_TARGETS = {"自己", "无", "None", "", None}
_DIALOGUE_IMPORTANCE_THRESHOLD = 7


class BasicInvokePlugin(InvokePlugin):
    """Executes hourly plans, resolving occupancy and generating dialogue."""

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

            current_plan = None
            if hourly_plans:
                for plan in hourly_plans:
                    if len(plan) >= 5 and plan[1] == current_hour:
                        current_plan = plan
                        break

            if not current_plan:
                await state_plugin.set_state("current_plan", None)
                await state_plugin.set_state("occupied_by", None)
                await state_plugin.set_state("current_action", None)
                await state_plugin.add_short_term_memory(
                    f"{self.agent_id} 当前没有具体计划，稍作休息。", tick=current_tick
                )
                return

            await state_plugin.set_state("current_plan", current_plan)
            action, _time, target, location, importance = current_plan[:5]

            # Yield to higher-priority actors first.
            if importance < _DIALOGUE_IMPORTANCE_THRESHOLD:
                await asyncio.sleep(2)

            # Respect existing higher-priority occupation.
            occupation_info = await self._get_occupation(current_tick, self.agent_id)
            if occupation_info:
                occupier = occupation_info.get("occupier")
                occ_importance = occupation_info.get("importance", 0)
                if occupier != self.agent_id and occ_importance > importance:
                    occupier_action = occupation_info.get("action", "某事")
                    busy = f"正在配合 {occupier} 进行：{occupier_action}。"
                    await state_plugin.set_state("occupied_by", occupation_info)
                    await state_plugin.add_short_term_memory(busy, tick=current_tick)
                    await state_plugin.set_state("current_action", busy)
                    return

            await state_plugin.set_state("occupied_by", None)
            if not await self._occupy(current_tick, importance, action, location):
                return

            # Move to the planned location first (delegated to move action).
            await self._try_move(location, current_tick)

            self_profile = profile_plugin.get_agent_profile()
            target_profile = None
            plan_note = None
            target_participated = False

            if target not in _SOLO_TARGETS:
                target_profile = await profile_plugin.get_agent_profile_by_id(target)
                if target_profile and await self._try_occupy_target(current_tick, target, importance, action):
                    target_participated = True
                    await state_plugin.set_state("current_plan_note", None)
                else:
                    plan_note = f"注意：{target} 目前正被占用或无法配合。"
                    await state_plugin.set_state("current_plan_note", plan_note)
            else:
                await state_plugin.set_state("current_plan_note", None)

            if importance >= _DIALOGUE_IMPORTANCE_THRESHOLD:
                desc_data = await self._generate_execution_description(
                    current_tick, action, target, location, importance,
                    self_profile, target_profile, plan_note,
                )
                description = desc_data.get("summary", "")
                dialogue_history = desc_data.get("history", [])
                if dialogue_history:
                    await state_plugin.add_dialogue(current_tick, dialogue_history)
            else:
                self_name = self_profile.get("name") or self_profile.get("id") or self.agent_id
                description = f"{self_name} 正在 {location} 执行：{action}。"
                dialogue_history = []

            await state_plugin.add_short_term_memory(description, tick=current_tick)
            await state_plugin.set_state("current_action", description)

            if target_participated:
                await self._propagate_to_target(
                    target, current_tick, action, _time, location, importance, description, dialogue_history
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s][%s] Error executing InvokePlugin: %s", self.agent_id, current_tick, exc)

    async def _try_move(self, location: str, current_tick: int) -> None:
        if not self.controller or not location:
            return
        try:
            await self.controller.run_action(
                "move", "move_to", agent_id=self.agent_id, location=location
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s][%s] move_to failed: %s", self.agent_id, current_tick, exc)

    # ── Occupancy (Redis) ───────────────────────────────────────────
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
            await self.redis.set(key, json.dumps(
                {"occupier": self.agent_id, "importance": importance, "action": action, "location": location}
            ))
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
                await self.redis.set(key, json.dumps(
                    {"occupier": self.agent_id, "importance": my_importance, "action": action}
                ))
                return True
            occupier = occ.get("occupier")
            occ_importance = occ.get("importance", 0)
            if occupier == self.agent_id:
                return True
            if my_importance > occ_importance:
                await self.redis.set(key, json.dumps(
                    {"occupier": self.agent_id, "importance": my_importance, "action": action}
                ))
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] try_occupy_target failed: %s", self.agent_id, tick, exc)
            return False

    # ── Dialogue ────────────────────────────────────────────────────
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
        except Exception:  # noqa: BLE001
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
    ) -> Dict[str, Any]:
        self_name = self_profile.get("name") or self_profile.get("id") or self.agent_id
        default = {"summary": f"{self_name} 正在 {location} 执行：{action}。", "history": []}
        if not self.model:
            return default

        participants = [self.agent_id]
        absent = []
        if target not in _SOLO_TARGETS:
            (absent if plan_note else participants).append(target)

        if len(participants) == 1:
            if absent:
                return {"summary": f"{self_name} 准备在 {location} 执行：{action}，但 {('、'.join(absent))} 未到场。", "history": []}
            return default

        try:
            from plugins.agent.plan.BasicPlanPlugin import BasicPlanPlugin
            world_context = BasicPlanPlugin._world_context
        except Exception:  # noqa: BLE001
            world_context = "一个开放的模拟世界"

        dialogue_history: list[str] = []
        speaker_idx = 0
        for round_num in range(8):
            speaker_id = participants[speaker_idx]
            sp_profile = self_profile if speaker_id == self.agent_id else (target_profile or {})
            sp_name = sp_profile.get("name") or sp_profile.get("id") or speaker_id
            sp_personality = (sp_profile.get("personality", {}) or {})
            sp_traits = sp_personality.get("traits", [])
            sp_style = sp_personality.get("speech_style", "未知")
            sp_memory = await self._get_agent_memory(speaker_id)

            prompt = f"""你正在扮演 {sp_name}。

【世界背景】
{world_context}

当前场景：{action}
地点：{location}
重要性：{importance}/10"""
            if plan_note:
                prompt += f"\n特殊情况：{plan_note}"
            prompt += f"""

{sp_name} 的设定：
- 性格特质：{('、'.join(str(t) for t in sp_traits)) if sp_traits else '未知'}
- 语言风格：{sp_style}

{sp_name} 的记忆：
{sp_memory}

已有对话：
{chr(10).join(dialogue_history) if dialogue_history else '（对话刚开始）'}

请以 {sp_name} 的身份说一句话（含动作描述）。格式：[动作]对话内容
若认为对话应结束，在末尾加 [END]。

【约束】
1. 言行必须符合该角色的性格、定位与上述世界背景设定。
2. 情绪与措辞应与角色身份一致，保持自洽，避免出现与世界观冲突的现代化表达。
3. 仅当场景明确涉及冲突或危险时，才可客观描述受伤/死亡等后果，日常互动不得出现极端结果。

{sp_name} 说：（必须使用中文）"""

            response = (await self.model.chat(prompt)).strip()
            dialogue_history.append(f"{sp_name}：{response}")
            if "[END]" in response or "END" in response:
                break
            speaker_idx = (speaker_idx + 1) % len(participants)

        summary_prompt = f"""以下是 {('、'.join(participants))} 在 {location} 的对话：

{chr(10).join(dialogue_history)}

请用一段话（50-100字）以第三人称总结这次互动。只返回总结内容。

【重要】若对话中发生致命事件，必须在总结中明确写出：
- 死亡：必须写出"XX死亡/身亡"
- 重伤：必须写出"XX重伤"
- 离场：必须写出"XX离开/消失"
这些信息是系统判断角色状态的关键。必须使用中文。"""
        summary = (await self.model.chat(summary_prompt)).strip()
        return {"summary": summary, "history": dialogue_history}

    async def _propagate_to_target(
        self, target: str, current_tick: int, action: str, time: int,
        location: str, importance: int, description: str, dialogue_history: list,
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
