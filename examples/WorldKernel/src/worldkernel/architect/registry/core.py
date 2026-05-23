from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from worldkernel.architect.tools.base import BaseStage2Tool
from worldkernel.architect.tools.generation import (
    CharacterGenerationTool,
    LocationGenerationTool,
    PathGraphTool,
    RelationGraphTool,
)


DEFAULT_SCHEMA_ALIASES = {
    "location_profile",
    "character_profile",
    "path_edge",
    "relation_edge",
}


class RegistryError(Exception):
    """Base class for Stage2 dependency registry errors."""


class SchemaRegistryError(RegistryError):
    pass


class SchemaNotFoundError(SchemaRegistryError):
    pass


class SchemaAmbiguityError(SchemaRegistryError):
    pass


class ToolRegistryError(RegistryError):
    pass


class ToolNotFoundError(ToolRegistryError):
    pass


class SchemaSource(BaseModel):
    source_id: str
    world_id: str | None = None
    world_scope: str = ""
    root_dir: Path | None = None
    models_dir: Path | None = None
    configs_dir: Path | None = None
    allow_partial: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def resolved_models_dir(self) -> Path:
        if self.models_dir is not None:
            return self.models_dir
        if self.root_dir is None:
            raise SchemaRegistryError("SchemaSource requires models_dir or root_dir")
        return self.root_dir / "models"

    def resolved_configs_dir(self) -> Path | None:
        if self.configs_dir is not None:
            return self.configs_dir
        if self.root_dir is None:
            return None
        return self.root_dir / "configs"


class SchemaEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    alias: str
    version: str = "v1"
    model_type: type[BaseModel]
    source: SchemaSource
    canonical_name: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def _version_key(version: str) -> tuple[int, ...] | tuple[str]:
    raw = version[1:] if version.startswith("v") else version
    parts = raw.split(".")
    if parts and all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (version,)


class SchemaRegistry:
    """Multi-source registry for Stage1 generated Pydantic schemas."""

    registry_version = "v2"

    def __init__(self, known_aliases: set[str] | None = None) -> None:
        self._known_aliases = set(known_aliases or DEFAULT_SCHEMA_ALIASES)
        self._sources: dict[str, SchemaSource] = {}
        self._entries: dict[tuple[str, str, str], SchemaEntry] = {}

    def register_source(self, source: SchemaSource) -> None:
        existing = self._sources.get(source.source_id)
        if existing is not None and existing != source:
            raise SchemaRegistryError(f"schema source already registered: {source.source_id}")
        self._sources[source.source_id] = source

    def register(self, entry: SchemaEntry) -> None:
        self.register_source(entry.source)
        key = (entry.source.source_id, entry.alias, entry.version)
        if key in self._entries:
            raise SchemaRegistryError(
                f"schema already registered: source={entry.source.source_id}, "
                f"alias={entry.alias}, version={entry.version}"
            )
        self._known_aliases.add(entry.alias)
        self._entries[key] = entry

    def has_alias(self, alias: str) -> bool:
        return alias in self._known_aliases or any(key[1] == alias for key in self._entries)

    def get(
        self,
        alias: str,
        source_id: str | None = None,
        version: str | None = None,
    ) -> SchemaEntry:
        resolved_source_id = self._resolve_source_id(alias, source_id)
        if version is not None:
            key = (resolved_source_id, alias, version)
            if key not in self._entries:
                raise SchemaNotFoundError(
                    f"schema not found: source={resolved_source_id}, alias={alias}, version={version}"
                )
            return self._entries[key]

        candidates = [
            entry
            for (entry_source_id, entry_alias, _entry_version), entry in self._entries.items()
            if entry_source_id == resolved_source_id and entry_alias == alias
        ]
        if not candidates:
            raise SchemaNotFoundError(f"schema not found: source={resolved_source_id}, alias={alias}")
        return sorted(candidates, key=lambda entry: _version_key(entry.version))[-1]

    def validate(
        self,
        alias: str,
        payload: Any,
        source_id: str | None = None,
        version: str | None = None,
    ) -> BaseModel:
        entry = self.get(alias, source_id=source_id, version=version)
        return entry.model_type.model_validate(payload)

    def list_sources(self) -> list[SchemaSource]:
        return list(self._sources.values())

    def list_entries(self, source_id: str | None = None, alias: str | None = None) -> list[SchemaEntry]:
        entries = list(self._entries.values())
        if source_id is not None:
            entries = [entry for entry in entries if entry.source.source_id == source_id]
        if alias is not None:
            entries = [entry for entry in entries if entry.alias == alias]
        return entries

    def _resolve_source_id(self, alias: str, source_id: str | None) -> str:
        if source_id is not None:
            return source_id
        matching_sources = sorted({key[0] for key in self._entries if key[1] == alias})
        if not matching_sources:
            raise SchemaNotFoundError(f"schema not found: alias={alias}")
        if len(matching_sources) > 1:
            raise SchemaAmbiguityError(
                f"schema alias '{alias}' exists in multiple sources; pass source_id explicitly"
            )
        return matching_sources[0]


class ToolRegistry:
    """Registry for callable Stage2 generator tools.

    Tools reference stable schema aliases. The concrete schema source is selected later by
    Stage2 context, which keeps this layer usable for multi-world setups.
    """

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._schema_registry = schema_registry
        self._tools_by_id: dict[str, BaseStage2Tool] = {}
        self._tools_by_generator_type: dict[str, BaseStage2Tool] = {}

    def register(self, tool: BaseStage2Tool) -> None:
        if not tool.tool_id:
            raise ToolRegistryError("tool_id is required")
        if not tool.generator_type:
            raise ToolRegistryError("generator_type is required")
        if not self._schema_registry.has_alias(tool.output_schema_alias):
            raise ToolRegistryError(f"unknown output schema alias: {tool.output_schema_alias}")
        if tool.input_schema_alias and not self._schema_registry.has_alias(tool.input_schema_alias):
            raise ToolRegistryError(f"unknown input schema alias: {tool.input_schema_alias}")
        if tool.tool_id in self._tools_by_id:
            raise ToolRegistryError(f"tool already registered: {tool.tool_id}")
        if tool.generator_type in self._tools_by_generator_type:
            raise ToolRegistryError(f"generator type already registered: {tool.generator_type}")
        self._tools_by_id[tool.tool_id] = tool
        self._tools_by_generator_type[tool.generator_type] = tool

    def get(self, tool_id: str) -> BaseStage2Tool:
        try:
            return self._tools_by_id[tool_id]
        except KeyError as exc:
            raise ToolNotFoundError(f"tool not found: {tool_id}") from exc

    def get_by_generator_type(self, generator_type: str) -> BaseStage2Tool:
        try:
            return self._tools_by_generator_type[generator_type]
        except KeyError as exc:
            raise ToolNotFoundError(f"generator type not found: {generator_type}") from exc

    def list_tools(self) -> list[BaseStage2Tool]:
        return list(self._tools_by_id.values())


def create_default_schema_registry() -> SchemaRegistry:
    return SchemaRegistry()


def create_default_tool_registry(schema_registry: SchemaRegistry) -> ToolRegistry:
    registry = ToolRegistry(schema_registry)
    for tool in (
        LocationGenerationTool(),
        CharacterGenerationTool(),
        PathGraphTool(),
        RelationGraphTool(),
    ):
        registry.register(tool)
    return registry
