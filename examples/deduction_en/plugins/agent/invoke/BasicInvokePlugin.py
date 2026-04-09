from typing import List, Dict, Any, TYPE_CHECKING

from agentkernel_distributed.mas.agent.base.plugin_base import InvokePlugin
from agentkernel_distributed.toolkit.logger import get_logger
from agentkernel_distributed.toolkit.storages import RedisKVAdapter
from agentkernel_distributed.types.schemas.action import ActionResult, CallStatus

from ...utils.schemas import *

if TYPE_CHECKING:
    from ..plan.BasicPlanPlugin import BasicPlanPlugin
logger = get_logger(__name__)

class BasicInvokePlugin(InvokePlugin):
    """
    Execute the action from the plan plugin.
    """
    def __init__(self, redis: RedisKVAdapter) -> None:
        super().__init__()
        self.redis = redis
        self.model = None
        self.agent_id = None

    async def init(self) -> None:
        """
        Initialize the Invoke Plugin, get model and agent_id from component.
        """
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        logger.info(f"[{self.agent_id}][N/A] BasicInvokePlugin initialization completed")

    async def execute(self, current_tick: int) -> None:
        """
        Execute the Invoke Plugin at every system tick.

        Args:
            current_tick (int): The system current tick.
        """
        try:
            # Get related components
            state_component = self._component.agent.get_component("state")
            profile_component = self._component.agent.get_component("profile")

            state_plugin = state_component.get_plugin()
            profile_plugin = profile_component.get_plugin()

            # Check if active
            if not await state_plugin.is_active():
                # logger.debug(f"[{self.agent_id}][{current_tick}] Agent is offline, skipping execution")
                return

            # Get current day's plans (every 12 ticks is one day)
            current_day = (current_tick // 12) + 1
            hourly_plans = await state_plugin.get_hourly_plans(day=current_day)

            # Calculate current hour (0-12)
            current_hour = current_tick % 12

            # Find the plan for the current hour
            current_plan = None
            if hourly_plans:
                for plan in hourly_plans:
                    # plan format: [action, time, target, location, importance]
                    if len(plan) >= 5 and plan[1] == current_hour:
                        current_plan = plan
                        break
            else:
                logger.debug(f"[{self.agent_id}][{current_tick}] No hourly plan for day {current_day}")

            # Check if there is a highest priority plan set by the user
            user_plan_key = f"user_plan:{self.agent_id}"
            user_plan_data_str = await self.redis.get(user_plan_key)
            if user_plan_data_str:
                try:
                    import json
                    if isinstance(user_plan_data_str, str):
                        user_plan_data = json.loads(user_plan_data_str)
                    else:
                        user_plan_data = user_plan_data_str
                    
                    # Check if the plan is for the current tick
                    if user_plan_data.get('tick') == current_tick:
                        logger.info(f"[{self.agent_id}][{current_tick}] Detected highest priority plan set by user!")
                        current_plan = [
                            user_plan_data.get('action', 'Execute user plan'),
                            current_hour,
                            user_plan_data.get('target', 'None'),
                            user_plan_data.get('location', ''),
                            999  # Highest priority
                        ]
                        # Delete the plan after execution to avoid repetition
                        await self.redis.delete(user_plan_key)
                except Exception as e:
                    logger.warning(f"[{self.agent_id}][{current_tick}] Failed to parse user plan: {e}")

            if not current_plan:
                logger.debug(f"[{self.agent_id}][{current_tick}] No plan for current hour {current_hour}")
                await state_plugin.set_state('current_plan', None)
                await state_plugin.set_state('occupied_by', None)
                await state_plugin.set_state('current_action', None)
                
                # Record a "resting" short-term memory to prevent Tick missing
                idle_desc = f"{self.agent_id} currently has no specific plan and is resting slightly."
                await state_plugin.add_short_term_memory(idle_desc, tick=current_tick)
                return

            # Store the current plan in state for frontend display
            await state_plugin.set_state('current_plan', current_plan)

            # Parse the plan
            action = current_plan[0]
            time = current_plan[1]
            target = current_plan[2]
            location = current_plan[3]
            importance = current_plan[4]

            # If importance is less than 7, wait 5 seconds to let high priority tasks execute first
            if importance < 7:
                import asyncio
                await asyncio.sleep(5)
                logger.debug(f"[{self.agent_id}][{current_tick}] Low priority task waiting 5 seconds before execution")

            # Check if self is occupied
            occupation_info = await self._get_occupation(current_tick, self.agent_id)
            if occupation_info:
                occupier = occupation_info.get("occupier")
                occupier_importance = occupation_info.get("importance", 0)
                
                # If occupied by someone else and their priority is higher
                if occupier != self.agent_id and occupier_importance > importance:
                    logger.info(f"[{self.agent_id}][{current_tick}] Occupied by higher priority person {occupier}, skipping original plan")
                    # Record who occupied and their action in state
                    await state_plugin.set_state('occupied_by', occupation_info)
                    
                    # Record the occupation description
                    occupier_name = occupier.split('.')[-1] # Simple name extraction
                    occupier_action = occupation_info.get("action", "some affair")
                    busy_desc = f"Assisting {occupier_name} with {occupier_action}."
                    
                    # First add short-term memory to self, ensuring Tick is not missing
                    await state_plugin.add_short_term_memory(busy_desc, tick=current_tick)
                    # Simultaneously set current_action to occupier's action to ensure frontend shows "current action"
                    await state_plugin.set_state('current_action', busy_desc)
                    return
            
            # If not occupied by others, clear occupation info
            await state_plugin.set_state('occupied_by', None)

            # Occupy self (give up if already preemptively occupied by others)
            if not await self._occupy(current_tick, importance, action, location):
                # Re-read occupation info, go to occupied handling branch
                occupation_info = await self._get_occupation(current_tick, self.agent_id)
                if occupation_info:
                    occupier_name = occupation_info.get("occupier", "").split('.')[-1]
                    occupier_action = occupation_info.get("action", "some affair")
                    busy_desc = f"Assisting {occupier_name} with {occupier_action}."
                    await state_plugin.set_state('occupied_by', occupation_info)
                    await state_plugin.add_short_term_memory(busy_desc, tick=current_tick)
                    await state_plugin.set_state('current_action', busy_desc)
                return

            logger.info(f"[{self.agent_id}][{current_tick}] Executing plan for hour {time}: {action}")

            # Get own profile
            self_profile = profile_plugin.get_agent_profile()

            # Get target's profile (if target exists)
            target_profile = None
            plan_note = None  # Plan note
            target_participated = False  # Record if target participated in interaction
            if target and target != "None" and target != "自己" and target != "无":
                target_profile = await profile_plugin.get_agent_profile_by_id(target)
                if not target_profile:
                    logger.warning(f"[{self.agent_id}][{current_tick}] Unable to retrieve profile for target {target}")
                else:
                    # Try to occupy target
                    if not await self._try_occupy_target(current_tick, target, importance, action):
                        plan_note = f"Note: {target} is currently occupied by someone else and cannot cooperate"
                        logger.info(f"[{self.agent_id}][{current_tick}] {plan_note}")
                        # Record to state for frontend display
                        await state_plugin.set_state('current_plan_note', plan_note)
                    else:
                        target_participated = True  # Occupation successful, target participated in interaction
                        await state_plugin.set_state('current_plan_note', None)
            else:
                await state_plugin.set_state('current_plan_note', None)

            # Generate execution description (only use LLM for detailed description if importance >= 7)
            if importance >= 7:
                description_data = await self._generate_execution_description(
                    agent_id=self.agent_id,
                    current_tick=current_tick,
                    action=action,
                    target=target,
                    location=location,
                    importance=importance,
                    self_profile=self_profile,
                    target_profile=target_profile,
                    plan_note=plan_note
                )
                if isinstance(description_data, dict):
                    description = description_data.get("summary", "")
                    dialogue_history = description_data.get("history", [])
                    # Save dialogue history
                    if dialogue_history:
                        await state_plugin.add_dialogue(current_tick, dialogue_history)
                else:
                    description = description_data
                    dialogue_history = []
            else:
                # Use simple template for low importance actions
                self_name = self_profile.get('id', 'Unknown')
                description = f"{self_name} is doing {action} at {location}."
                dialogue_history = []
                logger.info(f"[{self.agent_id}][{current_tick}] Generated description using simple template (importance {importance})")

            # Add description to short-term memory (stored by tick, can be overwritten)
            await state_plugin.add_short_term_memory(description, tick=current_tick)
            # Simultaneously store the currently ongoing detailed description into state for frontend "current action" richer display
            await state_plugin.set_state('current_action', description)
            logger.info(f"[{self.agent_id}][{current_tick}] Generated and saved execution description")

            # If target participated in interaction, also add memory to target
            if target_participated:
                try:
                    controller = self._component.agent.controller
                    # Set occupied_by for participant, ensuring frontend can show occupied status
                    occupation_info = {
                        "occupier": self.agent_id,
                        "importance": importance,
                        "action": action
                    }
                    await controller.run_agent_method(
                        target,
                        "state",
                        "set_state",
                        "occupied_by",
                        occupation_info
                    )
                    # Set current_plan for participant (including location info), ensuring frontend shows correct location
                    target_plan = [action, time, self.agent_id, location, importance]
                    await controller.run_agent_method(
                        target,
                        "state",
                        "set_state",
                        "current_plan",
                        target_plan
                    )
                    # Add memory to participant
                    await controller.run_agent_method(
                        target,
                        "state",
                        "add_short_term_memory",
                        description,
                        current_tick
                    )
                    # Also set current action description for participant, ensuring frontend can see it
                    await controller.run_agent_method(
                        target,
                        "state",
                        "set_state",
                        "current_action",
                        description
                    )
                    # Also save dialogue history for participant
                    if dialogue_history:
                        await controller.run_agent_method(
                            target,
                            "state",
                            "add_dialogue",
                            current_tick,
                            dialogue_history
                        )
                    logger.info(f"[{self.agent_id}][{current_tick}] Added execution description and dialogue history to participant {target}'s state")
                except Exception as e:
                    logger.warning(f"[{self.agent_id}][{current_tick}] Unable to add state to participant {target}: {e}")

        except Exception as e:
            logger.error(f"[{self.agent_id}][{current_tick}] Error executing InvokePlugin: {e}")

    async def _is_occupied_by_others(self, tick: int, my_importance: int) -> bool:
        """
        Check if self is occupied by someone else with a higher priority
        """
        try:
            key = f"occupation:{tick}:{self.agent_id}"
            occupation_data = await self.redis.get(key)
            if not occupation_data:
                return False

            occupier = occupation_data.get("occupier")
            occupier_importance = occupation_data.get("importance", 0)

            if occupier == self.agent_id:
                return False

            if occupier_importance > my_importance:
                return True

            return False
        except Exception as e:
            logger.warning(f"[{self.agent_id}][{tick}] Failed to check occupation status: {e}")
            return False

    async def _occupy(self, tick: int, importance: int, action: str, location: str = "") -> bool:
        """
        Occupy self (only written if not already occupied by others)
        """
        try:
            import json
            key = f"occupation:{tick}:{self.agent_id}"
            existing = await self.redis.get(key)
            if existing:
                if isinstance(existing, str):
                    existing = json.loads(existing)
                occupier = existing.get("occupier")
                occupier_importance = existing.get("importance", 0)
                if occupier != self.agent_id and occupier_importance > importance:
                    logger.info(f"[{self.agent_id}][{tick}] Self-occupation failed: already occupied by {occupier} (importance {occupier_importance})")
                    return False
            await self.redis.set(key, json.dumps({
                "occupier": self.agent_id,
                "importance": importance,
                "action": action,
                "location": location,
            }))
            logger.debug(f"[{self.agent_id}][{tick}] Self occupied (importance {importance}, action: {action})")
            return True
        except Exception as e:
            logger.warning(f"[{self.agent_id}][{tick}] Failed to occupy self: {e}")
            return False

    async def _get_occupation(self, tick: int, target_id: str) -> dict:
        """
        Get occupation info for a target
        """
        try:
            key = f"occupation:{tick}:{target_id}"
            return await self.redis.get(key)
        except Exception as e:
            logger.warning(f"[{self.agent_id}][{tick}] Failed to get occupation info for target {target_id}: {e}")
            return None

    async def _try_occupy_target(self, tick: int, target_id: str, my_importance: int, action: str) -> bool:
        """
        Try to occupy a target
        """
        try:
            import json
            occupation_info = await self._get_occupation(tick, target_id)

            if not occupation_info:
                key = f"occupation:{tick}:{target_id}"
                await self.redis.set(key, json.dumps({
                    "occupier": self.agent_id,
                    "importance": my_importance,
                    "action": action
                }))
                logger.debug(f"[{self.agent_id}][{tick}] Successfully occupied target {target_id} (importance {my_importance}, action: {action})")
                return True

            if isinstance(occupation_info, str):
                occupation_info = json.loads(occupation_info)
            occupier = occupation_info.get("occupier")
            occupier_importance = occupation_info.get("importance", 0)

            if occupier == self.agent_id:
                return True

            if my_importance > occupier_importance:
                key = f"occupation:{tick}:{target_id}"
                await self.redis.set(key, json.dumps({
                    "occupier": self.agent_id,
                    "importance": my_importance,
                    "action": action
                }))
                logger.info(f"[{self.agent_id}][{tick}] Overwrote occupation of target {target_id} (self {my_importance} > {occupier} {occupier_importance}, action: {action})")
                return True

            logger.info(f"[{self.agent_id}][{tick}] Failed to occupy target {target_id} (self {my_importance} <= {occupier} {occupier_importance})")
            return False

        except Exception as e:
            logger.warning(f"[{self.agent_id}][{tick}] Failed to try occupying target {target_id}: {e}")
            return False

    async def _get_target_importance(self, target_agent_id: str, current_hour: int) -> int:
        """
        Get the importance score of the target character's task for the current hour
        """
        try:
            controller = self._component.agent.controller
            target_hourly_plans = await controller.run_agent_method(
                target_agent_id,
                "state",
                "get_hourly_plans"
            )

            if not target_hourly_plans:
                logger.debug(f"[{self.agent_id}] Target {target_agent_id} has no hourly plans")
                return None

            for plan in target_hourly_plans:
                if len(plan) >= 5 and plan[1] == current_hour:
                    return plan[4]

            logger.debug(f"[{self.agent_id}] Target {target_agent_id} has no plan for hour {current_hour}")
            return None

        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to get importance score for target {target_agent_id}: {e}")
            return None

    async def _get_agent_memory(self, agent_id: str) -> str:
        """Get agent's short-term and long-term memory"""
        try:
            controller = self._component.agent.controller
            short_memory = await controller.run_agent_method(agent_id, "state", "get_short_term_memory")
            long_memory = await controller.run_agent_method(agent_id, "state", "get_long_term_memory")
            
            memory_text = ""
            if long_memory:
                memory_text += "[Long-term Memory]\n"
                memory_text += "\n".join([f"- {m['content']}" for m in long_memory]) + "\n\n"
            
            if short_memory:
                memory_text += "[Recent Memory]\n"
                memory_text += "\n".join([f"- {m}" for m in short_memory[-5:]])
                
            if not memory_text:
                return "No memory"
            return memory_text.strip()
        except Exception as e:
            logger.warning(f"Failed to retrieve memory for {agent_id}: {e}")
            return "No memory"

    async def _generate_execution_description(
        self,
        agent_id: str,
        current_tick: int,
        action: str,
        target: str,
        location: str,
        importance: int,
        self_profile: Dict[str, Any],
        target_profile: Dict[str, Any] = None,
        plan_note: str = None
    ) -> Dict[str, Any]:
        """
        Simulate agent dialogue to generate execution description in English
        """
        default_res = {"summary": f"{self_profile.get('id', 'Unknown')} is executing {action} at {location}.", "history": []}
        if not self.model:
            return default_res

        participants = [agent_id]
        absent_people = []

        if target and target not in ["自己", "无", "None", ""]:
            if plan_note:
                absent_people.append(target)
            else:
                participants.append(target)

        if len(participants) == 1:
            if absent_people:
                absent_names = ", ".join(absent_people)
                summary = f"{self_profile.get('id', 'Unknown')} was about to {action} at {location}, but {absent_names} was busy and didn't show up."
                return {"summary": summary, "history": []}
            else:
                return default_res

        try:
            dialogue_history = []
            max_rounds = 10
            current_speaker_idx = 0

            for round_num in range(max_rounds):
                speaker_id = participants[current_speaker_idx]

                if speaker_id == agent_id:
                    speaker_profile = self_profile
                else:
                    speaker_profile = target_profile or {}

                speaker_name = speaker_profile.get('id', speaker_id)
                speaker_memory = await self._get_agent_memory(speaker_id)

                prompt = f"""You are playing the role of {speaker_name}.

Context Information:
- Current Scene: {action}
- Location: {location}
- Priority: {importance}/10"""

                if absent_people:
                    absent_names = ", ".join(absent_people)
                    prompt += f"\n- Absentee: {absent_names} is busy and couldn't come."

                if plan_note:
                    prompt += f"\n- Special Note: {plan_note}"

                prompt += f"""

{speaker_name}'s Profile:
- Personality: {speaker_profile.get('性格', 'Unknown')}
- Linguistic Style: {speaker_profile.get('语言风格', 'Unknown')}

{speaker_name}'s Memories and Experiences:
{speaker_memory}
"""
                other_participants = [p for p in participants if p != speaker_id]
                if other_participants:
                    prompt += "\nOther people present:"
                    for other_id in other_participants:
                        other_profile = self_profile if other_id == agent_id else (target_profile or {})
                        prompt += f"\n- {other_profile.get('id', other_id)}: {other_profile.get('性格', 'Unknown')}"

                prompt += "\n\nExisting Dialogue:\n"
                if dialogue_history:
                    prompt += "\n".join(dialogue_history)
                else:
                    prompt += "(The conversation just started)"

                prompt += f"""

Please speak one sentence (including action descriptions) as {speaker_name}. MUST reply in English.
Format: [Action] Dialogue
If you believe the conversation should naturally end, append [END] at the very end of your response.
Example: [Walking over with a smile] "Hello, the weather is quite nice today."
Example: [Nodding slightly] "Alright, let's proceed with this plan." [END]

[CRITICAL WARNING] If the current scene involves fatal events (like murder, severe injury, death), it MUST be explicitly reflected in the action description:
- If someone is killed, explicitly write "[Kills XX]" or "[XX dies]"
- If someone is severely injured, write "[XX falls to the ground severely injured]"
- Do not be vague; the system relies on this to judge character status.

{speaker_name} says:"""

                response = await self.model.chat(prompt)
                response = response.strip()

                # Clean [END] tag
                clean_response = response.replace("[END]", "").replace("END", "").strip()

                dialogue_line = f"{speaker_name}: {clean_response}"
                dialogue_history.append(dialogue_line)
                logger.info(f"[{current_tick}] Dialogue round {round_num+1}: {dialogue_line}")

                if "[END]" in response or "END" in response:
                    break

                current_speaker_idx = (current_speaker_idx + 1) % len(participants)

            summary_prompt = f"""Below is the dialogue involving {', '.join([p for p in participants])} at {location}:

{chr(10).join(dialogue_history)}

Please summarize this interaction in one paragraph (50-100 words) using a third-person narrative in English. Return ONLY the summary content, without any extra text.

[CRITICAL WARNING] If the following fatal events occurred, they MUST be explicitly stated in the summary:
- Death event: Must write "XX died" or "XX was killed", do not be vague.
- Severe injury: Must write "XX was severely injured".
- Departure event: Must write "XX left" or "XX disappeared".
These details are critical for system state judgment!"""

            summary = await self.model.chat(summary_prompt)
            summary = summary.strip()
            logger.info(f"[{current_tick}] Dialogue summary: {summary}")
            return {"summary": summary, "history": dialogue_history}

        except Exception as e:
            logger.error(f"[{agent_id}][{current_tick}] Failed to generate dialogue: {e}")
            return default_res

    @property
    def get_last_tick_actions(self) -> List[Dict[str, Any]]:
        """
        Return the action execution records of the last tick.

        Returns:
            List[Dict[str, Any]]: List of action execution records from the last tick.
        """
        pass