
from __future__ import annotations

import importlib.util
import math
import sys
import types
from typing import Any

if "faker" not in sys.modules and importlib.util.find_spec("faker") is None:
    faker_stub = types.ModuleType("faker")
    faker_stub.Faker = type("Faker", (), {})
    sys.modules["faker"] = faker_stub
if "redis" not in sys.modules and importlib.util.find_spec("redis") is None:
    redis_stub = types.ModuleType("redis")
    redis_asyncio_stub = types.ModuleType("redis.asyncio")
    redis_asyncio_stub.ConnectionPool = type("ConnectionPool", (), {"from_url": classmethod(lambda cls, *a, **k: cls())})
    redis_asyncio_stub.StrictRedis = type("StrictRedis", (), {"__init__": lambda self, *a, **k: None, "ping": lambda self: True})
    redis_asyncio_stub.Redis = redis_asyncio_stub.StrictRedis
    redis_stub.asyncio = redis_asyncio_stub
    sys.modules["redis"] = redis_stub
    sys.modules["redis.asyncio"] = redis_asyncio_stub
if "pymilvus" not in sys.modules and importlib.util.find_spec("pymilvus") is None:
    pymilvus_stub = types.ModuleType("pymilvus")
    pymilvus_stub.AsyncMilvusClient = type("AsyncMilvusClient", (), {})
    pymilvus_stub.CollectionSchema = type("CollectionSchema", (), {"__init__": lambda self, *a, **k: None})
    pymilvus_stub.FieldSchema = type("FieldSchema", (), {"__init__": lambda self, *a, **k: None})
    pymilvus_stub.DataType = type("DataType", (), {"VARCHAR": "VARCHAR", "FLOAT_VECTOR": "FLOAT_VECTOR", "DOUBLE": "DOUBLE", "INT64": "INT64"})
    sys.modules["pymilvus"] = pymilvus_stub
if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
    sys.modules["asyncpg"] = types.ModuleType("asyncpg")

from agentkernel_distributed.mas.environment.base.plugin_base import RelationPlugin, SpacePlugin


class WKRelationPlugin(RelationPlugin):
    def __init__(self, relations: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self.relations = relations or []

    async def init(self) -> None:
        return None

    async def execute(self, current_tick: int) -> None:
        return None

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None

    async def get_all_relations(self) -> list[dict[str, Any]]:
        return self.relations

    async def get_relation(self, agent_id: str, target_id: str) -> dict[str, Any] | None:
        for relation in self.relations:
            if relation.get("source") == agent_id and relation.get("target") == target_id:
                return relation
        return None

    async def set_relation(self, agent_id: str, target_id: str, relation_data: dict[str, Any]) -> None:
        self.relations.append({"source": agent_id, "target": target_id, **relation_data})

    async def update_relation(self, agent_id: str, target_id: str, updates: dict[str, Any]) -> None:
        relation = await self.get_relation(agent_id, target_id)
        if relation:
            relation.update(updates)


class WKSpacePlugin(SpacePlugin):
    def __init__(
        self,
        locations: list[dict[str, Any]] | None = None,
        paths: list[dict[str, Any]] | None = None,
        agents: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.locations = locations or []
        self.paths = paths or []
        self.agents = agents or []
        self.location_by_id = {loc.get("id"): loc for loc in self.locations}
        self.location_by_name = {loc.get("name"): loc for loc in self.locations}
        self.agent_positions = {
            agent.get("id"): {
                "location_id": agent.get("location_id"),
                "location": agent.get("location"),
                "position": agent.get("position") or [0, 0],
            }
            for agent in self.agents
        }

    async def init(self) -> None:
        return None

    async def execute(self, current_tick: int) -> None:
        return None

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None

    async def get_location_profile(self, location_id_or_name: str) -> dict[str, Any] | None:
        return self.location_by_id.get(location_id_or_name) or self.location_by_name.get(location_id_or_name)

    async def list_locations(self) -> list[dict[str, Any]]:
        return self.locations

    async def list_accessible_locations(self, agent_profile: dict[str, Any], current_tick: int = 0) -> list[dict[str, Any]]:
        accessible = []
        for location in self.locations:
            check = await self.can_agent_enter(agent_profile, location.get("id"))
            if check.get("allowed"):
                accessible.append(location)
        return accessible

    async def get_location_affordances(self, location_id: str) -> dict[str, Any]:
        location = await self.get_location_profile(location_id)
        if not location:
            return {}
        return {
            "location_id": location.get("id"),
            "name": location.get("name"),
            "type": location.get("type"),
            "access": location.get("access", {}),
            "state": location.get("state", {}),
            "capacity": location.get("capacity", 0),
            "tags": location.get("tags", []),
            "key_plot_events": location.get("key_plot_events", ""),
            "symbolic_meaning": location.get("symbolic_meaning", ""),
        }

    async def can_agent_enter(self, agent_profile: dict[str, Any] | None, location_id_or_name: str) -> dict[str, Any]:
        location = await self.get_location_profile(location_id_or_name)
        if not location:
            return {"allowed": False, "reason": "location not found"}
        access = location.get("access", {})
        state = location.get("state", {})
        text = " ".join(str(access.get(k, "")) for k in access)
        state_text = " ".join(str(state.get(k, "")) for k in state)
        if any(token in (text + " " + state_text).lower() for token in ["closed", "forbidden", "blocked", "不可进入", "封闭"]):
            return {"allowed": False, "reason": "location access is restricted by current profile", "location_id": location.get("id")}
        return {"allowed": True, "location_id": location.get("id"), "location_name": location.get("name")}

    async def find_route(self, from_location_id: str, to_location_id: str) -> dict[str, Any] | None:
        if not from_location_id or not to_location_id:
            return None
        if from_location_id == to_location_id:
            return {"same_location": True}
        for path in self.paths:
            if path.get("from_location_id") == from_location_id and path.get("to_location_id") == to_location_id:
                return path
            if path.get("bidirectional", True) and path.get("from_location_id") == to_location_id and path.get("to_location_id") == from_location_id:
                return path
        return None

    async def get_agent_position(self, agent_id: str) -> list[int] | None:
        entry = self.agent_positions.get(agent_id)
        return entry.get("position") if entry else None

    async def update_agent_position(self, agent_id: str, position: list[int]) -> None:
        self.agent_positions.setdefault(agent_id, {})["position"] = position

    async def update_agent_location(self, agent_id: str, location_id: str) -> list[int]:
        location = self.location_by_id.get(location_id) or {}
        entrance = location.get("entrance") or {}
        position = [int(entrance.get("x", 0)), int(entrance.get("y", 0))]
        self.agent_positions[agent_id] = {
            "location_id": location_id,
            "location": location.get("name"),
            "position": position,
        }
        return position

    async def get_all_positions(self) -> dict[str, list[int]]:
        return {agent_id: data.get("position", [0, 0]) for agent_id, data in self.agent_positions.items()}

    async def get_surrounding_agents(self, position: list[int], radius: int) -> list[dict[str, Any]]:
        result = []
        px, py = position
        for agent_id, data in self.agent_positions.items():
            ax, ay = data.get("position", [0, 0])
            if math.dist([px, py], [ax, ay]) <= radius:
                result.append({"id": agent_id, **data})
        return result
