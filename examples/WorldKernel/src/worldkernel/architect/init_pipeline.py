from __future__ import annotations

from pathlib import Path

from worldkernel.architect.init_compilers import ContractCompiler, ExecutionDAGCompiler, SeedResolver
from worldkernel.architect.init_loader import InitInputLoader
from worldkernel.architect.init_models import InitBuildContext
from worldkernel.architect.registries import SchemaRegistry, ToolRegistry


def compile_stage1_init_context(
    session_root: str | Path,
    schema_registry: SchemaRegistry,
    tool_registry: ToolRegistry,
    source_id: str = "primary",
    world_id: str | None = None,
) -> InitBuildContext:
    bundle = InitInputLoader.from_session_root(
        session_root=session_root,
        source_id=source_id,
        world_id=world_id,
    )
    world_background = ContractCompiler().compile(bundle)
    execution_dag = ExecutionDAGCompiler(tool_registry).compile(bundle)
    resolved_location_seeds, resolved_character_seeds = SeedResolver().resolve(bundle)
    return InitBuildContext(
        world_background=world_background,
        execution_dag=execution_dag,
        resolved_location_seeds=resolved_location_seeds,
        resolved_character_seeds=resolved_character_seeds,
        provenance={
            "source": "stage1.init_compile_pipeline",
            "source_id": source_id,
            "world_id": bundle.world_id,
            **bundle.provenance,
        },
    )
