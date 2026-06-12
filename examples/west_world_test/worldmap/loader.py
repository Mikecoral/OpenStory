"""地图真值的加载、校验与查询。locations.yaml 是唯一真值源。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import yaml


@dataclass
class Location:
    id: str
    name: str
    region: str
    type: str
    active: bool
    bbox: List[float]
    adjacency: List[str]
    description: str = ""
    objects: List[Dict[str, Any]] = field(default_factory=list)
    default_occupants: List[str] = field(default_factory=list)

    def visible_objects(self) -> List[Dict[str, Any]]:
        return [o for o in self.objects if not o.get("hidden")]

    def hidden_objects(self) -> List[Dict[str, Any]]:
        return [o for o in self.objects if o.get("hidden")]


class WorldMap:
    def __init__(self, locations: List[Location]) -> None:
        self.locations: Dict[str, Location] = {loc.id: loc for loc in locations}
        self._validate(locations)

    def _validate(self, locations: List[Location]) -> None:
        if len(locations) != len(self.locations):
            raise ValueError("location id 重复")
        for loc in locations:
            for nb in loc.adjacency:
                if nb not in self.locations:
                    raise ValueError(f"{loc.id} 邻接未知地点 {nb}")
                if loc.id not in self.locations[nb].adjacency:
                    raise ValueError(f"邻接不对称: {loc.id} -> {nb}")

    def get(self, location_id: str) -> Location:
        return self.locations[location_id]

    def active_ids(self) -> set:
        return {loc.id for loc in self.locations.values() if loc.active}

    def neighbors(self, location_id: str, active_only: bool = True) -> List[str]:
        nbs = self.get(location_id).adjacency
        if active_only:
            nbs = [n for n in nbs if self.get(n).active]
        return list(nbs)

    def can_move(self, src: str, dst: str) -> Tuple[bool, str]:
        if dst not in self.locations:
            return False, f"不存在名为 {dst} 的地方"
        if src not in self.locations:
            return False, f"不存在名为 {src} 的出发地"
        if dst not in self.get(src).adjacency:
            return False, f"{self.get(dst).name} 与当前位置不相邻"
        if not self.get(dst).active:
            return False, f"通往{self.get(dst).name}的路被封锁了"
        return True, ""


def load_world_map(path: str) -> WorldMap:
    with open(path, "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)
    return WorldMap([Location(**row) for row in rows])
