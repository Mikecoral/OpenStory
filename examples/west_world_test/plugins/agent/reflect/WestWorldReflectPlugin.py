"""反思插件：每 tick 累积短期记忆，每 N tick 总结进长期记忆，天边界重置 host 位置。

每日重置（host only）在天边界 _summarize 之后执行，确保下一 tick 的 perceive
从 loop_origin 出发，与 plan 的天首 daily_loop 复制时序对齐。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from agentkernel_distributed.mas.agent.base.plugin_base import ReflectPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

SUMMARY_PROMPT = """你是西部世界角色「{name}」的记忆整理助手。
下面是 ta 最近若干刻发生的事（短期记忆），请用一段话（80-150 字）以第三人称总结这段经历，
保留关键事件、地点变化和与他人的互动，去掉冗余。只返回总结正文，不要前缀。

短期记忆：
{memories}

请总结："""

REPLAN_JUDGE_PROMPT = """你是西部世界角色「{name}」。你今天剩下的计划是：{remaining_loop}
刚刚这一刻发生了：{this_tick_event}（你的动作 + 结果 + 收到的消息）

判断：是否发生了重大变故，需要改写你今天剩余的计划？
（值得改的：被卷入冲突/他人剧情、关键目标失败或达成、出现必须应对的人或事。
 不值得改的：日常对话、环境细节、情绪波动。）

