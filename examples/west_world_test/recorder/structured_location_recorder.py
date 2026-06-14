"""Location Recorder where LLM proposes free-form object patches validated before applying."""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from examples.west_world_test.worldmap.loader import Location
from .location_recorder import (
    FALLBACK_JUDGEMENT,
    RECENT_EVENTS_WINDOW,
    LocationRecorder,
)

# Fields that belong to the object schema itself and must not be overwritten via patch.
_META_FIELDS = {"object_id", "name", "hidden"}

_PROPOSAL_PROMPT = """你是地点「{location_name}」的动作解析器与场景裁判。
把角色的自由文本动作转换成对【可见对象】的字段更新（patch），并判断动作是否触及隐藏秘密。你不能凭空创造新对象。

可见对象（patch 只能使用这些 object_id）：
{objects}

可见对象当前事实：
{facts}

隐藏秘密（仅你可见，严禁直接照抄给角色；隐藏物件不得出现在 patches 中）：
{hidden_secrets}

角色：{agent_id}
动作：{action_text}

规则：
- patches 只能针对【可见对象】，每条包含 object_id 以及要修改的字段；隐藏物件严禁出现在 patches 中。
- 可以更新任意字段（state、quantity、container 等），字段值为简短中文字符串（不超过 100 字）。
- state 是主要状态描述，优先用它记录对象当前状况。
- held_by 只能设为行动者 id（{agent_id}）或空字符串（表示放下）。
- 只更新确实发生变化的字段，未变化的字段不要出现在 patch 中。
- 动作完全不涉及任何可见对象时 patches 为空数组。
- 秘密揭示由你裁决：仅当动作确实触及某个隐藏秘密时，在 private_feedback 中按动作触及的深浅渐进式透露其内容（不要照抄原文，浅尝辄止则只给模糊线索，深入查看才完整揭示）；动作未触及秘密时，private_feedback 只描述动作的直接结果，绝不提及任何秘密。
- 所有字段值必须使用中文，严禁使用英文。

只输出 JSON：
{{"permission": true, "reason": "", "private_feedback": "...", "broadcast_level": "none|location",
"event_summary": "", "patches": [{{"object_id": "obj_0", "state": "新状态"}}]}}
"""


