"""Unified entity ID management for Stage2 generation.

Split into two classes:
- IdentityAllocator: deterministic candidate ID generator (pure, stateless)
- IdentityRegistry: idempotent mapping manager (reuse existing, register new)
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from worldkernel.architect.init.models import ResolvedSeed

logger = logging.getLogger(__name__)


class IdentityAllocator:
    """Deterministic candidate ID generator.

    Generates IDs based on sorted seed order, guaranteeing the same
    seed set always produces the same candidate IDs regardless of
    call order or retry strategy.
    """

    def __init__(self, world_slug: str):
        self._world_slug = world_slug

    def generate_for_seeds(
        self,
        seeds: list[ResolvedSeed],
        entity_type: str,
        existing_ids: set[str] | None = None,
    ) -> dict[str, str]:
        """Generate deterministic candidate IDs for a batch of seeds.

        Seeds are sorted by seed_id before counter assignment,
        ensuring the same seed set always gets the same IDs.

        Args:
            seeds: Seeds to generate IDs for.
            entity_type: Entity type prefix (e.g., "loc", "char").
            existing_ids: Set of already-registered entity IDs.
                If provided, counter starts after the max existing counter
                to avoid collisions.

        Returns:
            Mapping of {seed_id: entity_id}.
        """
        start_counter = 0
        if existing_ids:
            pattern = re.compile(
                rf"e:{re.escape(self._world_slug)}:{entity_type}:(\d+)"
            )
            for eid in existing_ids:
                m = pattern.match(eid)
                if m:
                    start_counter = max(start_counter, int(m.group(1)))

        sorted_seeds = sorted(seeds, key=lambda s: s.seed_id)
        result: dict[str, str] = {}
        for i, seed in enumerate(sorted_seeds, 1):
            short_id = f"{start_counter + i:03d}"
            entity_id = f"e:{self._world_slug}:{entity_type}:{short_id}"
            result[seed.seed_id] = entity_id
        return result

    @property
    def world_slug(self) -> str:
        return self._world_slug

    @staticmethod
    def to_slug(name: str) -> str:
        """Convert world_name to slug format.

        Rules: lowercase, spaces to underscores, strip special chars,
        merge consecutive underscores.
        """
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        return slug or "world"


class IdentityRegistry:
    """Idempotent entity ID registry.

    Maintains a mapping of ``{entity_type}:{seed_id}`` -> entity_id.
    Keys are scoped by entity_type to prevent cross-type collisions
    (e.g. a location seed and a character seed sharing the same seed_id).

    Guarantees:
    - Same seed always gets same entity_id (idempotent)
    - Deterministic regardless of call order or retry
    - New seeds don't affect existing mappings
    - Different entity types never collide, even with identical seed_ids
    """

    def __init__(self, allocator: IdentityAllocator):
        self._allocator = allocator
        self._registry: dict[str, str] = {}

    @staticmethod
    def _scoped_key(entity_type: str, seed_id: str) -> str:
        """Build a composite registry key that scopes seed_id by entity_type."""
        return f"{entity_type}:{seed_id}"

    def register_batch(
        self,
        seeds: list[ResolvedSeed],
        entity_type: str,
    ) -> dict[str, str]:
        """Batch register seeds. Already-registered seeds are skipped.

        New seeds get candidate IDs starting after the max existing counter
        to avoid collisions.

        Returns:
            Mapping of all seeds' {seed_id: entity_id} (both
            previously registered and newly registered).
        """
        new_seeds = [
            s for s in seeds
            if self._scoped_key(entity_type, s.seed_id) not in self._registry
        ]
        if new_seeds:
            candidates = self._allocator.generate_for_seeds(
                new_seeds,
                entity_type,
                existing_ids=set(self._registry.values()),
            )
            for sid, eid in candidates.items():
                self._registry[self._scoped_key(entity_type, sid)] = eid
        return {s.seed_id: self._registry[self._scoped_key(entity_type, s.seed_id)] for s in seeds}

    def lookup(self, seeds: list[ResolvedSeed], entity_type: str) -> dict[str, str]:
        """Look up pre-registered seed -> entity_id mappings.

        All seeds must have been registered beforehand via register_batch().
        """
        return {s.seed_id: self._registry[self._scoped_key(entity_type, s.seed_id)] for s in seeds}

    def verify_and_fix(
        self,
        items: list[BaseModel],
        entity_type: str,
        seeds: list[ResolvedSeed],
    ) -> list[str]:
        """Verify and fix items' identity.id to match registered values.

        Matches items to seeds by name (not positional index), so LLM
        reordering does not cause ID mismatches. Falls back to ID reverse
        lookup, then positional index.

        Returns:
            List of entity IDs (one per item).
        """
        seed_by_name: dict[str, ResolvedSeed] = {}
        for s in seeds:
            if s.name:
                seed_by_name[s.name] = s

        # Build reverse lookup: entity_id -> seed (for ID-based fallback)
        id_to_seed: dict[str, ResolvedSeed] = {}
        for s in seeds:
            eid = self._registry.get(self._scoped_key(entity_type, s.seed_id))
            if eid:
                id_to_seed[eid] = s

        used_seed_ids: set[str] = set()
        ids: list[str] = []
        fallback_index = 0

        for item in items:
            identity = getattr(item, "identity", None)
            item_name = getattr(identity, "name", "") if identity else ""
            item_id = getattr(identity, "id", "") if identity else ""

            matched_seed: ResolvedSeed | None = None

            # Strategy 1: match by name
            if item_name and item_name in seed_by_name:
                matched_seed = seed_by_name[item_name]

            # Strategy 2: reverse lookup by pre-allocated id
            if matched_seed is None and item_id and item_id in id_to_seed:
                matched_seed = id_to_seed[item_id]

            # Strategy 3: positional index fallback (skip already-used seeds)
            if matched_seed is None:
                while fallback_index < len(seeds) and seeds[fallback_index].seed_id in used_seed_ids:
                    fallback_index += 1
                if fallback_index < len(seeds):
                    matched_seed = seeds[fallback_index]
                    fallback_index += 1
                    logger.warning(
                        "verify_and_fix: item '%s' matched by positional fallback",
                        item_name or "(unnamed)",
                    )

            if matched_seed is None:
                logger.warning(
                    "verify_and_fix: no seed match for item '%s', skipping",
                    item_name or "(unnamed)",
                )
                continue

            used_seed_ids.add(matched_seed.seed_id)
            expected_id = self._registry[self._scoped_key(entity_type, matched_seed.seed_id)]
            if identity is not None and hasattr(identity, "id"):
                identity.id = expected_id
            ids.append(expected_id)

        return ids

    def allocate_dynamic(self, count: int, entity_type: str) -> list[str]:
        """Allocate entity IDs for dynamically generated items (no seeds).

        Used when the number of entities is determined by LLM output
        (e.g., path generation) and cannot be pre-registered.

        Returns:
            List of entity_id strings, length == count.
        """
        class _DynSeed:
            __slots__ = ("seed_id",)
            def __init__(self, sid: str):
                self.seed_id = sid

        synthetic = [_DynSeed(f"__dyn_{entity_type}_{i:03d}") for i in range(count)]
        self.register_batch(synthetic, entity_type)  # type: ignore[arg-type]
        return [self._registry[self._scoped_key(entity_type, s.seed_id)] for s in synthetic]

    def allocate_for_paths(self, paths: list[BaseModel]) -> list[str]:
        """Allocate deterministic IDs for paths based on sorted endpoint pairs.

        Same undirected edge (A-B or B-A) always gets the same entity_id,
        regardless of LLM output order or retry.
        """
        class _EdgeSeed:
            __slots__ = ("seed_id",)
            def __init__(self, sid: str):
                self.seed_id = sid

        seeds: list[_EdgeSeed] = []
        for path in paths:
            ep = getattr(path, "endpoints", None)
            if ep is None:
                continue
            src = getattr(ep, "from_id", "")
            dst = getattr(ep, "to_id", "")
            pair = tuple(sorted([src, dst]))
            seeds.append(_EdgeSeed(f"{pair[0]}->{pair[1]}"))

        self.register_batch(seeds, "path")  # type: ignore[arg-type]
        return [self._registry[self._scoped_key("path", s.seed_id)] for s in seeds]

    def allocate_for_relations(self, relations: list[BaseModel]) -> list[str]:
        """Allocate deterministic IDs for relations based on (from_id, to_id, type).

        Same directed relation (A->B with same type) always gets the same entity_id,
        regardless of LLM output order or retry.
        """
        class _RelSeed:
            __slots__ = ("seed_id",)
            def __init__(self, sid: str):
                self.seed_id = sid

        seeds: list[_RelSeed] = []
        for rel in relations:
            edge = getattr(rel, "edge", None)
            if edge is None:
                continue
            src = getattr(edge, "from_id", "")
            dst = getattr(edge, "to_id", "")
            rel_type = getattr(edge, "type", "")
            seeds.append(_RelSeed(f"{src}->{dst}:{rel_type}"))

        self.register_batch(seeds, "rel")  # type: ignore[arg-type]
        return [self._registry[self._scoped_key("rel", s.seed_id)] for s in seeds]

    def seed_mapping_by_type(self, entity_type: str) -> dict[str, str]:
        """Return seed_id -> entity_id mapping for a specific entity_type.

        Strips the scoped key prefix for external consumption.
        """
        prefix = f"{entity_type}:"
        return {
            k[len(prefix):]: v
            for k, v in self._registry.items()
            if k.startswith(prefix)
        }

    @property
    def seed_mapping(self) -> dict[str, str]:
        """Complete scoped_key -> entity_id mapping (for provenance/debugging)."""
        return dict(self._registry)
