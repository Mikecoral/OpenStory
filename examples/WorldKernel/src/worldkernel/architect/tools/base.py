from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from worldkernel.architect.init.models import (
    CompiledWorldBackground,
    ExecutionDAGNode,
    ResolvedSeed,
)
from worldkernel.architect.tools.identity_allocator import IdentityRegistry


@runtime_checkable
class SeedReuseProvider(Protocol):
    """Protocol for seed-based profile reuse from a parent world.

    Implementations check whether a seed_id has a previously generated
    profile that can be reused, avoiding redundant LLM generation in
    sub-world scenarios.
    """

    def check_reuse(self, seed_id: str, entity_type: str) -> Stage2ToolResult | None: ...


class Stage2ToolContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_registry: Any
    source_id: str = "primary"
    world_id: str = ""
    identity_registry: IdentityRegistry | None = None
    seed_reuse_provider: Any | None = None  # SeedReuseProvider (Any to avoid Pydantic Protocol issues)
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

    @property
    def upstream_locations(self) -> list[Any]:
        """Extract location items from upstream artifacts (for PathTool).

        Matches by artifact_type rather than step_id key, so it works
        regardless of how the DAG names its steps.
        """
        for result in self.upstream_artifacts.values():
            if hasattr(result, "artifact_type") and result.artifact_type == "location_profile":
                return result.items if hasattr(result, "items") else []
        return []

    @property
    def upstream_characters(self) -> list[Any]:
        """Extract character items from upstream artifacts (for RelationTool)."""
        for result in self.upstream_artifacts.values():
            if hasattr(result, "artifact_type") and result.artifact_type == "character_profile":
                return result.items if hasattr(result, "items") else []
        return []


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
