"""Reflect plugin: summarizes memory, checks survival, adjusts/replans tasks.

Generic port of story_of_the_stone's BasicReflectPlugin — the life-status and
adjustment prompts no longer reference 红楼梦; they rely on generic memory text.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

PROJECT_PATH = Path(__file__).resolve().parents[3]
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.agent.base.plugin_base import ReflectPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)


class BasicReflectPlugin(ReflectPlugin):
    """Per-tick survival/replan checks plus full daily reflection every 12 ticks."""

    def __init__(self) -> None:
        super().__init__()
        self.model = None
        self.agent_id = None

    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        logger.info("[%s][N/A] BasicReflectPlugin initialization completed", self.agent_id)

    async def execute(self, current_tick: int) -> None:
        if await self._check_life_status_lightweight(current_tick):
            return

        current_hour = current_tick % 12
        if current_hour < 11:
            should, reason = await self._should_replan(current_tick)
            if should:
                await self._replan_remaining(current_tick, reason)

        if (current_tick + 1) % 12 == 0:
            try:
                await self._summarize_short_term_memory(current_tick)
                if await self._check_life_status(current_tick):
                    return
                await self._check_long_task_completion(current_tick)
                await self._adjust_long_task(current_tick)
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s][%s] Error in full reflection: %s", self.agent_id, current_tick, exc)

    # ── Memory summary ──────────────────────────────────────────────
    async def _summarize_short_term_memory(self, current_tick: int) -> None:
        state = self._component.agent.get_component("state").get_plugin()
        short_memories = await state.get_short_term_memory()
        if not short_memories:
            return
        if not self.model:
            return
        memories_text = "\n".join(f"{m.get('tick', i)}: {m.get('content', m)}" for i, m in enumerate(short_memories))
        prompt = f"""你是一个智能体的记忆总结助手。请简明扼要地总结以下短期记忆并提取关键信息。

短期记忆列表：
{memories_text}

要求：
1. 提取最重要的事件和信息
2. 保持时间顺序
3. 去除冗余细节
4. 总结长度100-200字
5. 仅返回总结内容
6. 必须使用中文输出

请总结："""
        summary = (await self.model.chat(prompt)).strip()
        await state.add_long_term_memory(summary)
        await state.clear_short_term_memory()

    # ── Long task completion ────────────────────────────────────────
    async def _check_long_task_completion(self, current_tick: int) -> None:
        state = self._component.agent.get_component("state").get_plugin()
        long_task = await state.get_long_task()
        if not long_task or not self.model:
            return
        short = await state.get_short_term_memory()
        long = await state.get_long_term_memory()
        short_ctx = "\n".join(f"- {m.get('content', m)}" for m in short) if short else "(无)"
        long_ctx = "\n".join(f"- {m['content']}" for m in long) if long else "(无)"
        prompt = f"""你是任务完成度判断助手。请判断长期任务是否已大致完成。

当前长期任务：
{long_task}

短期记忆：
{short_ctx}

长期记忆：
{long_ctx}

要求：
1. 只要核心目标已达成即视为完成
2. 仅返回"已完成"或"未完成"

请判断："""
        result = (await self.model.chat(prompt)).strip()
        if "已完成" in result or "Completed" in result:
            summary_prompt = f"""请用50-100字总结以下已完成的长期任务的结果。仅返回总结，必须使用中文。

任务：{long_task}
短期记忆：{short_ctx}
长期记忆：{long_ctx}"""
            summary = (await self.model.chat(summary_prompt)).strip()
            await state.add_long_term_memory(f"[已完成任务] {summary}")
            await state.set_long_task(None)

    # ── Life status ─────────────────────────────────────────────────
    async def _check_life_status_lightweight(self, current_tick: int) -> bool:
        if not self.model:
            return False
        state = self._component.agent.get_component("state").get_plugin()
        short = await state.get_short_term_memory()
        if not short:
            return False
        recent = short[-5:] if len(short) > 5 else short
        memories_text = "\n".join(f"- {m.get('tick', '?')}: {m.get('content', m)}" for m in recent)
        return await self._evaluate_life_status(current_tick, memories_text, state)

    async def _check_life_status(self, current_tick: int) -> bool:
        if not self.model:
            return False
        state = self._component.agent.get_component("state").get_plugin()
        short = await state.get_short_term_memory()
        long = await state.get_long_term_memory()
        if not short and not long:
            return False
        ctx = ""
        if short:
            ctx += "近期记忆：\n" + "\n".join(f"- {m.get('content', m)}" for m in short) + "\n"
        if long:
            ctx += "历史记忆：\n" + "\n".join(f"- {m['content']}" for m in long)
        return await self._evaluate_life_status(current_tick, ctx, state)

    async def _evaluate_life_status(self, current_tick: int, memories_text: str, state) -> bool:
        prompt = f"""你是一个智能体生存状态分析助手。请根据以下记忆判断角色当前是否处于"无法继续参与后续行动"的状态。

这些状态包括但不限于：
1. 死亡（自杀、被杀、病死、遇害等）
2. 完全消失/失踪
3. 永久离开/远走且不再回来
4. 被长期囚禁/拘留
5. 记忆中出现 [END] 标记表示离场

