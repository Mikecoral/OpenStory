"""Converts FoundationBundle to SpatialBuildInput without disk I/O."""

from __future__ import annotations

from worldkernel.architect.semantic.models import FoundationBundle
from worldkernel.architect.spatial.input_assembler import SpatialInputAssembler
from worldkernel.architect.spatial.models import SpatialBuildInput


class SpatialPipelineAdapter:
    """Bridges semantic layer output to spatial layer input in-memory."""

    @staticmethod
    def from_foundation_bundle(bundle: FoundationBundle) -> SpatialBuildInput:
        """Convert in-memory FoundationBundle to SpatialBuildInput.

        Reuses the field extraction logic from SpatialInputAssembler but
        reads directly from bundle attributes instead of loading from disk.
        """
        assembler = SpatialInputAssembler()
        warnings: list = []

        locations, location_ids = assembler._assemble_locations(bundle.locations, warnings)
        paths = assembler._assemble_paths(bundle.path_graph, location_ids, warnings)
        characters = assembler._assemble_characters(bundle.characters, location_ids, warnings)

        return SpatialBuildInput(
            world_id=bundle.world_id,
            source_root="(in-memory:FoundationBundle)",
            locations=locations,
            paths=paths,
            characters=characters,
            warnings=warnings,
            provenance={
                "source": "foundation_bundle",
                "location_count_raw": len(bundle.locations),
                "location_count_kept": len(locations),
                "path_count_raw": len(bundle.path_graph),
                "path_count_kept": len(paths),
                "character_count_raw": len(bundle.characters),
                "character_count_kept": len(characters),
            },
        )