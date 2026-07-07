from __future__ import annotations

from pathlib import Path

from worldkernel.architect.init.compilers import ContractCompiler, ExecutionDAGCompiler, SeedResolver
from worldkernel.architect.init.loader import InitInputLoader
from worldkernel.architect.init.models import InitBuildContext, Stage1ArtifactBundle
from worldkernel.architect.registry.core import SchemaRegistry, ToolRegistry


def compile_stage1_init_context(
    bundle_or_session_root: Stage1ArtifactBundle | str | Path,
    schema_registry: SchemaRegistry | None = None,
    tool_registry: ToolRegistry | None = None,
    source_id: str = "primary",
    world_id: str | None = None,
    constraints: object | None = None,
) -> InitBuildContext:
    if isinstance(bundle_or_session_root, Stage1ArtifactBundle):
        bundle = bundle_or_session_root
        if tool_registry is None:
            raise ValueError("tool_registry is required when compiling from Stage1ArtifactBundle")
    else:
        if tool_registry is None:
            raise ValueError("tool_registry is required when compiling from session_root")
        bundle = InitInputLoader.from_session_root(
            session_root=bundle_or_session_root,
            source_id=source_id,
            world_id=world_id,
        )

    world_background = ContractCompiler().compile(bundle)
    execution_dag = ExecutionDAGCompiler(tool_registry).compile(bundle)
    resolved_location_seeds, resolved_character_seeds = SeedResolver().resolve(bundle, constraints=constraints)
    return InitBuildContext(
        world_background=world_background,
        execution_dag=execution_dag,
        resolved_location_seeds=resolved_location_seeds,
        resolved_character_seeds=resolved_character_seeds,
        provenance={
            "source": "stage1.init_compile_pipeline",
            "source_id": bundle.source_id,
            "world_id": bundle.world_id,
            **bundle.provenance,
        },
    )
