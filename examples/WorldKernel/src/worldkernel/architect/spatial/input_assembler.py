"""Step 1: SpatialInputAssembler — reads semantic artifacts into SpatialBuildInput."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from worldkernel.architect.semantic.repository import SemanticArtifactRepository
from worldkernel.architect.spatial.models import (
    CharacterPlacementFact,
    LocationSpatialFact,
    PathSpatialFact,
    SpatialBuildInput,
    SpatialInputWarning,
)

logger = logging.getLogger(__name__)

_SECRET_KEYWORDS = frozenset({
    "secret", "hidden", "restricted", "密道", "隐藏", "禁区", "秘密",
})


class SpatialInputAssemblyError(RuntimeError):
    """Raised when input assembly cannot proceed (missing files, corrupt JSON)."""


class SpatialInputAssembler:
    """Reads saved semantic artifacts and produces a standardised SpatialBuildInput."""

    def assemble(
        self,
        world_id: str,
        semantic_root: str | Path | None = None,
    ) -> SpatialBuildInput:
        repo = SemanticArtifactRepository(world_id=world_id, root=semantic_root)
        source_root = str(repo.root)

        # -- load raw lists --------------------------------------------------
        try:
            manifest = repo.load_manifest()
        except Exception as exc:
            raise SpatialInputAssemblyError(
                f"Failed to load semantic manifest from {source_root}: {exc}"
            ) from exc

        try:
            raw_locations = repo.load_locations()
        except Exception as exc:
            raise SpatialInputAssemblyError(
                f"Failed to load locations from {source_root}: {exc}"
            ) from exc

        try:
            raw_paths = repo.load_path_graph()
        except Exception as exc:
            raise SpatialInputAssemblyError(
                f"Failed to load path_graph from {source_root}: {exc}"
            ) from exc

        try:
            raw_characters = repo.load_characters()
        except Exception as exc:
            raw_characters = []
            logger.warning("Failed to load characters from %s: %s", source_root, exc)

        # -- assemble --------------------------------------------------------
        warnings: list[SpatialInputWarning] = []
        locations, location_ids = self._assemble_locations(raw_locations, warnings)
        paths = self._assemble_paths(raw_paths, location_ids, warnings)
        characters = self._assemble_characters(raw_characters, location_ids, warnings)

        provenance = {
            "semantic_root": source_root,
            "semantic_manifest": manifest.model_dump(mode="json"),
            "location_count_raw": len(raw_locations),
            "location_count_kept": len(locations),
            "path_count_raw": len(raw_paths),
            "path_count_kept": len(paths),
            "character_count_raw": len(raw_characters),
            "character_count_kept": len(characters),
        }

        return SpatialBuildInput(
            world_id=world_id,
            source_root=source_root,
            locations=locations,
            paths=paths,
            characters=characters,
            warnings=warnings,
            provenance=provenance,
        )

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def _assemble_locations(
        self,
        raw: list[Any],
        warnings: list[SpatialInputWarning],
    ) -> tuple[list[LocationSpatialFact], set[str]]:
        seen: set[str] = set()
        result: list[LocationSpatialFact] = []
        for idx, item in enumerate(raw):
            item = _to_dict(item)
            if not item:
                warnings.append(SpatialInputWarning(
                    code="non_dict_location",
                    message=f"location[{idx}] is not a dict; skipped",
                    source="locations",
                    item_index=idx,
                ))
                continue

            identity = _as_dict(item.get("identity"))
            access = _as_dict(item.get("access"))
            state = _as_dict(item.get("state"))

            location_id = (
                _safe_str(identity.get("id"))
                or _safe_str(item.get("id"))
                or ""
            )
            if not location_id:
                warnings.append(SpatialInputWarning(
                    code="missing_location_id",
                    message=f"location[{idx}] has no identity.id; skipped",
                    source="locations",
                    item_index=idx,
                ))
                continue

            if location_id in seen:
                warnings.append(SpatialInputWarning(
                    code="duplicate_location_id",
                    message=f"duplicate location_id {location_id!r}; skipped",
                    source="locations",
                    item_index=idx,
                    item_id=location_id,
                ))
                continue
            seen.add(location_id)

            name = (
                _safe_str(identity.get("name"))
                or location_id
            )
            location_type = _safe_str(identity.get("type"))
            description = _safe_str(identity.get("description"))
            access_level = _safe_str(access.get("access_level"))
            capacity = _safe_int(state.get("capacity"))
            importance = _infer_importance(item, access_level)
            tags = _build_location_tags(location_type, access_level, importance)

            fact = LocationSpatialFact(
                location_id=location_id,
                name=name,
                location_type=location_type,
                description=description,
                importance=importance,
                access_level=access_level,
                capacity=capacity,
                tags=tags,
                raw=item,
            )
            result.append(fact)

        return result, seen

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _assemble_paths(
        self,
        raw: list[Any],
        location_ids: set[str],
        warnings: list[SpatialInputWarning],
    ) -> list[PathSpatialFact]:
        seen_edge: set[tuple[str, str]] = set()
        result: list[PathSpatialFact] = []
        auto_id_counter = 0

        for idx, item in enumerate(raw):
            item = _to_dict(item)
            if not item:
                warnings.append(SpatialInputWarning(
                    code="non_dict_path",
                    message=f"path[{idx}] is not a dict; skipped",
                    source="path_graph",
                    item_index=idx,
                ))
                continue

            identity = _as_dict(item.get("identity"))
            endpoints = _as_dict(item.get("endpoints"))
            properties = _as_dict(item.get("properties"))
            conditions = _as_dict(item.get("conditions"))

            path_id = (
                _safe_str(identity.get("id"))
                or _safe_str(item.get("id"))
                or ""
            )
            if not path_id:
                auto_id_counter += 1
                path_id = f"input_path_{auto_id_counter:04d}"
                warnings.append(SpatialInputWarning(
                    code="missing_path_id",
                    message=f"path[{idx}] has no identity.id; assigned {path_id!r}",
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))

            from_id = _safe_str(endpoints.get("from_id"))
            to_id = _safe_str(endpoints.get("to_id"))
            if not from_id or not to_id:
                warnings.append(SpatialInputWarning(
                    code="missing_path_endpoint",
                    message=f"path {path_id!r} missing from_id or to_id; skipped",
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))
                continue

            if from_id not in location_ids:
                warnings.append(SpatialInputWarning(
                    code="unknown_path_endpoint",
                    message=f"path {path_id!r} from_id {from_id!r} not in locations; skipped",
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))
                continue
            if to_id not in location_ids:
                warnings.append(SpatialInputWarning(
                    code="unknown_path_endpoint",
                    message=f"path {path_id!r} to_id {to_id!r} not in locations; skipped",
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))
                continue

            if from_id == to_id:
                warnings.append(SpatialInputWarning(
                    code="self_loop_path",
                    message=f"path {path_id!r} is a self-loop; skipped",
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))
                continue

            edge_key = tuple(sorted([from_id, to_id]))
            if edge_key in seen_edge:
                warnings.append(SpatialInputWarning(
                    code="duplicate_path_pair",
                    message=(
                        f"path {path_id!r} duplicates edge "
                        f"{edge_key[0]!r} <-> {edge_key[1]!r}; skipped"
                    ),
                    source="path_graph",
                    item_index=idx,
                    item_id=path_id,
                ))
                continue
            seen_edge.add(edge_key)

            bidirectional = _safe_bool(endpoints.get("bidirectional"), default=True)
            name = _safe_str(identity.get("name")) or path_id
            path_type = _safe_str(identity.get("type"))
            access_level = _safe_str(conditions.get("access_level"))
            danger_level = _safe_str(conditions.get("danger_level"))
            movement_hint = (
                _safe_str(properties.get("travel_time"))
                or _safe_str(properties.get("distance"))
                or ""
            )
            is_secret = _infer_is_secret(
                identity.get("is_secret_passage"),
                path_type, access_level, name,
            )
            tags = _build_path_tags(path_type, access_level, danger_level, is_secret)

            fact = PathSpatialFact(
                path_id=path_id,
                from_location_id=from_id,
                to_location_id=to_id,
                name=name,
                path_type=path_type,
                bidirectional=bidirectional,
                is_secret=is_secret,
                access_level=access_level,
                danger_level=danger_level,
                movement_hint=movement_hint,
                tags=tags,
                raw=item,
            )
            result.append(fact)

        return result

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    def _assemble_characters(
        self,
        raw: list[Any],
        location_ids: set[str],
        warnings: list[SpatialInputWarning],
    ) -> list[CharacterPlacementFact]:
        result: list[CharacterPlacementFact] = []
        for idx, item in enumerate(raw):
            item = _to_dict(item)
            if not item:
                warnings.append(SpatialInputWarning(
                    code="non_dict_character",
                    message=f"character[{idx}] is not a dict; skipped",
                    source="characters",
                    item_index=idx,
                ))
                continue

            identity = _as_dict(item.get("identity"))
            state = _as_dict(item.get("state"))
            social = _as_dict(item.get("social_profile"))

            character_id = (
                _safe_str(identity.get("id"))
                or _safe_str(item.get("id"))
                or ""
            )
            if not character_id:
                warnings.append(SpatialInputWarning(
                    code="missing_character_id",
                    message=f"character[{idx}] has no identity.id; skipped",
                    source="characters",
                    item_index=idx,
                ))
                continue

            name = _safe_str(identity.get("name")) or character_id

            current_loc = (
                _safe_str(state.get("current_location_id"))
                or _safe_str(state.get("location_id"))
                or ""
            )
            home_loc = (
                _safe_str(state.get("home_location_id"))
                or _safe_str(social.get("home_location_id"))
                or ""
            )
            preferred_loc = _safe_str(state.get("preferred_location_id")) or ""

            # Validate location references — clear invalid ones, don't skip
            if current_loc and current_loc not in location_ids:
                warnings.append(SpatialInputWarning(
                    code="unknown_character_location",
                    message=(
                        f"character {character_id!r} current_location_id "
                        f"{current_loc!r} not in locations; cleared"
                    ),
                    source="characters",
                    item_index=idx,
                    item_id=character_id,
                ))
                current_loc = ""
            if home_loc and home_loc not in location_ids:
                warnings.append(SpatialInputWarning(
                    code="unknown_character_location",
                    message=(
                        f"character {character_id!r} home_location_id "
                        f"{home_loc!r} not in locations; cleared"
                    ),
                    source="characters",
                    item_index=idx,
                    item_id=character_id,
                ))
                home_loc = ""

            fact = CharacterPlacementFact(
                character_id=character_id,
                name=name,
                home_location_id=home_loc,
                current_location_id=current_loc,
                preferred_location_id=preferred_loc,
                raw=item,
            )
            result.append(fact)

        return result


# ======================================================================
# Helpers
# ======================================================================


def _to_dict(item: Any) -> dict[str, Any] | None:
    """Convert Pydantic model instance or dict to dict. Returns None if not convertible."""
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "dict"):
        return item.dict()
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return s


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "是"):
            return True
        if lowered in ("false", "0", "no", "否"):
            return False
    if value is None:
        return default
    return default


def _infer_importance(item: dict[str, Any], access_level: str) -> str:
    """Infer importance from available fields. Returns one of core/major/minor/""."""
    # Direct candidates
    identity = _as_dict(item.get("identity"))
    state = _as_dict(item.get("state"))
    for source in (item, identity, state):
        val = _safe_str(source.get("importance"))
        if val:
            return val.lower()

    # Derive from access_level
    al = access_level.lower()
    if any(kw in al for kw in ("core", "important", "核心", "重要")):
        return "core"
    if any(kw in al for kw in ("major", "主要")):
        return "major"
    if any(kw in al for kw in ("minor", "次要", "辅助")):
        return "minor"

    return ""


def _infer_is_secret(
    raw_value: Any,
    path_type: str,
    access_level: str,
    name: str,
) -> bool:
    """Check if a path is a secret passage."""
    if _safe_bool(raw_value, default=None) is True:
        return True
    for field in (path_type, access_level, name):
        lowered = field.lower()
        if any(kw in lowered for kw in _SECRET_KEYWORDS):
            return True
    return False


def _build_location_tags(
    location_type: str,
    access_level: str,
    importance: str,
) -> list[str]:
    tags: list[str] = []
    if importance:
        tags.append(importance)
    al = access_level.lower()
    if any(kw in al for kw in _SECRET_KEYWORDS):
        tags.append("secret")
    if any(kw in al for kw in ("public", "communal", "公共", "开放")):
        tags.append("public")
    lt = location_type.lower()
    if any(kw in lt for kw in ("indoor", "室内", "hall", "room", "chamber")):
        tags.append("indoor")
    if any(kw in lt for kw in ("outdoor", "室外", "garden", "forest", "yard")):
        tags.append("outdoor")
    return tags


def _build_path_tags(
    path_type: str,
    access_level: str,
    danger_level: str,
    is_secret: bool,
) -> list[str]:
    tags: list[str] = []
    if is_secret:
        tags.append("secret")
    dl = danger_level.lower()
    if any(kw in dl for kw in ("danger", "high", "危险", "致命")):
        tags.append("dangerous")
    al = access_level.lower()
    if any(kw in al for kw in ("blocked", "封", "阻断")):
        tags.append("blocked")
    return tags
