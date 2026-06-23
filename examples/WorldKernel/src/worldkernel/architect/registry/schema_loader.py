from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from worldkernel.architect.registry.core import (
    SchemaEntry,
    SchemaRegistry,
    SchemaRegistryError,
    SchemaSource,
    create_default_schema_registry,
)


class SchemaLoadError(SchemaRegistryError):
    pass

def load_stage1_schema_source(source: SchemaSource, registry: SchemaRegistry) -> SchemaRegistry:
    specs = _load_manifest_specs(source)
    missing: list[str] = []

    for spec in specs:
        try:
            model_type = _load_model_type(source, spec)
        except SchemaLoadError as exc:
            if not source.allow_partial:
                raise
            missing.append(str(exc))
            continue

        registry.register(
            SchemaEntry(
                alias=spec["alias"],
                version=spec.get("version", "v1"),
                model_type=model_type,
                source=source,
                canonical_name=spec.get("class_name", model_type.__name__),
                description=spec.get("description", ""),
                metadata={
                    "model_file": spec.get("file", ""),
                    "loader": "schema_manifest",
                    **spec.get("metadata", {}),
                },
            )
        )

    if missing:
        source.metadata.setdefault("missing_schemas", missing)
    registry.register_source(source)
    return registry


def load_stage1_session_schema_source(
    session_root: str | Path,
    registry: SchemaRegistry | None = None,
    source_id: str = "primary",
    world_id: str | None = None,
    world_scope: str = "",
    allow_partial: bool = False,
    metadata: dict[str, Any] | None = None,
) -> SchemaRegistry:
    session_root_path = Path(session_root)
    source = SchemaSource(
        source_id=source_id,
        world_id=world_id or session_root_path.name,
        world_scope=world_scope,
        root_dir=session_root_path,
        allow_partial=allow_partial,
        metadata=metadata or {},
    )
    target_registry = registry or create_default_schema_registry()
    return load_stage1_schema_source(source, target_registry)


def _manifest_path(source: SchemaSource) -> Path:
    return source.resolved_models_dir() / "schema_manifest.json"


def _load_manifest_specs(source: SchemaSource) -> list[dict[str, Any]]:
    manifest_path = _manifest_path(source)
    if not manifest_path.exists():
        raise SchemaLoadError(f"schema manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs = data.get("schemas")
    if not isinstance(specs, list):
        raise SchemaLoadError(f"invalid schema manifest: {manifest_path}")
    normalized: list[dict[str, Any]] = []
    for spec in specs:
        if not isinstance(spec, dict) or not spec.get("alias"):
            raise SchemaLoadError(f"invalid schema manifest entry in {manifest_path}")
        normalized.append(
            {
                "alias": spec["alias"],
                "file": spec.get("file") or spec.get("module_file"),
                "class_name": spec.get("class_name"),
                "version": spec.get("version", "v1"),
                "description": spec.get("description", ""),
                "metadata": spec.get("metadata", {}),
            }
        )
    if not normalized:
        raise SchemaLoadError(f"schema manifest has no schema entries: {manifest_path}")
    return normalized


def _load_model_type(source: SchemaSource, spec: dict[str, Any]) -> type[BaseModel]:
    model_file = spec.get("file")
    class_name = spec.get("class_name")
    if not model_file or not class_name:
        raise SchemaLoadError(f"schema spec requires file and class_name: {spec!r}")

    model_path = source.resolved_models_dir() / model_file
    if not model_path.exists():
        raise SchemaLoadError(f"schema model file not found: {model_path}")

    module = _load_module_from_path(source.source_id, spec["alias"], model_path)
    model_type = getattr(module, class_name, None)
    if model_type is None:
        raise SchemaLoadError(f"schema class '{class_name}' not found in {model_path}")
    if not isinstance(model_type, type) or not issubclass(model_type, BaseModel):
        raise SchemaLoadError(f"schema class '{class_name}' is not a Pydantic BaseModel")
    return model_type


def _load_module_from_path(source_id: str, alias: str, model_path: Path):
    digest = hashlib.sha1(str(model_path.resolve()).encode("utf-8")).hexdigest()[:12]
    module_name = f"worldkernel_dynamic_schema_{source_id}_{alias}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    if spec is None or spec.loader is None:
        raise SchemaLoadError(f"cannot import schema module: {model_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