class StructuredLocationRecorder(LocationRecorder):
    """Formal-simulation Recorder: LLM proposes free-form object patches, reducer applies atomically."""

    def __init__(self, location: Location, llm: Any) -> None:
        super().__init__(location, llm)
        self.object_facts: Dict[str, Dict[str, Any]] = {
            f"obj_{index}": {
                "object_id": f"obj_{index}",
                "name": item["name"],
                "state": item.get("note", "状态正常"),
                "held_by": "",
                "hidden": bool(item.get("hidden")),
            }
            for index, item in enumerate(location.objects)
        }
        self.fact_ledger: List[Dict[str, Any]] = []
        self._render_dynamic_objects()

    def submit_action(self, agent_id: str, action_text: str, tick: Optional[int] = None) -> Dict[str, Any]:
        # Only expose non-hidden objects to the LLM
        visible_objects = [
            {"object_id": row["object_id"], "name": row["name"]}
            for row in self.object_facts.values()
            if not row["hidden"]
        ]
        visible_facts = {
            oid: {k: v for k, v in row.items() if k != "hidden"}
            for oid, row in self.object_facts.items()
            if not row["hidden"]
        }
        prompt = _PROPOSAL_PROMPT.format(
            location_name=self.location.name,
            objects=json.dumps(visible_objects, ensure_ascii=False),
            facts=json.dumps(visible_facts, ensure_ascii=False),
            hidden_secrets=self.chunks.get("hidden_notes") or "（无）",
            agent_id=agent_id,
            action_text=action_text,
        )
        proposal = self._chat_json(
            prompt,
            retries=1,
            call_type="structured_action_parse",
            metadata={"agent_id": agent_id, "action_text": action_text, "tick": tick},
        )
        if proposal is None:
            return {**FALLBACK_JUDGEMENT, "permission": False, "reason": "动作解析失败"}
        try:
            patches = self._validate_patches(proposal.get("patches", []), agent_id)
        except ValueError as exc:
            return {**FALLBACK_JUDGEMENT, "permission": False, "reason": str(exc)}
        if not proposal.get("permission", False):
            patches = []
        before = copy.deepcopy(self.object_facts)
        self._apply_patches(patches)
        judgement = {
            key: proposal.get(key, FALLBACK_JUDGEMENT[key])
            for key in FALLBACK_JUDGEMENT
        }
        self.fact_ledger.append({
            "tick": tick,
            "agent_id": agent_id,
            "action_text": action_text,
            "patches": patches,
            "before": before,
            "after": copy.deepcopy(self.object_facts),
            "judgement": judgement,
        })
        if judgement["event_summary"]:
            self.chunks["recent_events"] = (
                self.chunks["recent_events"] + [str(judgement["event_summary"])]
            )[-RECENT_EVENTS_WINDOW:]
        self._render_dynamic_objects()
        return judgement

    def _validate_patches(self, patches: Any, agent_id: str) -> List[Dict[str, Any]]:
        if not isinstance(patches, list):
            raise ValueError("patches 必须是数组")
        validated = []
        for patch in patches:
            if not isinstance(patch, dict):
                raise ValueError("每条 patch 必须是对象")
            object_id = patch.get("object_id")
            if object_id not in self.object_facts:
                raise ValueError(f"未知 object_id: {object_id}")
            if self.object_facts[object_id]["hidden"]:
                # 隐藏对象永远保持 hidden：丢弃针对它的 patch，但不让整个动作失败
                # （秘密只通过 private_feedback 定向告知发现者，对象状态不迁移）
                continue
            updates: Dict[str, str] = {}
            for key, value in patch.items():
                if key == "object_id":
                    continue
                if key in _META_FIELDS:
                    raise ValueError(f"不允许修改保留字段: {key}")
                if not isinstance(value, str):
                    raise ValueError(f"字段 {key} 的值必须是字符串，收到: {type(value).__name__}")
                if len(value) > 100:
                    raise ValueError(f"字段 {key} 的值不能超过 100 字符")
                if key == "held_by" and value not in ("", agent_id):
                    raise ValueError("只能把对象交给行动者或放下")
                updates[key] = value
            validated.append({"object_id": object_id, "updates": updates})
        return validated

    def _apply_patches(self, patches: List[Dict[str, Any]]) -> None:
        for patch in patches:
            self.object_facts[patch["object_id"]].update(patch["updates"])

    def _render_dynamic_objects(self) -> None:
        parts = []
        skip = _META_FIELDS | {"state", "held_by"}
        for row in self.object_facts.values():
            if row["hidden"]:
                continue
            text = f"{row['name']}：{row.get('state', '')}"
            extras = [(k, v) for k, v in row.items() if k not in skip and v]
            if extras:
                text += "（" + "，".join(f"{k}：{v}" for k, v in extras) + "）"
            if row.get("held_by"):
                text += f"，由 {row['held_by']} 持有"
            parts.append(text)
        self.chunks["dynamic_objects"] = "；".join(parts) or "暂无可变物品。"

    def agent_leave(self, agent_id: str) -> None:
        # 离开地点时释放该 agent 在本地点持有的对象，避免留下「由不在场的人持有」的鬼魂状态。
        # 注：当前对象锚定在地点、无跨地点流动，离开等价于「放下」。
        super().agent_leave(agent_id)
        self._release_holdings(agent_id)

    def _release_holdings(self, agent_id: str) -> None:
        released = False
        for row in self.object_facts.values():
            if row.get("held_by") == agent_id:
                row["held_by"] = ""
                released = True
        if released:
            self._render_dynamic_objects()

    def tick_update(self, tick: int) -> None:
        return None

    def snapshot(self, include_hidden: bool = False, include_pending: bool = False) -> Dict[str, Any]:
        snapshot = super().snapshot(include_hidden=include_hidden, include_pending=include_pending)
        if include_hidden:
            snapshot["object_facts"] = copy.deepcopy(self.object_facts)
            snapshot["fact_ledger"] = copy.deepcopy(self.fact_ledger)
        return snapshot
