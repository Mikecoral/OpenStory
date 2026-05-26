from __future__ import annotations

from worldkernel.architect.tools.base import BaseStage2Tool
from worldkernel.architect.tools.generators import LocationGenerationTool
from worldkernel.architect.tools.generators.path_generator import PathGenerationTool

__all__ = [
    "CharacterGenerationTool",
    "LocationGenerationTool",
    "PathGenerationTool",
    "PathGraphTool",
    "RelationGenerationTool",
    "RelationGraphTool",
]


class CharacterGenerationTool(BaseStage2Tool):
    tool_id = "stage2.character_generator.v1"
    generator_type = "character_generator"
    output_schema_alias = "character_profile"
    capabilities = ("generate_characters",)


class RelationGraphTool(BaseStage2Tool):
    tool_id = "stage2.relation_generator.v1"
    generator_type = "relation_generator"
    output_schema_alias = "relation_edge"
    capabilities = ("generate_relations",)


# Backward-compatible aliases for earlier naming.
PathGraphTool = PathGenerationTool
RelationGenerationTool = RelationGraphTool
