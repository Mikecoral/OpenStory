from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any


def ensure_optional_agentkernel_imports() -> None:
    """Provide import-time stubs for optional Agent-Kernel dependencies."""

    if "faker" not in sys.modules and importlib.util.find_spec("faker") is None:
        faker_stub = types.ModuleType("faker")
        faker_stub.Faker = type("Faker", (), {})
        sys.modules["faker"] = faker_stub

    if "redis" not in sys.modules and importlib.util.find_spec("redis") is None:
        redis_stub = types.ModuleType("redis")
        redis_asyncio_stub = types.ModuleType("redis.asyncio")
        redis_asyncio_stub.ConnectionPool = type(
            "ConnectionPool",
            (),
            {"from_url": classmethod(lambda cls, *args, **kwargs: cls())},
        )
        redis_asyncio_stub.StrictRedis = type(
            "StrictRedis",
            (),
            {"__init__": lambda self, *args, **kwargs: None, "ping": lambda self: True},
        )
        redis_asyncio_stub.Redis = redis_asyncio_stub.StrictRedis
        redis_stub.asyncio = redis_asyncio_stub
        sys.modules["redis"] = redis_stub
        sys.modules["redis.asyncio"] = redis_asyncio_stub

    if "pymilvus" not in sys.modules and importlib.util.find_spec("pymilvus") is None:
        pymilvus_stub = types.ModuleType("pymilvus")
        pymilvus_stub.AsyncMilvusClient = type("AsyncMilvusClient", (), {})
        pymilvus_stub.CollectionSchema = type("CollectionSchema", (), {"__init__": lambda self, *a, **k: None})
        pymilvus_stub.FieldSchema = type("FieldSchema", (), {"__init__": lambda self, *a, **k: None})
        pymilvus_stub.DataType = type(
            "DataType",
            (),
            {"VARCHAR": "VARCHAR", "FLOAT_VECTOR": "FLOAT_VECTOR", "DOUBLE": "DOUBLE", "INT64": "INT64"},
        )
        sys.modules["pymilvus"] = pymilvus_stub

    if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
        asyncpg_stub = types.ModuleType("asyncpg")
        pool_stub = types.ModuleType("asyncpg.pool")
        asyncpg_stub.Pool = type("Pool", (), {})
        asyncpg_stub.Connection = type("Connection", (), {})
        pool_stub.Pool = asyncpg_stub.Pool
        pool_stub.PoolAcquireContext = type("PoolAcquireContext", (), {})

        async def create_pool(*args: Any, **kwargs: Any) -> Any:
            return asyncpg_stub.Pool()

        asyncpg_stub.create_pool = create_pool
        asyncpg_stub.pool = pool_stub
        sys.modules["asyncpg"] = asyncpg_stub
        sys.modules["asyncpg.pool"] = pool_stub

    if "fastmcp" not in sys.modules and importlib.util.find_spec("fastmcp") is None:
        fastmcp_stub = types.ModuleType("fastmcp")

        class Client:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def __aenter__(self) -> "Client":
                return self

            async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
                return None

            async def list_tools(self) -> list[Any]:
                return []

            async def call_tool(self, *args: Any, **kwargs: Any) -> Any:
                return None

        fastmcp_stub.Client = Client
        sys.modules["fastmcp"] = fastmcp_stub

    if "aiohttp" not in sys.modules and importlib.util.find_spec("aiohttp") is None:
        aiohttp_stub = types.ModuleType("aiohttp")

        class ClientSession:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def __aenter__(self) -> "ClientSession":
                return self

            async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
                return None

            async def post(self, *args: Any, **kwargs: Any) -> Any:
                return None

            async def get(self, *args: Any, **kwargs: Any) -> Any:
                return None

            async def close(self) -> None:
                return None

        aiohttp_stub.ClientSession = ClientSession
        aiohttp_stub.ClientTimeout = type("ClientTimeout", (), {"__init__": lambda self, *a, **k: None})
        aiohttp_stub.ClientError = type("ClientError", (Exception,), {})
        sys.modules["aiohttp"] = aiohttp_stub
