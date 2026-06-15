"""LLM 自由决策 plan：profile 中的 narrative_loop 作为软引导（行为倾向，非脚本）。"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict

from agentkernel_distributed.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_distributed.toolkit.logger import get_logger

logger = get_logger(__name__)

PLAN_PROMPT = """你是西部世界中的角色「{name}」。
性格：{personality}
你的日常习惯（这是你的本能倾向，但你可以因为眼前发生的事偏离它）：{narrative_loop}

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


def render_plan_prompt(profile: Dict[str, Any], percept: Dict[str, Any], feedback: str, tick: int) -> str:
    return PLAN_PROMPT.format(
        name=profile.get("name", profile.get("姓名", "")),
        personality=profile.get("persona", profile.get("性格", "")),
        narrative_loop=profile.get("narrative_loop", ""),
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
                recipient for recipient in recipients
                if isinstance(recipient, str) and recipient.strip()
            ] if isinstance(recipients, list) else []
            return decision
    except (json.JSONDecodeError, IndexError):
        pass
    return {"action": "stay", "target": "", "detail": "", "recipient_ids": [], "next_read": []}


async def _read_profile(agent) -> Dict[str, Any]:
    """通过 profile 组件读取 agent 档案（与 sots BasicPlanPlugin 相同的访问方式）。"""
    try:
        profile_component = agent.get_component("profile")
        profile_plugin = profile_component.get_plugin()
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

        state_component = self.agent.get_component("state")
        state_plugin = state_component.get_plugin()

        # 读感知与反馈
        percept = await state_plugin.get_state("percept") or {}
        feedback = await state_plugin.get_state("feedback") or ""

        # 读 profile（通过 profile 组件的 get_agent_profile()）
        profile = await _read_profile(self.agent)

        prompt = render_plan_prompt(profile, percept, feedback, current_tick)

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

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
