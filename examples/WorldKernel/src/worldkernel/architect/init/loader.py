from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worldkernel.architect.init.models import (
    ArtifactManifest,
    ExecutionPlanArtifact,
    InstanceSeedCatalogArtifact,
    SchemaManifestArtifact,
    Stage1ArtifactBundle,
    WorldBackgroundArtifact,
    WorldTemplateArtifact,
)


class InitInputLoadError(Exception):
    pass


class InitInputLoader:
    ARTIFACT_MANIFEST_REL_PATH = Path("generated") / "artifact_manifest.json"
    WORLD_BACKGROUND_REL_PATH = Path("generated") / "plan" / "world_background.json"
    EXECUTION_PLAN_REL_PATH = Path("generated") / "plan" / "execution_plan.json"
    SEED_CATALOG_REL_PATH = Path("generated") / "plan" / "instance_seed_catalog.json"
    WORLD_TEMPLATE_REL_PATH = Path("generated") / "world_template.json"
    SCHEMA_MANIFEST_REL_PATH = Path("models") / "schema_manifest.json"

    @classmethod
    def from_session_root(
        cls,
        session_root: str | Path,
        source_id: str = "primary",
        world_id: str | None = None,
    ) -> Stage1ArtifactBundle:
        root = Path(session_root)
        manifest_path = root / cls.ARTIFACT_MANIFEST_REL_PATH
        if manifest_path.exists():
            return cls.from_manifest_path(
                manifest_path=manifest_path,
                source_id=source_id,
                world_id=world_id,
                provenance={"session_root": str(root)},
            )
        return cls.from_paths(
            world_background_path=root / cls.WORLD_BACKGROUND_REL_PATH,
            execution_plan_path=root / cls.EXECUTION_PLAN_REL_PATH,
            seed_catalog_path=root / cls.SEED_CATALOG_REL_PATH,
            world_template_path=root / cls.WORLD_TEMPLATE_REL_PATH,
            schema_manifest_path=root / cls.SCHEMA_MANIFEST_REL_PATH,
            source_id=source_id,
            world_id=world_id,
            provenance={"session_root": str(root)},
        )

    @classmethod
    def from_manifest_path(
        cls,
        manifest_path: str | Path,
        source_id: str = "primary",
        world_id: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> Stage1ArtifactBundle:
        manifest_file = Path(manifest_path)
        manifest = cls._read_model(manifest_file, ArtifactManifest, "artifact_manifest")
        session_root = manifest_file.parent.parent
        return cls.from_paths(
            world_background_path=session_root / manifest.world_background_path,
            execution_plan_path=session_root / manifest.execution_plan_path,
            seed_catalog_path=session_root / manifest.instance_seed_catalog_path,
            world_template_path=(session_root / manifest.world_template_path) if manifest.world_template_path else None,
            schema_manifest_path=(session_root / manifest.schema_manifest_path) if manifest.schema_manifest_path else None,
            source_id=source_id,
            world_id=world_id or manifest.world_id,
            provenance={
                "artifact_manifest_path": str(manifest_file),
                "session_root": str(session_root),
                **manifest.provenance,
                **(provenance or {}),
            },
        )

    @classmethod
    def from_paths(
        cls,
        world_background_path: str | Path,
        execution_plan_path: str | Path,
        seed_catalog_path: str | Path,
        world_template_path: str | Path | None = None,
        schema_manifest_path: str | Path | None = None,
        source_id: str = "primary",
        world_id: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> Stage1ArtifactBundle:
        world_background_file = Path(world_background_path)
        execution_plan_file = Path(execution_plan_path)
        seed_catalog_file = Path(seed_catalog_path)

        world_background = cls._read_model(world_background_file, WorldBackgroundArtifact, "world_background")
        execution_plan = cls._read_model(execution_plan_file, ExecutionPlanArtifact, "execution_plan")
        seed_catalog = cls._read_model(seed_catalog_file, InstanceSeedCatalogArtifact, "seed_catalog")

        world_template = None
        if world_template_path is not None and Path(world_template_path).exists():
            world_template = cls._read_model(Path(world_template_path), WorldTemplateArtifact, "world_template")

        schema_manifest = None
        if schema_manifest_path is not None and Path(schema_manifest_path).exists():
            schema_manifest = cls._read_model(Path(schema_manifest_path), SchemaManifestArtifact, "schema_manifest")

        resolved_world_id = world_id or seed_catalog.session_id or world_background.world_name or source_id
        shared_provenance = {
            "world_background_path": str(world_background_file),
            "execution_plan_path": str(execution_plan_file),
            "seed_catalog_path": str(seed_catalog_file),
            **({"world_template_path": str(world_template_path)} if world_template_path else {}),
            **({"schema_manifest_path": str(schema_manifest_path)} if schema_manifest_path else {}),
            **(provenance or {}),
        }
        world_background = world_background.model_copy(
            update={
                "world_id": resolved_world_id,
                "source_id": source_id,
                "provenance": {"artifact": "world_background", **shared_provenance},
            }
        )
        execution_plan = execution_plan.model_copy(
            update={"provenance": {"artifact": "execution_plan", **shared_provenance}}
        )
        seed_catalog = seed_catalog.model_copy(
            update={"provenance": {"artifact": "instance_seed_catalog", **shared_provenance}}
        )
        if world_template is not None:
            world_template = world_template.model_copy(
                update={"provenance": {"artifact": "world_template", **shared_provenance}}
            )
        if schema_manifest is not None:
            schema_manifest = schema_manifest.model_copy(
                update={"provenance": {"artifact": "schema_manifest", **shared_provenance}}
            )

        return Stage1ArtifactBundle(
            world_background=world_background,
            execution_plan=execution_plan,
            seed_catalog=seed_catalog,
            schema_manifest=schema_manifest,
            world_template=world_template,
            world_id=resolved_world_id,
            source_id=source_id,
            provenance=shared_provenance,
        )

    @staticmethod
    def _read_json_object(path: Path, label: str) -> dict[str, Any]:
        if not path.exists():
            raise InitInputLoadError(f"missing {label} file: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InitInputLoadError(f"invalid JSON in {label}: {path}") from exc
        if not isinstance(data, dict):
            raise InitInputLoadError(f"{label} must be a JSON object: {path}")
        return data

    @classmethod
    def _read_model(cls, path: Path, model_type, label: str):
        payload = cls._read_json_object(path, label)
        try:
            return model_type.model_validate(payload)
        except Exception as exc:
            raise InitInputLoadError(f"invalid {label} structure: {path}") from exc


def load_stage1_artifacts_from_manifest(
    manifest_path: str | Path,
    source_id: str = "primary",
    world_id: str | None = None,
) -> Stage1ArtifactBundle:
    return InitInputLoader.from_manifest_path(
        manifest_path=manifest_path,
        source_id=source_id,
        world_id=world_id,
    )
