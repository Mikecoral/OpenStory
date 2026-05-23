from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from worldkernel.architect.init_models import (
    CompiledWorldBackground,
    ExecutionDAGNode,
    ResolvedSeed,
)


class Stage2ToolContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_registry: Any
    source_id: str = "primary"
    world_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Stage2ToolRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_id: str = ""
    generator_type: str
    node: ExecutionDAGNode | None = None
    world_background: CompiledWorldBackground | None = None
    resolved_location_seeds: list[ResolvedSeed] = Field(default_factory=list)
    resolved_character_seeds: list[ResolvedSeed] = Field(default_factory=list)
    upstream_artifacts: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    batch_size: int = 1
    provenance: dict[str, Any] = Field(default_factory=dict)


class Stage2ToolResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    artifact_type: str
    items: list[Any] = Field(default_factory=list)
    produced_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class BaseStage2Tool:
    tool_id: str = ""
    generator_type: str = ""
    input_schema_alias: str | None = None
    output_schema_alias: str = ""
    version: str = "v1"
    capabilities: tuple[str, ...] = ()

    async def run(
        self,
        request: Stage2ToolRequest,
        context: Stage2ToolContext,
    ) -> Stage2ToolResult:
        raise NotImplementedError(f"{self.__class__.__name__}.run() is not implemented yet")
