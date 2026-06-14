"""反思插件：每 tick 累积短期记忆，每 N tick 用 LLM 总结进长期记忆。

设计沿用红楼梦 BasicReflectPlugin 的「短期记忆 → 总结 → 长期记忆 → 清空」思路，
但适配 west_world 的「每 tick 现场决策」模型：没有 hourly_plans / LongTask / 每日周期，
所以不复用 sots 的 _should_replan / _check_long_task / _adjust_long_task（那些绑死在
每日 hourly-plan 模型上）。短期记忆由本插件从 state（plan_decision / feedback / location）
组装——invoke 保持专注，不需要改。复用 sots 的 BasicStatePlugin 记忆方法。
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agentkernel_distributed.mas.agent.base.plugin_base import ReflectPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

SUMMARY_PROMPT = """你是西部世界角色「{name}」的记忆整理助手。
下面是 ta 最近若干刻发生的事（短期记忆），请用一段话（80-150 字）以第三人称总结这段经历，
保留关键事件、地点变化和与他人的互动，去掉冗余。只返回总结正文，不要前缀。

短期记忆：
{memories}

请总结："""


def compose_tick_memory(decision: Optional[Dict[str, Any]], feedback: str, location: str, tick: int) -> str:
    """把这一刻的决策+反馈组装成一条第一人称短期记忆。"""
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
    """是否到了总结边界。与 sots 的 (current_tick+1)%12==0 同构。"""
    if interval <= 0:
        return False
    return (tick + 1) % interval == 0


def render_summary_prompt(name: str, memories: List[str]) -> str:
    joined = "\n".join(f"- {m}" for m in memories)
    return SUMMARY_PROMPT.format(name=name, memories=joined)


def _read_profile(agent) -> Dict[str, Any]:
    """通过 profile 组件读取档案（与 WestWorldPlanPlugin 相同的访问方式）。"""
    try:
        profile_plugin = agent.get_component("profile").get_plugin()
        return profile_plugin.get_agent_profile() or {}
    except Exception as exc:  # noqa: BLE001
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

        if should_summarize(current_tick, self.interval):
            await self._summarize(state_plugin, current_tick)

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
        except Exception as exc:  # noqa: BLE001
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
            # 留一个时间戳痕迹，便于事后核对
            await state_plugin.set_state("last_reflect", {
                "tick": current_tick,
                "timestamp": datetime.now().astimezone().isoformat(),
                "summarized": len(texts),
            })

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
