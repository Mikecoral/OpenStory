from __future__ import annotations

from worldkernel.architect.tools.base import BaseStage2Tool

from worldkernel.architect.tools.generators.character_generator import CharacterGenerationTool
from worldkernel.architect.tools.generators import LocationGenerationTool

__all__ = [
    "CharacterGenerationTool",
    "LocationGenerationTool",
    "PathGenerationTool",
    "PathGraphTool",
    "RelationGenerationTool",
    "RelationGraphTool",
]

class PathGraphTool(BaseStage2Tool):
    tool_id = "stage2.path_generator.v1"
    generator_type = "path_generator"
    output_schema_alias = "path_edge"
    capabilities = ("generate_paths",)


class RelationGraphTool(BaseStage2Tool):
    tool_id = "stage2.relation_generator.v1"
    generator_type = "relation_generator"
    output_schema_alias = "relation_edge"
    capabilities = ("generate_relations",)


# Backward-compatible aliases for earlier naming.
PathGenerationTool = PathGraphTool
RelationGenerationTool = RelationGraphTool