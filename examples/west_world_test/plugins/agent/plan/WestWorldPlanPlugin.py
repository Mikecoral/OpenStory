"""LLM 自由决策 plan：narrative_loop 作软引导，daily_loop 给结构化骨架。"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

SEGMENT_NAMES = ["清晨", "上午", "正午", "下午", "傍晚", "夜晚"]

PLAN_PROMPT = """你是西部世界中的角色「{name}」。
性格：{personality}
你的日常习惯（本能倾向，可因眼前事偏离）：{narrative_loop}

## 你今天的计划
此刻是{segment}，你本应在「{loop_location}」{loop_intent}。
- 若你不在那里：**应当立刻用 move 前进**（一步一格）。日常闲聊、观察周围不是留下的理由——你有地方要去。只有正面临人身安全威胁、或他人强行阻拦你，才可以暂缓移动。
- 若你已在那里：do 你这一刻具体在做什么。
- 若你已完成今天的任务且暂时没有更紧迫的计划：在当前位置 do 合适的事。

## 当前情况（tick {tick}）
你在：{location}。{here_description}
场景信息：{scene}
收到的消息：{messages}
上一个动作的结果：{feedback}
可以前往的相邻地点：{neighbors}

## 决定你这一刻要做什么
- 继续待在这里做某件事：action 用 "do"，detail 写具体动作（一句话，第一人称行为描述）。do 必须能在当前位置内完成，严禁描述离开、前往、进入或到达其他地点
- 移动到相邻地点：action 用 "move"，target 填地点 id
- 什么都不做：action 用 "stay"
- 如果要对在场角色说话、下命令或交谈，仍使用 do，并把接收者的角色 id 写入 recipient_ids；没有明确接收者则填空数组
- next_read 填你下一刻想了解的场景信息块，可选项: ["present_agents", "recent_events", "dynamic_objects", "static_facilities"]

