from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worldkernel.architect.init_models import RawStage1Bundle


class InitInputLoadError(Exception):
    pass


class InitInputLoader:
    WORLD_BACKGROUND_REL_PATH = Path("generated") / "plan" / "world_background.json"
    EXECUTION_PLAN_REL_PATH = Path("generated") / "plan" / "execution_plan.json"
    SEED_CATALOG_REL_PATH = Path("generated") / "plan" / "instance_seed_catalog.json"

    @classmethod
    def from_session_root(
        cls,
        session_root: str | Path,
        source_id: str = "primary",
        world_id: str | None = None,
    ) -> RawStage1Bundle:
        root = Path(session_root)
        return cls.from_paths(
            world_background_path=root / cls.WORLD_BACKGROUND_REL_PATH,
            execution_plan_path=root / cls.EXECUTION_PLAN_REL_PATH,
            seed_catalog_path=root / cls.SEED_CATALOG_REL_PATH,
            source_id=source_id,
            world_id=world_id,
            provenance={"session_root": str(root)},
        )

    @classmethod
    def from_paths(
        cls,
        world_background_path: str | Path,
        execution_plan_path: str | Path,
        seed_catalog_path: str | Path,
        source_id: str = "primary",
        world_id: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> RawStage1Bundle:
        world_background_file = Path(world_background_path)
        execution_plan_file = Path(execution_plan_path)
        seed_catalog_file = Path(seed_catalog_path)

        world_background = cls._read_json_object(world_background_file, "world_background")
        execution_plan = cls._read_json_object(execution_plan_file, "execution_plan")
        seed_catalog = cls._read_json_object(seed_catalog_file, "seed_catalog")
        cls._validate_raw_shapes(world_background, execution_plan, seed_catalog)

        resolved_world_id = world_id or str(seed_catalog.get("session_id") or world_background.get("world_name") or source_id)
        return RawStage1Bundle(
            world_background=world_background,
            execution_plan=execution_plan,
            seed_catalog=seed_catalog,
            world_id=resolved_world_id,
            source_id=source_id,
            provenance={
                "world_background_path": str(world_background_file),
                "execution_plan_path": str(execution_plan_file),
                "seed_catalog_path": str(seed_catalog_file),
                **(provenance or {}),
            },
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

    @staticmethod
    def _validate_raw_shapes(
        world_background: dict[str, Any],
        execution_plan: dict[str, Any],
        seed_catalog: dict[str, Any],
    ) -> None:
        if "world_constraints" not in world_background:
            raise InitInputLoadError("world_background missing required field: world_constraints")
        steps = execution_plan.get("steps")
        if not isinstance(steps, list):
            raise InitInputLoadError("execution_plan.steps must be a list")
        seeds = seed_catalog.get("instance_seeds")
        if not isinstance(seeds, dict):
            raise InitInputLoadError("seed_catalog.instance_seeds must be an object")
