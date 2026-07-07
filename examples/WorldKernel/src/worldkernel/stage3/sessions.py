from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_stage2_semantic_manifest(session_dir: Path) -> Path | None:
    for path in [
        session_dir / "generated" / "artifacts" / "semantic" / "metadata" / "semantic_manifest.json",
        session_dir / "generated" / "artifacts" / "metadata" / "semantic_manifest.json",
    ]:
        if path.exists():
            return path
    return None


def find_stage2_spatial_blueprint(session_dir: Path) -> Path | None:
    for path in [
        session_dir / "generated" / "artifacts" / "spatial" / "spatial_blueprint.json",
        session_dir / "generated" / "stage2" / "spatial" / "spatial_blueprint.json",
    ]:
        if path.exists():
            return path
    return None


def build_stage3_session_summary(session_dir: Path) -> dict[str, Any] | None:
    semantic_manifest_path = find_stage2_semantic_manifest(session_dir)
    spatial_blueprint_path = find_stage2_spatial_blueprint(session_dir)
    if semantic_manifest_path is None or spatial_blueprint_path is None:
        return None

    try:
        semantic_manifest = read_json_file(semantic_manifest_path)
        spatial_blueprint = read_json_file(spatial_blueprint_path)
    except (OSError, json.JSONDecodeError):
        return None

    world_background: dict[str, Any] = {}
    world_background_path = session_dir / "generated" / "plan" / "world_background.json"
    if world_background_path.exists():
        try:
            loaded_background = read_json_file(world_background_path)
            if isinstance(loaded_background, dict):
                world_background = loaded_background
        except (OSError, json.JSONDecodeError):
            world_background = {}

    artifact_files = semantic_manifest.get("artifact_files", {})
    if not isinstance(artifact_files, dict):
        artifact_files = {}
    semantic_root = semantic_manifest_path.parent.parent
    counts = {
        "characters": _count_artifact_items(semantic_root, artifact_files, "character_profile"),
        "locations": _count_artifact_items(semantic_root, artifact_files, "location_profile"),
        "paths": _count_artifact_items(semantic_root, artifact_files, "path_edge"),
        "relations": _count_artifact_items(semantic_root, artifact_files, "relation_edge"),
        "regions": len(spatial_blueprint.get("regions", [])),
        "routes": len(spatial_blueprint.get("routes", [])),
        "spawn_points": len(spatial_blueprint.get("spawn_points", [])),
    }

    return {
        "session_id": session_dir.name,
        "world_id": semantic_manifest.get("world_id") or spatial_blueprint.get("world_id") or session_dir.name,
        "world_name": world_background.get("world_name") or session_dir.name,
        "theme": world_background.get("theme", ""),
        "simulation_start": world_background.get("simulation_start", {}),
        "counts": counts,
        "modified_at": _get_session_modified_at(session_dir),
    }


def list_stage3_ready_session_summaries(templates_dir: Path) -> list[dict[str, Any]]:
    if not templates_dir.exists():
        return []

    sessions = [
        summary
        for session_dir in templates_dir.iterdir()
        if session_dir.is_dir()
        for summary in [build_stage3_session_summary(session_dir)]
        if summary is not None
    ]
    sessions.sort(key=lambda item: item["modified_at"], reverse=True)
    return sessions


def _count_artifact_items(semantic_root: Path, artifact_files: dict[str, str], key: str) -> int:
    rel_path = artifact_files.get(key)
    if not rel_path:
        return 0
    path = semantic_root / rel_path
    if not path.exists():
        return 0
    try:
        data = read_json_file(path)
    except (OSError, json.JSONDecodeError):
        return 0
    items = data.get("items", [])
    return len(items) if isinstance(items, list) else 0


def _get_session_modified_at(session_dir: Path) -> float:
    mtimes = [session_dir.stat().st_mtime]
    for pattern in [
        "generated/plan/world_background.json",
        "generated/artifacts/**/semantic_manifest.json",
        "generated/artifacts/**/spatial_blueprint.json",
    ]:
        mtimes.extend(path.stat().st_mtime for path in session_dir.glob(pattern) if path.is_file())
    return max(mtimes)
