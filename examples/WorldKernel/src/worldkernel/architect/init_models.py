from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RawStage1Bundle(BaseModel):
    world_background: dict[str, Any]
    execution_plan: dict[str, Any]
    seed_catalog: dict[str, Any]
    world_id: str
    source_id: str = "primary"
    provenance: dict[str, Any] = Field(default_factory=dict)


class CompiledWorldBackground(BaseModel):
    world_id: str
    source_id: str = "primary"
    world_name: str = ""
    world_origin_summary: str = ""
    primary: str = ""
    secondary: str | None = None
    tags: list[str] = Field(default_factory=list)
    scope: str = ""
    simulation_start: dict[str, Any] = Field(default_factory=dict)
    world_constraints: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ExecutionDAGNode(BaseModel):
    step_id: str
    generator_type: str
    target_entity_type: str
    batch_size: int = 1
    priority: int = 1
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    tool_id: str = ""
    output_schema_alias: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)


class ExecutionDAG(BaseModel):
    nodes: list[ExecutionDAGNode] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ResolvedSeed(BaseModel):
    seed_id: str
    entity_type: str
    archetype_id: str
    name: str = ""
    importance: str = ""
    source_type: str = ""
    confidence: float = 0.0
    priority: int = 1
    role_in_world: str = ""
    stable_seed_ref: str
    source: str = "stage1_seed_catalog"
    provenance: dict[str, Any] = Field(default_factory=dict)


class InitBuildContext(BaseModel):
    world_background: CompiledWorldBackground
    execution_dag: ExecutionDAG
    resolved_location_seeds: list[ResolvedSeed] = Field(default_factory=list)
    resolved_character_seeds: list[ResolvedSeed] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
