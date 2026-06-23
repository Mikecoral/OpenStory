from __future__ import annotations

import asyncio
from typing import Any

from worldkernel.architect.init.models import ExecutionDAG, ExecutionDAGNode, InitBuildContext
from worldkernel.architect.registry.core import SchemaRegistry, ToolRegistry
from worldkernel.architect.semantic.state import SemanticGenerationState
from worldkernel.architect.tools.base import Stage2ToolContext, Stage2ToolRequest, Stage2ToolResult
from worldkernel.architect.tools.identity_allocator import IdentityAllocator, IdentityRegistry


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
        identity_registry: IdentityRegistry | None = None,
    ) -> None:
        self._schema_registry = schema_registry
        self._tool_registry = tool_registry
        self._dependency_resolver = dependency_resolver or StepDependencyResolver()
        self._identity_registry = identity_registry

    async def run_async(self, init_context: InitBuildContext) -> SemanticGenerationState:
        nodes_by_id = {node.step_id: node for node in init_context.execution_dag.nodes}
        state = SemanticGenerationState(
            execution_order=list(init_context.execution_dag.execution_order),
            provenance={
                "world_id": init_context.world_background.world_id,
                "source_id": init_context.world_background.source_id,
            },
        )

        registry = self._identity_registry or IdentityRegistry(
            IdentityAllocator(IdentityAllocator.to_slug(init_context.world_background.world_id or "world"))
        )

        # Pre-register all seeds before any generation.
        # All entity IDs are determined here, before any LLM call.
        registry.register_batch(init_context.resolved_location_seeds, "loc")
        registry.register_batch(init_context.resolved_character_seeds, "char")

        waves = self._topological_waves(init_context.execution_dag)
        # Derive deterministic flat execution order from waves
        state.execution_order = [sid for wave in waves for sid in wave]

        for wave in waves:
            tasks = [
                self._execute_step(step_id, nodes_by_id, state, init_context, registry)
                for step_id in wave
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Record completed steps in wave order (deterministic),
            # not in LLM-return order.
            # Process ALL results before failing — successful results are
            # preserved even when a sibling in the same wave fails.
            for step_id, result in zip(wave, results):
                if isinstance(result, Exception):
                    state.failed_step_id = step_id
                    state.errors.append(f"{step_id}: {result}")
                else:
                    await state.result_store.add_result(step_id, result)
                    state.completed_steps.append(step_id)
                    state.warnings.extend(result.warnings)

            if state.failed_step_id is not None:
                return state

        return state

    async def _execute_step(
        self,
        step_id: str,
        nodes_by_id: dict[str, ExecutionDAGNode],
        state: SemanticGenerationState,
        init_context: InitBuildContext,
        registry: IdentityRegistry,
    ) -> Stage2ToolResult:
        """Execute a single DAG step. Returns the result (does not mutate state)."""
        node = nodes_by_id[step_id]
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
            identity_registry=registry,
            metadata={"step_id": node.step_id, "tool_id": node.tool_id},
        )
        return await tool.run(request, context)

    @staticmethod
    def _topological_waves(dag: ExecutionDAG) -> list[list[str]]:
        """Group DAG nodes into topological waves for parallel execution.

        Nodes with no dependencies form Wave 1. Nodes whose dependencies
        are all in earlier waves form subsequent waves.

        Returns:
            List of waves, each wave is a sorted list of step_ids.
        """
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {}
        for node in dag.nodes:
            in_degree[node.step_id] = len(node.depends_on)
            for dep in node.depends_on:
                dependents.setdefault(dep, []).append(node.step_id)

        waves: list[list[str]] = []
        ready = [sid for sid, deg in in_degree.items() if deg == 0]

        while ready:
            waves.append(sorted(ready))
            next_ready: list[str] = []
            for sid in ready:
                for dep_sid in dependents.get(sid, []):
                    in_degree[dep_sid] -= 1
                    if in_degree[dep_sid] == 0:
                        next_ready.append(dep_sid)
            ready = next_ready

        return waves


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
