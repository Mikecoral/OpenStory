from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from worldkernel.architect.init.models import InitBuildContext
from worldkernel.architect.semantic.models import (
    ReferenceIndex,
    SemanticDomainArtifact,
    SemanticGenerationReport,
    SemanticManifest,
)
from worldkernel.architect.semantic.state import SemanticGenerationState


ARTIFACT_DOMAIN_PATHS = {
    "location_profile": ("locations", "locations.json"),
    "character_profile": ("characters", "characters.json"),
    "path_edge": ("path_graph", "path_graph.json"),
    "relation_edge": ("relation_graph", "relation_graph.json"),
}


def _default_output_root(world_id: str) -> Path:
    worldkernel_root = Path(__file__).resolve().parents[4]
    return worldkernel_root / "worlds" / "generated" / world_id / "stage2" / "semantic"


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _extract_item_id(item: Any) -> str | None:
    if isinstance(item, BaseModel):
        if hasattr(item, "id"):
            return getattr(item, "id")
        identity = getattr(item, "identity", None)
        if identity is not None and hasattr(identity, "id"):
            return getattr(identity, "id")
        item = item.model_dump(mode="json")
    if isinstance(item, dict):
        if isinstance(item.get("id"), str):
            return item["id"]
        identity = item.get("identity")
        if isinstance(identity, dict) and isinstance(identity.get("id"), str):
            return identity["id"]
    return None


def _build_domain_artifact(
    generation_state: SemanticGenerationState,
    artifact_type: str,
) -> SemanticDomainArtifact:
    results = generation_state.result_store.list_by_artifact_type(artifact_type)
    items: list[Any] = []
    produced_refs: list[str] = []
    warnings: list[str] = []
    source_ids: list[str] = []
    upstream_step_ids: list[str] = []

    for step_id, result in generation_state.result_store.iter_results():
        if result.artifact_type != artifact_type:
            continue
        items.extend(result.items)
        produced_refs.extend(result.produced_refs)
        warnings.extend(result.warnings)
        source_id = str(result.provenance.get("source_id", "primary"))
        if source_id not in source_ids:
            source_ids.append(source_id)
        upstream_step_ids.append(step_id)

    return SemanticDomainArtifact(
        artifact_type=artifact_type,
        items=_to_jsonable(items),
        source_ids=source_ids,
        produced_refs=produced_refs,
        upstream_step_ids=upstream_step_ids,
        warnings=warnings,
        provenance={"result_count": len(results)},
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_reference_index(domain_artifacts: dict[str, SemanticDomainArtifact]) -> ReferenceIndex:
    index = ReferenceIndex()
    for artifact_type, domain_artifact in domain_artifacts.items():
        for item in domain_artifact.items:
            item_id = _extract_item_id(item)
            if not item_id:
                continue
            if artifact_type == "location_profile":
                index.location_ids.append(item_id)
            elif artifact_type == "character_profile":
                index.character_ids.append(item_id)
            elif artifact_type == "path_edge":
                index.path_edge_ids.append(item_id)
            elif artifact_type == "relation_edge":
                index.relation_edge_ids.append(item_id)
            index.artifact_domain_by_id[item_id] = artifact_type
    return index


def _build_debug_snapshot(generation_state: SemanticGenerationState) -> dict[str, Any]:
    results = {}
    for step_id, result in generation_state.result_store.iter_results():
        results[step_id] = {
            "artifact_type": result.artifact_type,
            "items": _to_jsonable(result.items),
            "produced_refs": result.produced_refs,
            "warnings": result.warnings,
            "provenance": result.provenance,
        }
    return {
        "execution_order": generation_state.execution_order,
        "completed_steps": generation_state.completed_steps,
        "failed_step_id": generation_state.failed_step_id,
        "warnings": generation_state.warnings,
        "errors": generation_state.errors,
        "results": results,
    }


def save_semantic_artifacts(
    world_id: str,
    init_context: InitBuildContext,
    generation_state: SemanticGenerationState,
    output_root: str | Path | None = None,
    debug: bool = False,
) -> SemanticGenerationReport:
    root = Path(output_root) if output_root is not None else _default_output_root(world_id)
    metadata_dir = root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    domain_artifacts = {
        artifact_type: _build_domain_artifact(generation_state, artifact_type)
        for artifact_type in ARTIFACT_DOMAIN_PATHS
    }

    artifact_files: dict[str, str] = {}
    counts: dict[str, int] = {}
    for artifact_type, domain_artifact in domain_artifacts.items():
        folder_name, file_name = ARTIFACT_DOMAIN_PATHS[artifact_type]
        target_path = root / folder_name / file_name
        _write_json(target_path, domain_artifact.model_dump(mode="json"))
        artifact_files[artifact_type] = str(target_path.relative_to(root))
        counts[artifact_type] = len(domain_artifact.items)

    manifest = SemanticManifest(
        world_id=world_id,
        source_ids=[init_context.world_background.source_id],
        artifact_files=artifact_files,
        counts=counts,
        constraints=init_context.world_background.world_constraints,
        provenance={
            "stage1_inputs": init_context.provenance,
            "world_background": init_context.world_background.provenance,
        },
    )
    reference_index = _build_reference_index(domain_artifacts)
    report = SemanticGenerationReport(
        world_id=world_id,
        success=generation_state.failed_step_id is None,
        source_ids=[init_context.world_background.source_id],
        execution_order=generation_state.execution_order,
        completed_steps=generation_state.completed_steps,
        failed_step_id=generation_state.failed_step_id,
        warnings=generation_state.warnings,
        errors=generation_state.errors,
        artifact_files=artifact_files,
        counts=counts,
        provenance={
            "stage1_inputs": init_context.provenance,
            "world_background": init_context.world_background.provenance,
        },
    )

    _write_json(metadata_dir / "semantic_manifest.json", manifest.model_dump(mode="json"))
    _write_json(metadata_dir / "reference_index.json", reference_index.model_dump(mode="json"))
    _write_json(metadata_dir / "generation_report.json", report.model_dump(mode="json"))

    if debug:
        debug_dir = metadata_dir / "debug"
        init_context_path = debug_dir / "init_context.debug.json"
        generation_state_path = debug_dir / "generation_state.debug.json"
        _write_json(init_context_path, init_context.model_dump(mode="json"))
        _write_json(generation_state_path, _build_debug_snapshot(generation_state))
        report.debug_files = {
            "init_context": str(init_context_path.relative_to(root)),
            "generation_state": str(generation_state_path.relative_to(root)),
        }
        _write_json(metadata_dir / "generation_report.json", report.model_dump(mode="json"))

    return report
