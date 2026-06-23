from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolArtifactEnvelope(BaseModel):
    artifact_type: str
    items: list[Any] = Field(default_factory=list)
    produced_refs: list[str] = Field(default_factory=list)
    source_id: str = "primary"
    step_id: str = ""
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SemanticDomainArtifact(BaseModel):
    artifact_type: str
    items: list[Any] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    produced_refs: list[str] = Field(default_factory=list)
    upstream_step_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class FoundationBundle(BaseModel):
    world_id: str
    locations: list[Any] = Field(default_factory=list)
    characters: list[Any] = Field(default_factory=list)
    path_graph: list[Any] = Field(default_factory=list)
    relation_graph: list[Any] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SemanticManifest(BaseModel):
    world_id: str
    source_ids: list[str] = Field(default_factory=list)
    schema_version: str = "stage2-semantic-v1"
    artifact_files: dict[str, str] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_timestamp)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ReferenceIndex(BaseModel):
    location_ids: list[str] = Field(default_factory=list)
    character_ids: list[str] = Field(default_factory=list)
    path_edge_ids: list[str] = Field(default_factory=list)
    relation_edge_ids: list[str] = Field(default_factory=list)
    artifact_domain_by_id: dict[str, str] = Field(default_factory=dict)


class SemanticGenerationReport(BaseModel):
    world_id: str
    success: bool = False
    source_ids: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    failed_step_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    artifact_files: dict[str, str] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utc_timestamp)
    debug_files: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