只输出 JSON：{{"action": "do|move|stay", "target": "", "detail": "", "recipient_ids": [], "next_read": []}}
"""

REPLAN_PROMPT = """你是西部世界角色「{name}」。
今天发生了意外：{reason}
你今天已完成的时段（不要改动）：{completed}
请为今天剩余的 {n} 个时段（{remaining_names}）重新规划，以适应新情况。
地点必须使用以下合法地点 id 之一（你已知的地点）：{known_locations}
每段格式：{{"segment": "时段名", "location": "地点id", "intent": "这个时段打算做什么（一句话）"}}
只输出 JSON 数组（{n} 条），不要其他内容："""


def render_plan_prompt(
    profile: Dict[str, Any],
    percept: Dict[str, Any],
    feedback: str,
    tick: int,
    loop_segment: Optional[Dict[str, Any]] = None,
) -> str:
    seg = loop_segment or {}
    return PLAN_PROMPT.format(
        name=profile.get("name", profile.get("姓名", "")),
        personality=profile.get("persona", profile.get("性格", "")),
        narrative_loop=profile.get("narrative_loop", ""),
        segment=seg.get("segment", SEGMENT_NAMES[tick % 6]),
        loop_location=seg.get("location", "（未知）"),
        loop_intent=seg.get("intent", "按日常行事"),
        tick=tick,
        location=percept.get("location", ""),
        here_description=percept.get("here_description", ""),
        scene=json.dumps(percept.get("scene", {}), ensure_ascii=False),
        messages=json.dumps(percept.get("messages", []), ensure_ascii=False),
        feedback=feedback or "（无）",
        neighbors=", ".join(percept.get("neighbors", [])),
    )


def parse_decision(raw: str) -> Dict[str, Any]:
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        decision = json.loads(text)
        if decision.get("action") in ("do", "move", "stay"):
            recipients = decision.get("recipient_ids", [])
            decision["recipient_ids"] = [
                r for r in recipients
                if isinstance(r, str) and r.strip()
            ] if isinstance(recipients, list) else []
            return decision
    except (json.JSONDecodeError, IndexError):
        pass
    return {"action": "stay", "target": "", "detail": "", "recipient_ids": [], "next_read": []}


async def _read_profile(agent) -> Dict[str, Any]:
    try:
        profile_plugin = agent.get_component("profile").get_plugin()
        return profile_plugin.get_agent_profile() or {}
    except Exception as exc:
        logger.warning("[%s] 读取 profile 失败: %s", getattr(agent, "agent_id", "?"), exc)
        return {}


class WestWorldPlanPlugin(PlanPlugin):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.model = None

    async def init(self) -> None:
        pass

    async def execute(self, current_tick: int) -> None:
        if self.agent is None:
            return
        if self.model is None:
            self.model = self._component.agent.model

        state_plugin = self.agent.get_component("state").get_plugin()
        profile = await _read_profile(self.agent)

        # 天首：复制固定 loop 表到 state，初始化 loop_origin
        if current_tick % 6 == 0:
            if not await state_plugin.get_state("loop_origin"):
                origin = await state_plugin.get_state("location") or ""
                await state_plugin.set_state("loop_origin", origin)
            await state_plugin.set_state("current_day", current_tick // 6)
            profile_loop = profile.get("daily_loop", [])
            if profile_loop:
                await state_plugin.set_state("daily_loop", profile_loop)

        # 读当前段
        daily_loop: List[Dict] = await state_plugin.get_state("daily_loop") or []
        seg_idx = current_tick % 6
        loop_segment = daily_loop[seg_idx] if len(daily_loop) > seg_idx else {}

        percept = await state_plugin.get_state("percept") or {}
        feedback = await state_plugin.get_state("feedback") or ""

        prompt = render_plan_prompt(profile, percept, feedback, current_tick, loop_segment)

        raw = ""
        error = ""
        request_id = f"req_{uuid.uuid4().hex}"
        started = time.perf_counter()
        if self.model:
            try:
                raw = await self.model.chat(
                    prompt,
                    timeout=int(os.environ.get("WW_LLM_TIMEOUT_SECONDS", "120")),
                    max_attempts=int(os.environ.get("WW_LLM_MAX_ATTEMPTS", "3")),
                    _trace_context={
                        "request_id": request_id,
                        "request_type": "agent_plan",
                        "tick": current_tick,
                        "agent_id": self.agent.agent_id,
                        "location_id": percept.get("location", ""),
                    },
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                logger.warning("[%s] plan LLM 调用失败，降级为 stay: %s", self.agent.agent_id, exc)

        raw_text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, default=str)
        decision = parse_decision(raw_text)
        await state_plugin.set_state("plan_decision", decision)
        await state_plugin.set_state("next_read", decision.get("next_read") or [])
        await state_plugin.set_state("plan_trace", {
            "timestamp": datetime.now().astimezone().isoformat(),
            "request_id": request_id,
            "call_type": "agent_plan",
            "prompt": prompt,
            "raw_response": raw,
            "error": error,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "parsed_decision": decision,
            "parse_fallback": decision["action"] == "stay" and raw_text.strip() not in (
                '{"action": "stay", "target": "", "detail": "", "next_read": []}', ""
            ),
        })
        logger.info("[%s] tick %s 决策: %s", self.agent.agent_id, current_tick,
                    json.dumps(decision, ensure_ascii=False))

    async def replan_remaining(
        self, current_tick: int, reason: str, state_plugin
    ) -> bool:
        """重写当天 (current_segment+1)..5 的剩余段，返回是否成功。"""
        daily_loop: List[Dict] = await state_plugin.get_state("daily_loop") or []
        if not daily_loop or len(daily_loop) < 6:
            return False

        seg_idx = current_tick % 6
        if seg_idx >= 5:
            return False

        if self.model is None:
            self.model = self._component.agent.model
        if self.model is None:
            return False

        profile = await _read_profile(self.agent)
        name = profile.get("name", profile.get("姓名", self.agent.agent_id))
        known_map: List[str] = await state_plugin.get_state("known_map") or []
        remaining_count = 5 - seg_idx
        remaining_names = "、".join(SEGMENT_NAMES[seg_idx + 1:])

        prompt = REPLAN_PROMPT.format(
            name=name,
            reason=reason,
            completed=json.dumps(daily_loop[: seg_idx + 1], ensure_ascii=False),
            n=remaining_count,
            remaining_names=remaining_names,
            known_locations="、".join(known_map) if known_map else "（未知）",
        )

        try:
            raw = await self.model.chat(
                prompt,
                timeout=60,
                max_attempts=2,
                _trace_context={
                    "request_type": "agent_replan",
                    "tick": current_tick,
                    "agent_id": self.agent.agent_id,
                },
            )
            text = raw.strip() if isinstance(raw, str) else str(raw)
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            new_segs = json.loads(text)
            if isinstance(new_segs, list) and len(new_segs) == remaining_count:
                new_loop = list(daily_loop[: seg_idx + 1]) + new_segs
                await state_plugin.set_state("daily_loop", new_loop)
                replan_log: List[Dict] = await state_plugin.get_state("replan_log") or []
                replan_log.append({
                    "day": await state_plugin.get_state("current_day") or 0,
                    "tick": current_tick,
                    "from_segment": seg_idx + 1,
                    "reason": reason,
                })
                await state_plugin.set_state("replan_log", replan_log)
                logger.info(
                    "[%s] tick %s replan：从第 %s 段开始改写，原因：%s",
                    self.agent.agent_id, current_tick, seg_idx + 1, reason,
                )
                return True
        except Exception as exc:
            logger.warning("[%s] replan_remaining 失败: %s", self.agent.agent_id, exc)
        return False

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