只输出 JSON：{{"replan": true/false, "reason": "<简短>"}}"""


def compose_tick_memory(decision: Optional[Dict[str, Any]], feedback: str, location: str, tick: int) -> str:
    decision = decision or {}
    action = decision.get("action", "stay")
    if action == "move":
        body = f"我前往了 {decision.get('target', '')}"
    elif action == "do":
        body = decision.get("detail") or "我做了一件事"
    else:
        body = "我在原地停留"
    line = f"（第{tick}刻@{location}）{body}"
    if feedback:
        line += f"。结果：{feedback}"
    return line


def should_summarize(tick: int, interval: int) -> bool:
    if interval <= 0:
        return False
    return (tick + 1) % interval == 0


def render_summary_prompt(name: str, memories: List[str]) -> str:
    joined = "\n".join(f"- {m}" for m in memories)
    return SUMMARY_PROMPT.format(name=name, memories=joined)


def _read_profile(agent) -> Dict[str, Any]:
    try:
        profile_plugin = agent.get_component("profile").get_plugin()
        return profile_plugin.get_agent_profile() or {}
    except Exception as exc:
        logger.warning("[%s] 读取 profile 失败: %s", getattr(agent, "agent_id", "?"), exc)
        return {}


class WestWorldReflectPlugin(ReflectPlugin):
    def __init__(self, interval: Optional[int] = None, **_: Any) -> None:
        super().__init__()
        self.model = None
        self.interval = interval if interval else int(os.environ.get("WW_REFLECT_INTERVAL", "6"))

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        if self.agent is None:
            return
        if self.model is None:
            self.model = self._component.agent.model

        state_plugin = self.agent.get_component("state").get_plugin()

        decision = await state_plugin.get_state("plan_decision") or {}
        feedback = await state_plugin.get_state("feedback") or ""
        location = await state_plugin.get_state("location") or ""

        memory = compose_tick_memory(decision, feedback, location, current_tick)
        await state_plugin.add_short_term_memory(memory, current_tick)

        # Replan 判断（WW_ENABLE_REPLAN=true 且非最后一段）
        if (
            os.environ.get("WW_ENABLE_REPLAN", "").lower() in ("true", "1")
            and self.model is not None
            and current_tick % 6 < 5
        ):
            should_rp, reason = await self._should_replan(state_plugin, current_tick, decision, feedback)
            if should_rp:
                try:
                    plan_plugin = self.agent.get_component("plan").get_plugin()
                    await plan_plugin.replan_remaining(current_tick, reason, state_plugin)
                except Exception as exc:
                    logger.warning("[%s] replan 调用失败: %s", self.agent.agent_id, exc)

        # 天边界：总结短期记忆 + host 每日重置
        if should_summarize(current_tick, self.interval):
            await self._summarize(state_plugin, current_tick)
            await self._day_reset(state_plugin, current_tick)

    async def _summarize(self, state_plugin, current_tick: int) -> None:
        memories = await state_plugin.get_short_term_memory()
        if not memories or self.model is None:
            return

        profile = _read_profile(self.agent)
        name = profile.get("name") or profile.get("姓名") or self.agent.agent_id
        texts = [m.get("content", str(m)) for m in memories]
        prompt = render_summary_prompt(name, texts)

        request_id = f"req_{uuid.uuid4().hex}"
        started = time.perf_counter()
        try:
            summary = await self.model.chat(
                prompt,
                timeout=int(os.environ.get("WW_LLM_TIMEOUT_SECONDS", "120")),
                max_attempts=int(os.environ.get("WW_LLM_MAX_ATTEMPTS", "3")),
                _trace_context={
                    "request_id": request_id,
                    "request_type": "agent_reflect",
                    "tick": current_tick,
                    "agent_id": self.agent.agent_id,
                },
            )
        except Exception as exc:
            logger.warning("[%s] reflect LLM 总结失败，保留短期记忆: %s", self.agent.agent_id, exc)
            return

        summary_text = summary if isinstance(summary, str) else str(summary)
        if summary_text.strip():
            await state_plugin.add_long_term_memory(summary_text.strip())
            await state_plugin.clear_short_term_memory()
            logger.info(
                "[%s] tick %s 反思总结(%s 条→长期记忆, 耗时%sms)",
                self.agent.agent_id, current_tick, len(texts),
                round((time.perf_counter() - started) * 1000, 1),
            )
            await state_plugin.set_state("last_reflect", {
                "tick": current_tick,
                "timestamp": datetime.now().astimezone().isoformat(),
                "summarized": len(texts),
            })

    async def _should_replan(
        self,
        state_plugin,
        current_tick: int,
        decision: Dict[str, Any],
        feedback: str,
    ) -> Tuple[bool, str]:
        """调 LLM 判断是否需要 replan，返回 (should_replan, reason)。"""
        daily_loop: List[Dict] = await state_plugin.get_state("daily_loop") or []
        seg_idx = current_tick % 6
        remaining = daily_loop[seg_idx + 1:] if len(daily_loop) > seg_idx + 1 else []
        if not remaining:
            return False, ""

        action = decision.get("action", "stay")
        detail = decision.get("detail", "")
        this_event = f"动作={action}"
        if detail:
            this_event += f"：{detail}"
        if feedback:
            this_event += f"，反馈：{feedback}"

        profile = _read_profile(self.agent)
        name = profile.get("name", profile.get("姓名", self.agent.agent_id))

        prompt = REPLAN_JUDGE_PROMPT.format(
            name=name,
            remaining_loop=json.dumps(remaining, ensure_ascii=False),
            this_tick_event=this_event,
        )

        try:
            raw = await self.model.chat(
                prompt,
                timeout=60,
                max_attempts=2,
                _trace_context={
                    "request_type": "agent_replan_judge",
                    "tick": current_tick,
                    "agent_id": self.agent.agent_id,
                },
            )
            text = raw.strip() if isinstance(raw, str) else str(raw)
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            result = json.loads(text)
            return bool(result.get("replan", False)), str(result.get("reason", ""))
        except Exception as exc:
            logger.warning("[%s] _should_replan 解析失败: %s", self.agent.agent_id, exc)
            return False, ""

    async def _day_reset(self, state_plugin, current_tick: int) -> None:
        """每日重置（host only）：teleport 回 loop_origin，清空短期记忆已在 _summarize 完成。"""
        profile = _read_profile(self.agent)
        if profile.get("agent_type") != "host":
            return

        loop_origin = await state_plugin.get_state("loop_origin")
        if not loop_origin:
            return

        location = await state_plugin.get_state("location") or ""
        if location == loop_origin:
            return

        controller = self.agent.controller
        await self._scene_call(controller, location, "agent_leave", self.agent.agent_id)
        await self._scene_call(controller, loop_origin, "agent_enter", self.agent.agent_id)
        await self._scene_call(
            controller, location, "record_event",
            f"{self.agent.agent_id} 结束了今天，回到了起点 {loop_origin}。",
        )
        await self._scene_call(
            controller, loop_origin, "relocate_holdings",
            self.agent.agent_id, location, loop_origin, current_tick,
        )
        await state_plugin.set_state("location", loop_origin)
        logger.info(
            "[%s] tick %s 每日重置: %s → %s",
            self.agent.agent_id, current_tick, location, loop_origin,
        )

    async def _scene_call(self, controller, location_id: str, method: str, *args) -> Any:
        try:
            return await controller.run_environment(f"scene_{location_id}", method, *args)
        except Exception as exc:
            logger.warning("scene_%s.%s 调用失败: %s", location_id, method, exc)
            return None

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
