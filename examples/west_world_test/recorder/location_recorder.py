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
            "present_agents": "、".join(location.default_occupants) or "（无人）",
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
        self.chunks["present_agents"] = "、".join(sorted(present)) or "（无人）"

    def _present_set(self) -> set:
        raw = self.chunks["present_agents"]
        return set() if raw == "（无人）" else {x for x in raw.split("、") if x}
