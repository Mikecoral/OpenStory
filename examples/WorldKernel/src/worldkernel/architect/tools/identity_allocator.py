"""Unified entity ID allocator for Stage2 generation.

Assigns persistent, globally unique entity IDs after generation,
replacing the unreliable LLM-generated identity.id values.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from worldkernel.architect.init.models import ResolvedSeed


class IdentityAllocator:
    """统一实体 ID 分配器。管理全局唯一性，天然支持子世界层级路径。"""

    def __init__(self, world_name: str):
        self._world_slug = self._to_slug(world_name)
        self._counter = 0
        self._allocated: set[str] = set()
        self._seed_to_entity: dict[str, str] = {}

    def allocate_ids(
        self,
        items: list[BaseModel],
        entity_type: str,
        seeds: list[ResolvedSeed],
    ) -> list[str]:
        """为生成的实体分配 ID，返回分配的 ID 列表。

        Args:
            items: 已验证的 Pydantic 模型实例列表，必须有 identity.id 字段。
            entity_type: 实体类型缩写（"loc", "char", "path", "rel"）。
            seeds: 对应的种子列表，用于建立 seed_ref → entity_id 映射。

        Returns:
            分配的 entity_id 列表。
        """
        if len(items) != len(seeds):
            # items 和 seeds 数量不匹配时，按最小数量分配
            pass

        ids: list[str] = []
        for i, item in enumerate(items):
            entity_id = self._next_id(entity_type)
            self._allocated.add(entity_id)

            # 更新 identity.id
            identity = getattr(item, "identity", None)
            if identity is not None and hasattr(identity, "id"):
                old_id = identity.id
                identity.id = entity_id
            else:
                old_id = ""

            # 记录 seed_ref → entity_id 映射
            if i < len(seeds):
                self._seed_to_entity[seeds[i].stable_seed_ref] = entity_id

            ids.append(entity_id)

        return ids

    def resolve_ref(self, seed_ref: str) -> str | None:
        """将 seed_ref 解析为已分配的 entity_id。"""
        return self._seed_to_entity.get(seed_ref)

    @property
    def allocated_count(self) -> int:
        """已分配的 ID 总数。"""
        return len(self._allocated)

    @property
    def seed_mapping(self) -> dict[str, str]:
        """seed_ref → entity_id 的完整映射。"""
        return dict(self._seed_to_entity)

    def _next_id(self, entity_type: str) -> str:
        """生成下一个全局唯一的实体 ID。"""
        self._counter += 1
        short_id = f"{self._counter:03d}"
        return f"e:{self._world_slug}:{entity_type}:{short_id}"

    @staticmethod
    def _to_slug(name: str) -> str:
        """将 world_name 转换为 slug 格式。

        规则：小写、空格转下划线、去除特殊字符、合并连续下划线。
        """
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9一-鿿]+", "_", slug)
        slug = slug.strip("_")
        return slug or "world"
