"""Global generation constraints for WorldKernel pipeline.

Provides configurable limits on entity counts (locations, characters, etc.)
that are enforced in both Stage1 (prompt injection + post-LLM truncation)
and Stage2 (SeedResolver safety check).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_IMPORTANCE_RANK: dict[str, int] = {"core": 3, "major": 2, "minor": 1}

T = TypeVar("T")


class GenerationConstraints(BaseModel):
    max_locations: int = 20   # 0 = unlimited
    max_characters: int = 20  # 0 = unlimited


_CONSTRAINTS_PATH = Path(__file__).parent.parent.parent / "configs" / "architect.yaml"


def load_generation_constraints(path: Path | None = None) -> GenerationConstraints:
    """Load constraints from YAML config. Returns defaults if file missing/empty."""
    p = path or _CONSTRAINTS_PATH
    if not p.exists():
        return GenerationConstraints()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return GenerationConstraints.model_validate(data.get("generation_constraints", {}))


def truncate_seeds(
    seeds: list[T],
    max_count: int,
    entity_type_label: str,
) -> tuple[list[T], list[str]]:
    """Truncate seed list to max_count, keeping highest-priority seeds.

    Sorting priority (highest first):
      1. generation_priority ascending (1 = highest)
      2. importance descending (core=3 > major=2 > minor=1)
      3. confidence descending

    Args:
        seeds: List of seeds (EntitySeed, SeedCatalogEntry, or ResolvedSeed).
        max_count: Maximum allowed. <= 0 means unlimited.
        entity_type_label: Label for warning messages (e.g. "location").

    Returns:
        (kept_seeds, warning_messages)
    """
    if max_count <= 0 or len(seeds) <= max_count:
        return seeds, []

    def sort_key(seed: T) -> tuple[int, int, float]:
        priority = getattr(seed, "generation_priority", None)
        if priority is None:
            seed_obj = getattr(seed, "seed", None)
            priority = getattr(seed_obj, "generation_priority", 1) if seed_obj else 1
        importance = getattr(seed, "importance", None)
        if importance is None:
            seed_obj = getattr(seed, "seed", None)
            importance = getattr(seed_obj, "importance", "") if seed_obj else ""
        confidence = getattr(seed, "confidence", None)
        if confidence is None:
            seed_obj = getattr(seed, "seed", None)
            confidence = getattr(seed_obj, "confidence", 0.0) if seed_obj else 0.0
        return (
            int(priority),
            -_IMPORTANCE_RANK.get(str(importance).lower(), 0),
            -float(confidence),
        )

    sorted_seeds = sorted(seeds, key=sort_key)
    kept = sorted_seeds[:max_count]
    dropped = sorted_seeds[max_count:]

    warnings: list[str] = []
    for s in dropped:
        name = getattr(s, "name", None)
        if name is None:
            seed_obj = getattr(s, "seed", None)
            name = getattr(seed_obj, "name", getattr(s, "seed_id", "?")) if seed_obj else "?"
        warnings.append(
            f"constraint: dropped {entity_type_label} seed '{name}' "
            f"(priority={getattr(s, 'generation_priority', '?')}, "
            f"importance={getattr(s, 'importance', '?')})"
        )

    logger.info(
        "Truncated %s seeds: %d -> %d (dropped %d)",
        entity_type_label, len(seeds), len(kept), len(dropped),
    )
    for w in warnings:
        logger.warning(w)

    return kept, warnings
