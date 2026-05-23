from __future__ import annotations

import asyncio
from typing import Any

from worldkernel.architect.init.models import ExecutionDAGNode, InitBuildContext
from worldkernel.architect.registry.core import SchemaRegistry, ToolRegistry
from worldkernel.architect.semantic.state import SemanticGenerationState
from worldkernel.architect.tools.base import Stage2ToolContext, Stage2ToolRequest, Stage2ToolResult


class StepDependencyError(RuntimeError):
    pass


class StepDependencyResolver:
    def resolve(
        self,
        node: ExecutionDAGNode,
        state: SemanticGenerationState,
    ) -> dict[str, Stage2ToolResult]:
        upstream_artifacts: dict[str, Stage2ToolResult] = {}
        for dependency_step_id in node.depends_on:
            if not state.result_store.has_step_result(dependency_step_id):
                raise StepDependencyError(
                    f"missing upstream artifact for step '{node.step_id}': {dependency_step_id}"
                )
            upstream_artifacts[dependency_step_id] = state.result_store.get_step_result(dependency_step_id)
        return upstream_artifacts


class InitDAGRunner:
    def __init__(
        self,
        schema_registry: SchemaRegistry,
        tool_registry: ToolRegistry,
        dependency_resolver: StepDependencyResolver | None = None,
    ) -> None:
        self._schema_registry = schema_registry
        self._tool_registry = tool_registry
        self._dependency_resolver = dependency_resolver or StepDependencyResolver()

    async def run_async(self, init_context: InitBuildContext) -> SemanticGenerationState:
        nodes_by_id = {node.step_id: node for node in init_context.execution_dag.nodes}
        state = SemanticGenerationState(
            execution_order=list(init_context.execution_dag.execution_order),
            provenance={
                "world_id": init_context.world_background.world_id,
                "source_id": init_context.world_background.source_id,
            },
        )

        for step_id in init_context.execution_dag.execution_order:
            node = nodes_by_id[step_id]
            try:
                upstream_artifacts = self._dependency_resolver.resolve(node, state)
                tool = self._tool_registry.get_by_generator_type(node.generator_type)
                request = Stage2ToolRequest(
                    step_id=node.step_id,
                    generator_type=node.generator_type,
                    node=node,
                    world_background=init_context.world_background,
                    resolved_location_seeds=init_context.resolved_location_seeds,
                    resolved_character_seeds=init_context.resolved_character_seeds,
                    upstream_artifacts=upstream_artifacts,
                    batch_size=node.batch_size,
                    provenance=node.provenance,
                )
                context = Stage2ToolContext(
                    schema_registry=self._schema_registry,
                    source_id=init_context.world_background.source_id,
                    world_id=init_context.world_background.world_id,
                    metadata={"step_id": node.step_id, "tool_id": node.tool_id},
                )
                result = await tool.run(request, context)
                state.result_store.add_result(node.step_id, result)
                state.completed_steps.append(node.step_id)
                state.warnings.extend(result.warnings)
            except NotImplementedError as exc:
                state.failed_step_id = node.step_id
                state.errors.append(f"{node.step_id}: {exc}")
                break
            except Exception as exc:
                state.failed_step_id = node.step_id
                state.errors.append(f"{node.step_id}: {exc}")
                break

        return state


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("run_semantic_generation must be awaited via InitDAGRunner.run_async() inside an active event loop")


def run_semantic_generation(
    init_context: InitBuildContext,
    schema_registry: SchemaRegistry,
    tool_registry: ToolRegistry,
) -> SemanticGenerationState:
    runner = InitDAGRunner(schema_registry=schema_registry, tool_registry=tool_registry)
    return _run_async(runner.run_async(init_context))
