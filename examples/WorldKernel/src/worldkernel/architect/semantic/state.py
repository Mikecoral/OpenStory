from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from worldkernel.architect.semantic.models import ToolArtifactEnvelope
from worldkernel.architect.tools.base import Stage2ToolResult


class StepResultStore:
    """In-memory result store that keeps a single reference per step result.

    Thread-safe for concurrent async writers via asyncio.Lock.
    Read methods are lock-free (Python dict reads are safe between await points).
    """

    def __init__(self) -> None:
        self._results_by_step_id: dict[str, Stage2ToolResult] = {}
        self._results_by_artifact_type: dict[str, list[Stage2ToolResult]] = {}
        self._lock = asyncio.Lock()

    async def add_result(self, step_id: str, result: Stage2ToolResult) -> None:
        async with self._lock:
            self._results_by_step_id[step_id] = result
            self._results_by_artifact_type.setdefault(result.artifact_type, []).append(result)

    def get_step_result(self, step_id: str) -> Stage2ToolResult:
        return self._results_by_step_id[step_id]

    def has_step_result(self, step_id: str) -> bool:
        return step_id in self._results_by_step_id

    def list_by_artifact_type(self, artifact_type: str) -> list[Stage2ToolResult]:
        return list(self._results_by_artifact_type.get(artifact_type, []))

    def get_latest_by_artifact_type(self, artifact_type: str) -> Stage2ToolResult | None:
        results = self._results_by_artifact_type.get(artifact_type, [])
        return results[-1] if results else None

    def list_step_ids(self) -> list[str]:
        return list(self._results_by_step_id.keys())

    def iter_results(self) -> list[tuple[str, Stage2ToolResult]]:
        return list(self._results_by_step_id.items())


class SemanticGenerationState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    result_store: StepResultStore = Field(default_factory=StepResultStore)
    execution_order: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    failed_step_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


def build_artifact_envelope(
    step_id: str,
    result: Stage2ToolResult,
    source_id: str,
) -> ToolArtifactEnvelope:
    return ToolArtifactEnvelope(
        artifact_type=result.artifact_type,
        items=result.items,
        produced_refs=result.produced_refs,
        source_id=source_id,
        step_id=step_id,
        warnings=result.warnings,
        provenance=result.provenance,
    )
