"""World-level object registry: single source of truth for all objects across locations."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

# 不可被 patch 覆盖的保留字段
META_FIELDS = {"object_id", "name", "hidden", "destroyed", "provenance", "location_id"}


class WorldObjectRegistry:
    """所有地点所有对象的唯一真值源 + append-only ledger。"""

    def __init__(self) -> None:
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._next_id = 0
        self.ledger: List[Dict[str, Any]] = []
        self._seeded = False

    # ---- 写 ----
    def create(self, name: str, location_id: str, by: str, tick: Optional[int],
               action: str, fields: Dict[str, Any], hidden: bool = False,
               held_by: str = "") -> str:
        oid = f"obj_{self._next_id}"
        self._next_id += 1
        row: Dict[str, Any] = {
            "object_id": oid,
            "name": name,
            "location_id": location_id,
            "held_by": held_by,
            "state": "状态正常",
            "hidden": bool(hidden),
            "destroyed": False,
            "provenance": {"created_by": by, "created_tick": tick, "created_action": action},
        }
        for key, value in fields.items():
            if key not in META_FIELDS and key not in ("held_by",):
                row[key] = value
        self._objects[oid] = row
        self._log("create", oid, None, copy.deepcopy(row), by, tick)
        return oid

    def apply_patch(self, object_id: str, updates: Dict[str, Any]) -> None:
        if object_id not in self._objects:
            raise KeyError(f"unknown object_id: {object_id}")
        row = self._objects[object_id]
        before = copy.deepcopy(row)
        for key, value in updates.items():
            if key in META_FIELDS:
                continue
            row[key] = value
        self._log("patch", object_id, before, copy.deepcopy(row), None, None)

    def destroy(self, object_id: str, by: str, tick: Optional[int]) -> None:
        if object_id not in self._objects:
            raise KeyError(f"unknown object_id: {object_id}")
        row = self._objects[object_id]
        before = copy.deepcopy(row)
        row["destroyed"] = True
        self._log("destroy", object_id, before, copy.deepcopy(row), by, tick)

    # ---- 读 ----
    def get(self, object_id: str) -> Dict[str, Any]:
        return copy.deepcopy(self._objects[object_id])

    def has(self, object_id: str) -> bool:
        return object_id in self._objects

    def objects_at(self, location_id: str, include_hidden: bool = False) -> List[Dict[str, Any]]:
        rows = [
            r for r in self._objects.values()
            if r["location_id"] == location_id and not r["destroyed"]
            and (include_hidden or not r["hidden"])
        ]
        return [copy.deepcopy(r) for r in rows]

    def relocate_holdings(self, agent_id: str, to_location: str) -> None:
        for row in self._objects.values():
            if row["held_by"] == agent_id and not row["destroyed"]:
                before = copy.deepcopy(row)
                row["location_id"] = to_location
                self._log("relocate", row["object_id"], before, copy.deepcopy(row), agent_id, None)

    def seed_from_world(self, world_map: Any) -> None:
        if self._seeded:
            return
        for lid in sorted(world_map.active_ids()):
            location = world_map.get(lid)
            for item in location.objects:
                fields = {"state": item.get("note", "状态正常")}
                if item.get("secret"):
                    fields["secret"] = item["secret"]
                self.create(
                    name=item["name"], location_id=lid, by="__seed__", tick=None,
                    action="__seed__", fields=fields, hidden=bool(item.get("hidden")),
                )
        self._seeded = True

    def snapshot(self) -> Dict[str, Any]:
        return {
            "objects": [copy.deepcopy(r) for r in self._objects.values()],
            "ledger": copy.deepcopy(self.ledger),
        }

    def _log(self, op: str, object_id: str, before: Optional[Dict[str, Any]],
             after: Optional[Dict[str, Any]], by: Optional[str], tick: Optional[int]) -> None:
        self.ledger.append({
            "op": op, "object_id": object_id,
            "before": before, "after": after, "by": by, "tick": tick,
        })


_REGISTRY: Optional[WorldObjectRegistry] = None


def get_object_registry() -> WorldObjectRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = WorldObjectRegistry()
    return _REGISTRY


def reset_object_registry() -> None:
    """测试隔离用：清空进程内单例。"""
    global _REGISTRY
    _REGISTRY = None
