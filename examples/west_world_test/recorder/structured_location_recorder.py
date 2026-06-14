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
from .world_object_registry import META_FIELDS, get_object_registry

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
        self.registry = get_object_registry()
        self._seed_location()
        self.fact_ledger: List[Dict[str, Any]] = []
        self._render_dynamic_objects()

    def _seed_location(self) -> None:
        if self.registry.is_location_seeded(self.location.id):
            return
        for item in self.location.objects:
            fields = {"state": item.get("note", "状态正常")}
            if item.get("secret"):
                fields["secret"] = item["secret"]
            self.registry.create(
                name=item["name"], location_id=self.location.id, by="__seed__",
                tick=None, action="__seed__", fields=fields, hidden=bool(item.get("hidden")),
            )
        self.registry.mark_location_seeded(self.location.id)

    def submit_action(self, agent_id: str, action_text: str, tick: Optional[int] = None) -> Dict[str, Any]:
        # Only expose non-hidden objects to the LLM
        visible_rows = self.registry.objects_at(self.location.id, include_hidden=False)
        visible_objects = [
            {"object_id": row["object_id"], "name": row["name"]}
            for row in visible_rows
        ]
        visible_facts = {
            row["object_id"]: {k: v for k, v in row.items() if k != "hidden"}
            for row in visible_rows
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
        before = self.registry.objects_at(self.location.id, include_hidden=True)
        self._apply_patches(patches)
        after = self.registry.objects_at(self.location.id, include_hidden=True)
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
            "after": after,
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
            # Check existence: must be known to registry and belong to this location
            if not self.registry.has(object_id):
                raise ValueError(f"未知 object_id: {object_id}")
            obj = self.registry.get(object_id)
            if obj["location_id"] != self.location.id or obj["destroyed"]:
                raise ValueError(f"未知 object_id: {object_id}")
            if obj["hidden"]:
                # 隐藏对象永远保持 hidden：丢弃针对它的 patch，但不让整个动作失败
                continue
            updates: Dict[str, str] = {}
            for key, value in patch.items():
                if key == "object_id":
                    continue
                if key in META_FIELDS:
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
            self.registry.apply_patch(patch["object_id"], patch["updates"])

    def _render_dynamic_objects(self) -> None:
        parts = []
        skip = {"object_id", "name", "hidden", "destroyed", "provenance", "location_id", "state", "held_by", "secret"}
        for row in self.registry.objects_at(self.location.id):
            text = f"{row['name']}：{row.get('state', '')}"
            extras = [(k, v) for k, v in row.items() if k not in skip and v]
            if extras:
                text += "（" + "，".join(f"{k}：{v}" for k, v in extras) + "）"
            if row.get("held_by"):
                text += f"，由 {row['held_by']} 持有"
            parts.append(text)
        self.chunks["dynamic_objects"] = "；".join(parts) or "暂无可变物品。"

    def tick_update(self, tick: int) -> None:
        return None

    def snapshot(self, include_hidden: bool = False, include_pending: bool = False) -> Dict[str, Any]:
        snapshot = super().snapshot(include_hidden=include_hidden, include_pending=include_pending)
        if include_hidden:
            snapshot["object_facts"] = self.registry.objects_at(self.location.id, include_hidden=True)
            snapshot["fact_ledger"] = copy.deepcopy(self.fact_ledger)
        return snapshot
