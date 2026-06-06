
import importlib.util
import sys
import types

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
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Pool = type("Pool", (), {})
    asyncpg_stub.Connection = type("Connection", (), {})
    async def create_pool(*args, **kwargs):
        return asyncpg_stub.Pool()
    pool_stub = types.ModuleType("asyncpg.pool")
    pool_stub.Pool = asyncpg_stub.Pool
    pool_stub.PoolAcquireContext = type("PoolAcquireContext", (), {})
    asyncpg_stub.create_pool = create_pool
    asyncpg_stub.pool = pool_stub
    sys.modules["asyncpg"] = asyncpg_stub
    sys.modules["asyncpg.pool"] = pool_stub
if "fastmcp" not in sys.modules and importlib.util.find_spec("fastmcp") is None:
    fastmcp_stub = types.ModuleType("fastmcp")
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args, **kwargs):
            return None
        async def list_tools(self):
            return []
        async def call_tool(self, *args, **kwargs):
            return None
    fastmcp_stub.Client = Client
    sys.modules["fastmcp"] = fastmcp_stub

from agentkernel_distributed.mas.action.components import CommunicationComponent, OtherActionsComponent
from agentkernel_distributed.mas.agent.components import InvokeComponent, PerceiveComponent, PlanComponent, ProfileComponent, ReflectComponent
from agentkernel_distributed.mas.environment.components import RelationComponent, SpaceComponent
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider

from BasicController import WKController
from BasicPodManager import WKPodManager
from plugins.action.wk_plugins import WKCommunicationPlugin, WKMovePlugin, WKOtherActionPlugin
from plugins.agent.wk_plugins import (
    WKInvokePlugin,
    WKPerceivePlugin,
    WKPlanPlugin,
    WKProfilePlugin,
    WKReflectPlugin,
    WKStateComponent,
    WKStatePlugin,
)
from plugins.environment.wk_plugins import WKRelationPlugin, WKSpacePlugin


RESOURCES_MAPS = {
    "agent_components": {
        "profile": ProfileComponent,
        "state": WKStateComponent,
        "plan": PlanComponent,
        "perceive": PerceiveComponent,
        "reflect": ReflectComponent,
        "invoke": InvokeComponent,
    },
    "agent_plugins": {
        "WKProfilePlugin": WKProfilePlugin,
        "WKStatePlugin": WKStatePlugin,
        "WKPlanPlugin": WKPlanPlugin,
        "WKPerceivePlugin": WKPerceivePlugin,
        "WKInvokePlugin": WKInvokePlugin,
        "WKReflectPlugin": WKReflectPlugin,
    },
    "action_components": {
        "communication": CommunicationComponent,
        "move": OtherActionsComponent,
        "otheractions": OtherActionsComponent,
    },
    "action_plugins": {
        "WKCommunicationPlugin": WKCommunicationPlugin,
        "WKMovePlugin": WKMovePlugin,
        "WKOtherActionPlugin": WKOtherActionPlugin,
    },
    "environment_components": {
        "relation": RelationComponent,
        "space": SpaceComponent,
    },
    "environment_plugins": {
        "WKRelationPlugin": WKRelationPlugin,
        "WKSpacePlugin": WKSpacePlugin,
    },
    "system_components": {
        "messager": Messager,
        "timer": Timer,
    },
    "models": {"OpenAIProvider": OpenAIProvider},
    "adapters": {},
    "controller": WKController,
    "pod_manager": WKPodManager,
}