当前角色：{self.agent_id}

记忆：
{memories_text}

[判断规则]：
1. 若记忆明确提到"{self.agent_id}死了/被杀/遇害/离世"，必须判定为"已离场"
2. 若提到某人"杀了{self.agent_id}"，必须判定为"已离场"
3. 若角色仍在场（仅休息、受伤未死、情绪低落），判定为"活跃"
4. 只有明确发生离场事件时才判定为"已离场"
5. 返回格式：判断结果 | 离场原因（包含核心因果，如"因为..."）
6. 必须使用中文

返回示例：已离场 | 角色因卷入冲突而身亡
返回示例：活跃 |

请分析并返回："""
        result = (await self.model.chat(prompt)).strip()
        if "活跃" in result or "Active" in result:
            return False
        if "已离场" in result or "Departed" in result:
            parts = result.split("|")
            reason = parts[1].strip() if len(parts) > 1 else "发生不可逆的离场事件"
            await state.set_active_status(False, reason)
            await state.add_long_term_memory(f"[最终结局] {reason}")
            await self._broadcast_departure(reason)
            return True
        return False

    async def _broadcast_departure(self, reason: str) -> None:
        try:
            controller = self._component.agent.controller
            all_ids = await controller.get_all_agent_ids()
            msg = f"[噩耗] {self.agent_id} 已离场。原因：{reason}"
            for tid in all_ids:
                if tid != self.agent_id:
                    await controller.run_agent_method(tid, "state", "add_long_term_memory", msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Failed to broadcast departure: %s", self.agent_id, exc)

    # ── Long task adjustment ────────────────────────────────────────
    async def _adjust_long_task(self, current_tick: int) -> None:
        state = self._component.agent.get_component("state").get_plugin()
        long_task = await state.get_long_task()
        if not long_task or not self.model:
            return
        short = await state.get_short_term_memory()
        long = await state.get_long_term_memory()
        short_ctx = "\n".join(f"- {m.get('content', m)}" for m in short) if short else "(无)"
        long_ctx = "\n".join(f"- {m['content']}" for m in long) if long else "(无)"
        prompt = f"""你是智能体的战略规划助手。请判断当前长期任务是否需要调整。

当前长期任务：
{long_task}

近期记忆：
{short_ctx}

历史记忆：
{long_ctx}

要求：
1. 若环境发生重大变化或目标偏离，建议调整
2. 不需要调整则仅返回"无需调整"
3. 需要调整则返回调整后的新任务全文
4. 仅返回结论，必须使用中文

请判断："""
        result = (await self.model.chat(prompt)).strip()
        if "无需调整" in result or "No Adjustment" in result:
            return
        await state.set_long_task(result)
        await state.add_long_term_memory(f"[任务调整] 由于环境变化，长期任务调整为：{result}")
        current_day = (current_tick // 12) + 1
        await state.add_long_task_adjustment(tick=current_tick, from_day=current_day + 1)

    # ── Replan ──────────────────────────────────────────────────────
    async def _should_replan(self, current_tick: int) -> Tuple[bool, str]:
        if not self.model:
            return (False, "no model")
        state = self._component.agent.get_component("state").get_plugin()
        long_task = await state.get_long_task()
        if not long_task:
            return (False, "无长期任务")
        short = await state.get_short_term_memory()
        if not short:
            return (False, "无短期记忆")
        last = short[-1].get("content", str(short[-1]))
        current_hour = current_tick % 12
        prompt = f"""你是计划评估助手。请根据上一时段事件判断是否需要重新规划剩余时间。

当前长期任务：{long_task}
上一时段事件：{last}
当前时段：第{current_hour}个时段

判断标准：
1. 上一时段是否发生重大变化（重要角色离场、任务完成、突发事件）
2. 当前任务是否已失效或偏离

返回（仅返回结论）：
- "需要重新规划 | 原因"
- "无需规划 | 原因"
"""
        result = (await self.model.chat(prompt)).strip()
        if "需要重新规划" in result:
            parts = result.split("|")
            return (True, parts[1].strip() if len(parts) > 1 else "发生重大变化")
        return (False, result)

    async def _replan_remaining(self, current_tick: int, reason: str) -> None:
        try:
            state = self._component.agent.get_component("state").get_plugin()
            profile = self._component.agent.get_component("profile").get_plugin().get_agent_profile()
            long_task = await state.get_long_task()
            current_hour = current_tick % 12
            current_day = (current_tick // 12) + 1
            plan_component = self._component.agent.get_component("plan")
            if not plan_component:
                return
            plan_plugin = plan_component.get_plugin()
            await plan_plugin.replan_remaining_plans(
                agent_id=self.agent_id, current_tick=current_tick, profile=profile,
                long_task=long_task, start_hour=current_hour + 1,
            )
            await state.add_replan_event(
                tick=current_tick, reason=reason, day=current_day, from_hour=current_hour + 1
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s][%s] Error replanning: %s", self.agent_id, current_tick, exc)
