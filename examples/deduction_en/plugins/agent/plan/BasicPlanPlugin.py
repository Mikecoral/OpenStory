from typing import List, Dict, Any, Tuple

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_distributed.toolkit.logger import get_logger
from agentkernel_distributed.toolkit.storages import RedisKVAdapter
from ...utils.schemas import *

logger = get_logger(__name__)

class BasicPlanPlugin(PlanPlugin):
    """
    A basic plan plugin for agents to decide the plan of different granularity.
    """

    # Available locations parsed from map file, injected by run_simulation.py upon startup
    _available_locations: List[str] = []
    # List of original characters from Dream of the Red Chamber (Chapter 80)
    _original_characters: List[str] = [
        "贾宝玉", "林黛玉", "薛宝钗", "王熙凤", "贾母", "王夫人", "贾政",
        "贾探春", "贾迎春", "贾惜春", "李纨", "秦可卿", "妙玉", "史湘云",
        "贾琏", "贾环", "赵姨娘", "平儿", "袭人", "晴雯", "麝月", "紫鹃",
        "莺儿", "香菱", "薛蟠", "薛姨妈", "贾赦", "邢夫人", "尤氏",
        "贾珍", "贾蓉", "贾兰", "刘姥姥", "焦大", "赖大", "林之孝",
        "周瑞", "王善保", "来旺", "智能", "柳五儿", "龄官", "芳官"
    ]

    @classmethod
    def set_locations(cls, locations: List[str]) -> None:
        cls._available_locations = locations
        logger.info(f"[BasicPlanPlugin] Injected {len(locations)} locations: {locations}")

    def __init__(self, redis: RedisKVAdapter) -> None:
        """
        Initialize the Plan Plugin and the variables.
        """
        super().__init__()
        self.redis = redis
        self.model = None
        self.agent_id = None

    async def init(self) -> None:
        """
        Initialize the Plan Plugin, get model and agent_id from component.
        """
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model

        # Parse TMX directly within Actor, do not rely on main process class variable injection
        if not BasicPlanPlugin._available_locations:
            try:
                import xml.etree.ElementTree as ET
                import os
                tmx_path = os.path.join("map", "sos.tmx")
                tree = ET.parse(tmx_path)
                root = tree.getroot()
                locations = []
                for top_group in root.findall("group"):
                    if top_group.get("name") == "地点":
                        for sub_group in top_group.findall("group"):
                            for layer in sub_group.findall("layer"):
                                name = layer.get("name")
                                if name:
                                    locations.append(name)
                        for layer in top_group.findall("layer"):
                            name = layer.get("name")
                            if name:
                                locations.append(name)
                BasicPlanPlugin._available_locations = locations
                logger.info(f"[{self.agent_id}][N/A] Loaded {len(locations)} locations from TMX: {locations}")
            except Exception as e:
                logger.warning(f"[{self.agent_id}][N/A] Failed to load TMX locations: {e}")

        logger.info(f"[{self.agent_id}][N/A] BasicPlanPlugin initialization completed")

    async def _get_all_agent_ids(self) -> List[str]:
        """
        Get all agent IDs from Redis

        Returns:
            List[str]: List of all agent IDs
        """
        agent_ids = []
        try:
            if self.redis and self.redis.client:
                async for key in self.redis.client.scan_iter(match="*:profile"):
                    # Key format is "agent_id:profile", extract agent_id
                    agent_id = key.split(":")[0]
                    agent_ids.append(agent_id)
        except Exception as e:
            logger.warning(f"[{self.agent_id}][N/A] Failed to get all agent IDs: {e}")
        return agent_ids

    def _format_characters_info(self, all_agent_ids: List[str]) -> str:
        """
        Format character information, distinguishing original characters and new faces

        Args:
            all_agent_ids: List of all agent IDs

        Returns:
            str: Formatted character information text
        """
        # Find new faces (not in original list)
        new_faces = [aid for aid in all_agent_ids if aid not in self._original_characters]

        info_parts = ["世界拥有红楼梦80回时存在的全部角色"]
        if new_faces:
            info_parts.append(f"以及新面孔：{', '.join(new_faces)}")

        return "，".join(info_parts)

    async def execute(self, current_tick: int) -> None:
        """
        Execute the Plan Plugin at every system tick.

        Args:
            current_tick (int): The system current tick.
        """
        try:
            # Access other components via agent.get_component(), then get plugin via get_plugin()
            state_component = self._component.agent.get_component("state")
            profile_component = self._component.agent.get_component("profile")

            state_plugin = state_component.get_plugin()
            profile_plugin = profile_component.get_plugin()

            # Check if active
            if not await state_plugin.is_active():
                reason = await state_plugin.get_inactive_reason()
                logger.warning(f"[{self.agent_id}][{current_tick}] Agent is offline, stop generating plans. Reason: {reason}")
                return

            profile = profile_plugin.get_agent_profile()

            # Get current long_task
            current_long_task = await state_plugin.get_long_task()

            # If no long_task yet, generate one
            if current_long_task is None:
                # Generate long_task
                long_task_str = await self.generate_long_task(
                    agent_id=self.agent_id,
                    current_tick=current_tick,
                    profile=profile
                )

                # Store generated long_task to state
                await state_plugin.set_long_task(long_task_str)
                current_long_task = long_task_str  # Update local variable for hourly plan generation below
                logger.info(f"[{self.agent_id}][{current_tick}] Generated and stored LongTask")
            else:
                logger.debug(f"[{self.agent_id}][{current_tick}] LongTask already exists, skipping generation")

            # Generate 12 hourly plans at specific ticks (1, 13, 25, 37...)
            # Pattern: Starting from tick 1, generate once every 12 ticks
            if current_tick >= 0 and (current_tick) % 12 == 0:
                logger.info(f"[{self.agent_id}][{current_tick}] Starting to generate 12 hourly plans")

                # Generate 12 hourly plans
                hourly_plans = await self.generate_hourly_plans(
                    agent_id=self.agent_id,
                    current_tick=current_tick,
                    profile=profile,
                    long_task=current_long_task
                )

                # Store hourly plans to state
                await state_plugin.set_hourly_plans(hourly_plans)
                logger.info(f"[{self.agent_id}][{current_tick}] Generated and stored 12 hourly plans")
            else:
                logger.debug(f"[{self.agent_id}][{current_tick}] Not a plan generation cycle, skipping hourly plan generation")

        except Exception as e:
            logger.error(f"[{self.agent_id}][{current_tick}] Error executing PlanPlugin: {e}")

    async def generate_long_task(self, agent_id: str, current_tick: int, profile: Dict[str, Any]) -> str:
        """
        Generate LongTask and return in string format

        Args:
            agent_id: Agent ID
            current_tick: Current tick number
            profile: Agent profile data

        Returns:
            str: String representation of LongTask
        """
        if not profile:
            logger.warning(f"[{agent_id}][{current_tick}] No profile provided, using default configuration")
            profile = {}

        # Extract core motivation
        motivation = profile.get('核心驱动', '未知驱动')

        # Generate plan using LLM based on character info
        plan = await self._generate_plan_based_on_profile(profile)

        # Create LongTask object
        long_task = LongTask(
            task_description=plan,
            motivation=motivation,
            plan=plan,
            created_tick=current_tick,
            status="pending"
        )

        # Log generated LongTask
        logger.info(f"[{agent_id}][{current_tick}] Generated LongTask: {long_task.to_string()}")

        # Return string format
        return long_task.to_string()

    def _format_profile_for_prompt(self, profile: Dict[str, Any]) -> str:
        """
        Format profile data into text format suitable for LLM in English
        """
        name = profile.get('id', 'Unknown')
        family = profile.get('家族', 'Unknown')
        gender = profile.get('性别', 'Unknown')
        personality = profile.get('性格', 'Unknown')
        motivation = profile.get('核心驱动', 'Unknown')
        language_style = profile.get('语言风格', 'Unknown')
        background = profile.get('背景经历', 'Unknown')

        father = profile.get('父亲', '')
        mother = profile.get('母亲', '')
        status = profile.get('嫡庶', '')

        major_events = profile.get('重大节点', [])
        recent_events = major_events[-3:] if len(major_events) > 3 else major_events

        formatted_text = f"""Character Profile:
Name: {name}
Family/Faction: {family}
Gender: {gender}"""

        if father or mother:
            formatted_text += f"\nFamily Relations:"
            if father:
                formatted_text += f" Father: {father}"
            if mother:
                formatted_text += f" Mother: {mother}"
            if status:
                formatted_text += f" ({status})"

        formatted_text += f"""

Personality Traits: {personality}
Core Drive: {motivation}
Linguistic Style: {language_style}

Background Experience:
{background}"""

        if recent_events:
            formatted_text += f"\n\nImportant Experiences:"
            for event in recent_events:
                round_num = event.get('回合', 'Unknown')
                content = event.get('内容', '')
                formatted_text += f"\n- Round {round_num}: {content}"

        return formatted_text

    async def _generate_plan_based_on_profile(self, profile: Dict[str, Any]) -> str:
        formatted_profile = self._format_profile_for_prompt(profile)
        all_agent_ids = await self._get_all_agent_ids()
        
        new_faces = [aid for aid in all_agent_ids if aid not in self._original_characters]
        characters_info = "The world contains all original characters from Chapter 80 of Dream of the Red Chamber."
        if new_faces:
            characters_info += f" Also includes new faces: {', '.join(new_faces)}"

        prompt = f"""You are an agent's long-term plan generator. Please generate a long-term plan that matches the character's personality and motivation based on the following profile. Respond in English.

[Important Context]
- You are currently in Chapter 80 of "Dream of the Red Chamber".
- Please generate a plan that fits the current plot.

[Characters in Current World]
{characters_info}

{formatted_profile}

Requirements:
1. The plan must be closely tied to the character's core drive and personality.
2. The plan should be specific, feasible, and reflect their behavioral style.
3. Keep the plan length around 200 words.
4. Clearly state your task goal, action method, and the specific outcome you want.
5. [CRITICAL] Write naturally in the first person. Do not use rigid openings like "Because of my drive...".
6. [CRITICAL] Do not generate daily repetitive routines. Formulate a specific, one-time overarching goal or event.

Please generate the plan:"""

        try:
            if self.model:
                plan = await self.model.chat(prompt)
                plan = plan.strip()
                logger.info(f"[{self.agent_id}][N/A] Generated plan using LLM: {plan}")
                return plan
            else:
                raise Exception("Model not initialized")
        except Exception as e:
            logger.error(f"[{self.agent_id}][N/A] Failed to generate plan with LLM: {e}")
            raise

    async def generate_hourly_plans(self, agent_id: str, current_tick: int, profile: Dict[str, Any], long_task: str = None) -> List[List[Any]]:
        if not profile:
            profile = {}

        formatted_profile = self._format_profile_for_prompt(profile)
        all_agent_ids = await self._get_all_agent_ids()
        
        new_faces = [aid for aid in all_agent_ids if aid not in self._original_characters]
        characters_info = "The world contains all original characters from Chapter 80."
        if new_faces:
            characters_info += f" Also includes new faces: {', '.join(new_faces)}"

        long_task_info = f"\n\n[Long-Term Goal]\n{long_task}" if long_task else ""

        if self._available_locations:
            locations_str = "、".join(self._available_locations)
            location_rule = f"6. [STRICT RESTRICTION] The location MUST be selected from the following list ONLY:\n   {locations_str}"
        else:
            location_rule = "6. The location must be a specific place (e.g., Grand View Garden)."

        prompt = f"""You are a daily schedule generator for an agent. Please generate a detailed action plan for the 12 periods (shichen/hours) of a day based on the profile. Respond in English.

[Important Context]
- You are currently in Chapter 80 of "Dream of the Red Chamber".

[Characters in Current World]
{characters_info}

{formatted_profile}{long_task_info}

Ancient 12 Periods Reference:
0 - Zi (23:00-1:00): Rest
1 - Chou (1:00-3:00): Late Night
2 - Yin (3:00-5:00): Dawn
3 - Mao (5:00-7:00): Early Morning
4 - Chen (7:00-9:00): Morning
5 - Si (9:00-11:00): Late Morning
6 - Wu (11:00-13:00): Noon
7 - Wei (13:00-15:00): Afternoon
8 - Shen (15:00-17:00): Late Afternoon
9 - You (17:00-19:00): Evening
10 - Xu (19:00-21:00): Night
11 - Hai (21:00-23:00): Late Night

Requirements:
1. Generate one specific action for each period (0-11).
2. Actions must fit the character's personality and core drive.
3. Actions should be specific: include the action, target character, and location.
4. [IMPORTANT ADVICE] Most of the time should be spent alone.
   - Out of 12 periods, only 1-2 should involve interaction with other specific characters (target being a name).
   - For other periods, fill in "None" or "Self" for the target.
   - Characters should handle daily routines, rest, or think independently.
5. [CRITICAL] Target characters must use their FULL NAMES.
   - If not involving anyone, strictly write "None" or "Self".
{location_rule}
7. Keep action descriptions brief (10-20 words).
8. Evaluate an importance score (1-10) for each action:
   - 1-3: Trivial daily routines (e.g., eating, resting)
   - 4-6: General activities (e.g., visiting, reading)
   - 7-8: Important activities driving the plot (e.g., key dialogues, decisions)
   - 9-10: Core events with major plot impact (e.g., critical conflicts)
9. Strictly return in JSON format, without any Markdown blocks or extra text.

Please return the 12-period plan in the exact JSON format below:
[
  {{"action": "Action description", "time": 0, "target": "Target character", "location": "Location", "importance": Score}},
  ...
  {{"action": "Action description", "time": 11, "target": "Target character", "location": "Location", "importance": Score}}
]"""

        try:
            if not self.model:
                raise Exception("Model not initialized")

            response = await self.model.chat(prompt)
            response = response.strip()

            import json
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                plans_data = json.loads(json_str)
            else:
                plans_data = json.loads(response)

            hourly_plans = []
            for plan_data in plans_data:
                hourly_plan = HourlyPlan(
                    action=plan_data['action'],
                    time=plan_data['time'],
                    target=plan_data['target'],
                    location=plan_data['location'],
                    importance=plan_data['importance']
                )
                hourly_plans.append(hourly_plan.to_list())

            hourly_plans = self._log_target_statistics(hourly_plans, agent_id, current_tick)
            return hourly_plans

        except Exception as e:
            logger.error(f"[{agent_id}][{current_tick}] Failed to generate hourly plans: {e}")
            raise

    def _log_target_statistics(self, hourly_plans: List[List[Any]], agent_id: str, current_tick: int) -> List[List[Any]]:
        """
        Log statistics of hours involving other characters within a day

        Args:
            hourly_plans: 12 hourly plans list
            agent_id: Agent ID
            current_tick: Current tick number

        Returns:
            List[List[Any]]: Original plans list (unmodified)
        """
        # Find all hours involving other characters (target is not "self" or "none")
        plans_with_target = []
        for i, plan in enumerate(hourly_plans):
            # plan format: [action, time, target, location, importance]
            target = plan[2]
            if target and target not in ["自己", "无", "None", ""]:
                plans_with_target.append((i, plan))

        # Log statistics
        if len(plans_with_target) > 0:
            logger.info(f"[{agent_id}][{current_tick}] {len(plans_with_target)} hours in a day involve interacting with other characters")
            for _, plan in plans_with_target:
                logger.debug(f"  - Hour {plan[1]}: Interact with {plan[2]}, importance {plan[4]}")
        else:
            logger.info(f"[{agent_id}][{current_tick}] No plans interacting with other characters in a day")

        return hourly_plans