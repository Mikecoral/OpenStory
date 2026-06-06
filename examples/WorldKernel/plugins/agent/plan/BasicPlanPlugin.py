"""Plan plugin: generates a LongTask and 12 hourly plans per day.

Generic port of story_of_the_stone's BasicPlanPlugin:
- No hardcoded 红楼梦 character roster — the roster is discovered at runtime.
- No TMX parsing — accessible locations come from the ``space`` environment plugin.
- World context is injected via ``set_world_context`` (from Stage1 world_background)
  instead of hardcoding "红楼梦第80回".
- Profile formatting follows the Stage2/Stage3 character schema
  (personality / goals / memories / capabilities / role).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_distributed.toolkit.logger import get_logger

from plugins.utils.schemas import HourlyPlan, LongTask

logger = get_logger(__name__)


class BasicPlanPlugin(PlanPlugin):
    """Generates long-term and hourly plans grounded in the agent's profile."""

    # World theme/background injected at startup (replaces 红楼梦第80回 framing).
    _world_context: str = "一个开放的模拟世界"
    # Accessible location names, optionally injected; otherwise queried at runtime.
    _available_locations: List[str] = []

    @classmethod
    def set_world_context(cls, context: str) -> None:
        if context:
            cls._world_context = context
        logger.info("[BasicPlanPlugin] World context set: %s", cls._world_context)

    @classmethod
    def set_locations(cls, locations: List[str]) -> None:
        cls._available_locations = list(locations or [])
        logger.info("[BasicPlanPlugin] Injected %d locations", len(cls._available_locations))

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
        logger.info("[%s][N/A] BasicPlanPlugin initialization completed", self.agent_id)

    # ── Location discovery ──────────────────────────────────────────
    async def _get_accessible_locations(self, profile: Dict[str, Any], current_tick: int) -> List[str]:
        """Return location names the agent may go to.

        Prefers the injected list; otherwise asks the ``space`` environment plugin.
        """
        if self._available_locations:
            return self._available_locations
        if not self.controller:
            return []
        try:
            locations = await self.controller.run_environment(
                "space", "list_accessible_locations", profile, current_tick
            )
            names = [
                str(loc.get("name") or loc.get("id"))
                for loc in (locations or [])
                if isinstance(loc, dict)
            ]
            return [n for n in names if n]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][%s] Failed to query accessible locations: %s", self.agent_id, current_tick, exc)
            return []

    async def _get_all_agent_ids(self) -> List[str]:
        if not self.controller:
            return []
        try:
            return await self.controller.get_all_agent_ids()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s][N/A] Failed to get all agent ids: %s", self.agent_id, exc)
            return []

    def _format_characters_info(self, all_agent_ids: List[str]) -> str:
        others = [aid for aid in all_agent_ids if aid != self.agent_id]
        if not others:
            return "当前世界中暂无其他已知角色。"
        return "当前世界中的其他角色：" + "、".join(others)

    # ── Profile formatting (Stage2/Stage3 schema) ───────────────────
    def _format_profile_for_prompt(self, profile: Dict[str, Any]) -> str:
        name = profile.get("name") or profile.get("id") or "未知"
        role = profile.get("role", "")

        personality = profile.get("personality", {}) or {}
        traits = personality.get("traits", [])
        values = personality.get("values", [])
        speech_style = personality.get("speech_style", "")

        goals = profile.get("goals", {}) or {}
        short_goal = goals.get("short_term_goal", "")
        long_goal = goals.get("long_term_goal", "")
        motivation = goals.get("motivation", "")

        capabilities = profile.get("capabilities", {}) or {}
        skills = capabilities.get("skills", [])

        memories = profile.get("memories", {}) or {}
        background = memories.get("background_summary", "")
        key_events = memories.get("key_events", [])

        def _join(value: Any) -> str:
            if isinstance(value, list):
                return "、".join(str(v) for v in value if v) or "未知"
            return str(value) if value else "未知"

        lines = [
            "人物档案：",
            f"姓名：{name}",
        ]
        if role:
            lines.append(f"角色定位：{role}")
        lines.append(f"性格特质：{_join(traits)}")
        lines.append(f"价值取向：{_join(values)}")
        if speech_style:
            lines.append(f"语言风格：{speech_style}")
        lines.append(f"能力专长：{_join(skills)}")
        if motivation:
            lines.append(f"核心动机：{motivation}")
        if short_goal:
            lines.append(f"短期目标：{short_goal}")
        if long_goal:
            lines.append(f"长期目标：{long_goal}")
        if background:
            lines.append(f"\n背景经历：\n{background}")
        if key_events:
            recent = key_events[-3:] if len(key_events) > 3 else key_events
            lines.append("\n重要经历：")
            for ev in recent:
                lines.append(f"- {ev}")
        return "\n".join(lines)

    # ── Main loop ───────────────────────────────────────────────────
    async def execute(self, current_tick: int) -> None:
        try:
            state_plugin = self._component.agent.get_component("state").get_plugin()
            profile_plugin = self._component.agent.get_component("profile").get_plugin()

            if not await state_plugin.is_active():
                reason = await state_plugin.get_inactive_reason()
                logger.warning("[%s][%s] Agent offline, skip planning. Reason: %s", self.agent_id, current_tick, reason)
                return

            profile = profile_plugin.get_agent_profile()
            current_long_task = await state_plugin.get_long_task()

            if current_long_task is None:
                long_task_str = await self.generate_long_task(self.agent_id, current_tick, profile)
                await state_plugin.set_long_task(long_task_str)
                current_long_task = long_task_str
                logger.info("[%s][%s] Generated and stored LongTask", self.agent_id, current_tick)

            if current_tick >= 0 and current_tick % 12 == 0:
                hourly_plans = await self.generate_hourly_plans(
                    self.agent_id, current_tick, profile, current_long_task
                )
                await state_plugin.set_hourly_plans(hourly_plans, tick=current_tick)
                logger.info("[%s][%s] Generated and stored 12 hourly plans", self.agent_id, current_tick)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s][%s] Error executing PlanPlugin: %s", self.agent_id, current_tick, exc)

    async def generate_long_task(self, agent_id: str, current_tick: int, profile: Dict[str, Any]) -> str:
        profile = profile or {}
        goals = profile.get("goals", {}) or {}
        motivation = goals.get("motivation", "未知驱动")
        plan = await self._generate_plan_based_on_profile(profile)
        long_task = LongTask(
            task_description=plan,
            motivation=motivation,
            plan=plan,
            created_tick=current_tick,
            status="pending",
        )
        logger.info("[%s][%s] Generated LongTask: %s", agent_id, current_tick, long_task.to_string())
        return long_task.to_string()

    async def _generate_plan_based_on_profile(self, profile: Dict[str, Any]) -> str:
        formatted_profile = self._format_profile_for_prompt(profile)
        all_agent_ids = await self._get_all_agent_ids()
        characters_info = self._format_characters_info(all_agent_ids)

        prompt = f"""你是一个智能体的长期计划生成器。请根据以下人物档案，生成一个符合人物性格和动机的长期计划。

【世界背景】
{self._world_context}

【当前世界角色】
{characters_info}

{formatted_profile}

要求：
1. 计划必须紧密结合人物的核心动机和性格特点
2. 计划应当具体可行，体现人物的行为风格
3. 如果有重要经历，可考虑这些经历对计划的影响
4. 计划要在有限时间内可以完成，不要过于长远或短期
5. 计划长度控制在200字以内
6. 明确说明任务目标、行动方式以及想要获得的具体结果
7. 用第一人称自然表达，不要使用"因为某某驱动"这类生硬开头
8. 生成具体的、一次性的目标或事件，不要生成规律性的重复行为
9. 计划必须可实现，不要设定不切实际的目标
10. 必须使用中文输出

请生成计划："""

        if not self.model:
            raise RuntimeError("Model not initialized")
        plan = (await self.model.chat(prompt)).strip()
        logger.info("[%s][N/A] Generated plan: %s", self.agent_id, plan[:80])
        return plan

    async def generate_hourly_plans(
        self, agent_id: str, current_tick: int, profile: Dict[str, Any], long_task: str | None = None
    ) -> List[List[Any]]:
        profile = profile or {}
        formatted_profile = self._format_profile_for_prompt(profile)
        all_agent_ids = await self._get_all_agent_ids()
        characters_info = self._format_characters_info(all_agent_ids)
        locations = await self._get_accessible_locations(profile, current_tick)

        long_task_info = f"\n\n【长期目标】\n{long_task}" if long_task else ""
        if locations:
            location_rule = (
                "6. 【严格限制】地点必须从以下列表中选择，不能使用列表外的地点：\n   "
                + "、".join(locations)
            )
        else:
            location_rule = "6. 地点必须是世界中存在的具体场所"

        prompt = f"""你是一个智能体的日程计划生成器。请根据以下人物档案，生成该人物一天12个时段的详细行动计划。

【世界背景】
{self._world_context}

【当前世界角色】
{characters_info}

{formatted_profile}{long_task_info}

时段说明：一天划分为 0-11 共 12 个时段，从清晨到深夜依次推进。

要求：
1. 为每个时段(0-11)生成一个具体行动
2. 行动必须符合人物性格、定位与核心动机
3. 行动要具体，包含动作、目标对象和地点
4. 【重要建议】大部分时间应专注于自己的事情
   - 建议只有1-2个时段涉及与其他具体角色的互动(target 为具体角色名)
   - 其他时段的 target 填写"自己"或"无"
5. 目标对象若涉及其他角色，必须使用其在角色列表中的完整名称；否则填"自己"或"无"
{location_rule}
7. 行动描述控制在10-20字
8. 为每个行动评估重要性分数(1-10)：
   - 1-3：日常琐事，对剧情影响很小
   - 4-6：一般活动，有一定价值
   - 7-8：重要活动，推动剧情发展
   - 9-10：核心事件，对剧情有重大影响
9. 严格按JSON格式返回，不要有任何其他文字
10. 内容描述必须使用中文输出

请按以下JSON格式返回12个时段的计划：
[
  {{"action": "行动描述", "time": 0, "target": "目标对象", "location": "地点", "importance": 重要性分数}},
  ...
  {{"action": "行动描述", "time": 11, "target": "目标对象", "location": "地点", "importance": 重要性分数}}
]"""

        if not self.model:
            raise RuntimeError("Model not initialized")
        response = (await self.model.chat(prompt)).strip()
        plans_data = self._parse_plan_json(response)

        hourly_plans: List[List[Any]] = []
        for item in plans_data:
            hp = HourlyPlan(
                action=item["action"],
                time=item["time"],
                target=item["target"],
                location=item["location"],
                importance=item["importance"],
            )
            hourly_plans.append(hp.to_list())
        logger.info("[%s][%s] Generated %d hourly plans", agent_id, current_tick, len(hourly_plans))
        return hourly_plans

    async def replan_remaining_plans(
        self,
        agent_id: str,
        current_tick: int,
        profile: Dict[str, Any],
        long_task: str | None = None,
        start_hour: int = 0,
    ) -> List[List[Any]]:
        profile = profile or {}
        formatted_profile = self._format_profile_for_prompt(profile)
        all_agent_ids = await self._get_all_agent_ids()
        characters_info = self._format_characters_info(all_agent_ids)
        locations = await self._get_accessible_locations(profile, current_tick)
        remaining = 12 - start_hour
        long_task_info = f"\n\n【长期目标】\n{long_task}" if long_task else ""
        location_rule = (
            "5. 【严格限制】地点必须从以下列表中选择：\n   " + "、".join(locations)
            if locations else "5. 地点必须是世界中存在的具体场所"
        )

        prompt = f"""你是一个智能体的日程计划生成器。请为该人物重新规划从第 {start_hour} 个时段开始的剩余 {remaining} 个时段。

【世界背景】
{self._world_context}

【当前世界角色】
{characters_info}

{formatted_profile}{long_task_info}

要求：
1. 仅为第 {start_hour} 到第 11 个时段生成计划（共 {remaining} 个）
2. 行动符合人物性格、定位与核心动机
3. 行动具体，包含动作、目标对象和地点
4. 大部分时段 target 填"自己"或"无"，仅少数涉及其他具体角色
{location_rule}
6. 行动描述10-20字，并给出重要性分数(1-10)
7. 严格按JSON格式返回，必须使用中文

请按JSON格式返回 {remaining} 个时段：
[
  {{"action": "行动描述", "time": {start_hour}, "target": "目标对象", "location": "地点", "importance": 重要性分数}},
  ...
  {{"action": "行动描述", "time": 11, "target": "目标对象", "location": "地点", "importance": 重要性分数}}
]"""

        if not self.model:
            raise RuntimeError("Model not initialized")
        response = (await self.model.chat(prompt)).strip()
        plans_data = self._parse_plan_json(response)

        state_plugin = self._component.agent.get_component("state").get_plugin()
        current_day = (current_tick // 12) + 1
        existing = await state_plugin.get_hourly_plans(day=current_day)

        new_plans: List[List[Any]] = []
        for hour in range(12):
            if hour < start_hour:
                kept = None
                if existing:
                    for plan in existing:
                        if len(plan) >= 5 and plan[1] == hour:
                            kept = plan
                            break
                new_plans.append(kept or ["", hour, "自己", "", 1])
            else:
                found = None
                for item in plans_data:
                    if item.get("time") == hour:
                        found = HourlyPlan(
                            action=item["action"], time=item["time"], target=item["target"],
                            location=item["location"], importance=item["importance"],
                        ).to_list()
                        break
                new_plans.append(found or ["休息", hour, "自己", "", 1])

        await state_plugin.set_hourly_plans(new_plans, tick=current_tick)
        logger.info("[%s][%s] Replanned remaining plans (%d slots)", agent_id, current_tick, len(new_plans))
        return new_plans

    @staticmethod
    def _parse_plan_json(response: str) -> List[Dict[str, Any]]:
        start = response.find("[")
        end = response.rfind("]") + 1
        json_str = response[start:end] if start != -1 and end > start else response
        return json.loads(json_str)
