from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InitialWorldPatch(BaseModel):
    world_id: str
    world_background: dict[str, Any] = Field(default_factory=dict)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    spatial: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class AgentKernelAdapterResult(BaseModel):
    world_id: str
    project_root: str
    entrypoint: str
    manifest_path: str
    counts: dict[str, int] = Field(default_factory=dict)
    data_paths: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    dry_validation_passed: bool = False
