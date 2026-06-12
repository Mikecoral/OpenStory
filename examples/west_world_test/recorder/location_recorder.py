"""每地点一个的场景记录员：分块状态 + 被动调用接口。

LLM 只在 submit_action（裁决）和 tick_update（合并更新）两处被调用；
read/enter/leave 是纯文本操作。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from examples.west_world_test.worldmap.loader import Location
from . import prompts

logger = logging.getLogger(__name__)

RECENT_EVENTS_WINDOW = 10
READABLE_CHUNKS = {"static_facilities", "dynamic_objects", "present_agents", "recent_events"}
EMPTY_PRESENCE = "（无人）"
FALLBACK_JUDGEMENT = {
    "permission": True, "reason": "", "private_feedback": "",
    "broadcast_level": "none", "event_summary": "",
}


class LocationRecorder:
    def __init__(self, location: Location, llm: Any) -> None:
        self.location = location
        self.llm = llm
        visible = "；".join(f"{o['name']}（{o.get('note', '')}）" for o in location.visible_objects())
        self.chunks: Dict[str, Any] = {
            "static_facilities": f"{location.description.strip()} 设施与陈设：{visible}",
            "dynamic_objects": "暂无特别状态。",
            "present_agents": "、".join(location.default_occupants) or EMPTY_PRESENCE,
            "recent_events": [],
            "hidden_notes": "\n".join(f"{o['name']}: {o.get('secret', '')}" for o in location.hidden_objects()) or "（无）",
        }
        self._pending_actions: List[Dict[str, Any]] = []

    # ---- 被动读取（无 LLM） ----
    def read(self, agent_id: str, chunk_names: List[str]) -> Dict[str, Any]:
        wanted = [c for c in chunk_names if c in READABLE_CHUNKS]
        return {c: self.chunks[c] for c in wanted}

    def agent_enter(self, agent_id: str) -> str:
        present = self._present_set()
        present.add(agent_id)
        self.chunks["present_agents"] = "、".join(sorted(present))
        return self.chunks["static_facilities"]

    def agent_leave(self, agent_id: str) -> None:
        present = self._present_set()
        present.discard(agent_id)
        self.chunks["present_agents"] = "、".join(sorted(present)) or EMPTY_PRESENCE

    def _present_set(self) -> set[str]:
        raw = self.chunks["present_agents"]
        return set() if raw == EMPTY_PRESENCE else {x for x in raw.split("、") if x}

    # ---- 动作裁决（每动作一次 LLM） ----
    def submit_action(self, agent_id: str, action_text: str) -> Dict[str, Any]:
        prompt = prompts.render_judge(self.location.name, self.chunks, agent_id, action_text)
        judgement = self._chat_json(prompt, retries=1)
        if judgement is None:
            logger.warning("[%s] 裁决 JSON 解析失败，降级为允许/无反馈/不广播: %s", self.location.id, action_text)
            judgement = dict(FALLBACK_JUDGEMENT)
        record = {"agent_id": agent_id, "action": action_text, **judgement}
        self._pending_actions.append(record)
        return judgement

    def _chat_json(self, prompt: str, retries: int) -> Optional[Dict[str, Any]]:
        for _ in range(retries + 1):
            raw = self.llm.chat(prompt)
            try:
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("```")[1].lstrip("json").strip()
                return json.loads(text)
            except (json.JSONDecodeError, IndexError):
                continue
        return None

    # ---- tick 末结算（每地点每 tick 至多一次 LLM） ----
    def tick_update(self, tick: int) -> None:
        if not self._pending_actions:
            return
        actions_log = self._pending_actions
        self._pending_actions = []
        prompt = prompts.render_update(self.location.name, tick, self.chunks, actions_log)
        update = self._chat_json(prompt, retries=1)
        if update is None:
            logger.error("[%s] tick %s 更新失败，保留旧状态块", self.location.id, tick)
            return
        for key in ("dynamic_objects", "present_agents"):
            if isinstance(update.get(key), str) and update[key].strip():
                self.chunks[key] = update[key]
        events = update.get("recent_events")
        if isinstance(events, list):
            self.chunks["recent_events"] = [str(e) for e in events][-RECENT_EVENTS_WINDOW:]
