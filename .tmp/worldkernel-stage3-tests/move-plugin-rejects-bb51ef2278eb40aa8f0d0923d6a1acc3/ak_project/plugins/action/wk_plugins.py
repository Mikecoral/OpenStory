
from __future__ import annotations

import importlib.util
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

from agentkernel_distributed.mas.action.base.plugin_base import CommunicationPlugin, OtherActionsPlugin
from agentkernel_distributed.toolkit.utils.annotation import AgentCall
from agentkernel_distributed.types.schemas.action import ActionResult, CallStatus


def _result(method_name: str, success: bool, message: str, data: dict[str, Any] | None = None) -> ActionResult:
    if success:
        return ActionResult.success(method_name=method_name, message=message, data=data or {})
    return ActionResult.error(method_name=method_name, message=message, data=data or {})


class WKCommunicationPlugin(CommunicationPlugin):
    async def _log_action(self, *args: Any, **kwargs: Any) -> None:
        return None

    @AgentCall
    async def communicate(self, sender: str, receiver: str, content: str) -> ActionResult:
        return _result("communicate", True, "communication recorded", {"sender": sender, "receiver": receiver, "content": content})


class WKMovePlugin(OtherActionsPlugin):
    async def init(self, model_router: Any = None, controller: Any = None) -> None:
        self.model = model_router
        self.controller = controller

    async def _log_action(self, *args: Any, **kwargs: Any) -> None:
        return None

    @AgentCall
    async def move_to(self, agent_id: str, location: str) -> ActionResult:
        if not self.controller:
            return _result("move_to", False, "controller unavailable")
        profile = await self.controller.run_agent_method(agent_id, "profile", "get_agent_profile")
        current_location_id = await self.controller.run_agent_method(agent_id, "state", "get_state", "location_id")
        can_enter = await self.controller.run_environment("space", "can_agent_enter", profile, location)
        if not can_enter.get("allowed"):
            return _result("move_to", False, can_enter.get("reason", "location is not accessible"))
        route = await self.controller.run_environment("space", "find_route", current_location_id, can_enter.get("location_id"))
        if route is None and current_location_id != can_enter.get("location_id"):
            return _result("move_to", False, "target location is not reachable")
        position = await self.controller.run_environment("space", "update_agent_location", agent_id, can_enter.get("location_id"))
        await self.controller.run_agent_method(agent_id, "state", "set_state", "location_id", can_enter.get("location_id"))
        await self.controller.run_agent_method(agent_id, "state", "set_state", "current_location", can_enter.get("location_name"))
        await self.controller.run_agent_method(agent_id, "state", "set_state", "position", position)
        return _result("move_to", True, "move completed", {"location_id": can_enter.get("location_id"), "position": position})


class WKOtherActionPlugin(OtherActionsPlugin):
    async def init(self, model_router: Any = None, controller: Any = None) -> None:
        self.model = model_router
        self.controller = controller

    async def _log_action(self, *args: Any, **kwargs: Any) -> None:
        return None

    @AgentCall
    async def noop(self, agent_id: str, reason: str = "") -> ActionResult:
        return _result("noop", True, reason or "no operation")
