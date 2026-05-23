from __future__ import annotations

import re
from typing import Any

from worldkernel.architect.init.models import (
    CompiledWorldBackground,
    ExecutionDAG,
    ExecutionDAGNode,
    RawStage1Bundle,
    ResolvedSeed,
)
from worldkernel.architect.registry.core import ToolRegistry


class InitCompileError(Exception):
    pass


class ContractCompiler:
    def compile(self, bundle: RawStage1Bundle) -> CompiledWorldBackground:
        raw = bundle.world_background
        constraints = raw.get("world_constraints", [])
        if not isinstance(constraints, list):
            raise InitCompileError("world_background.world_constraints must be a list")
        simulation_start = raw.get("simulation_start", {})
        if simulation_start is None:
            simulation_start = {}
        if not isinstance(simulation_start, dict):
            raise InitCompileError("world_background.simulation_start must be an object")

        return CompiledWorldBackground(
            world_id=bundle.world_id,
            source_id=bundle.source_id,
            world_name=str(raw.get("world_name", "")),
            world_origin_summary=str(raw.get("world_origin_summary", "")),
            primary=str(raw.get("primary", "")),
            secondary=raw.get("secondary"),
            tags=list(raw.get("tags", []) or []),
            scope=str(raw.get("scope", "")),
            simulation_start=simulation_start,
            world_constraints=constraints,
            provenance={
                "source": "stage1.world_background",
                **bundle.provenance,
            },
        )


class ExecutionDAGCompiler:
    REQUIRED_TARGETS_BY_TARGET = {
        "path": ("location",),
        "relation": ("character",),
    }

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    def compile(self, bundle: RawStage1Bundle) -> ExecutionDAG:
        raw_steps = bundle.execution_plan.get("steps")
        if not isinstance(raw_steps, list):
            raise InitCompileError("execution_plan.steps must be a list")

        normalized_steps: list[tuple[int, dict[str, Any]]] = []
        seen_step_ids: set[str] = set()
        for index, step in enumerate(raw_steps):
            if not isinstance(step, dict):
                raise InitCompileError(f"execution_plan.steps[{index}] must be an object")
            step_id = str(step.get("step_id", "")).strip()
            if not step_id:
                raise InitCompileError(f"execution_plan.steps[{index}] missing step_id")
            if step_id in seen_step_ids:
                raise InitCompileError(f"duplicate execution step_id: {step_id}")
            seen_step_ids.add(step_id)
            priority = self._positive_int(step.get("priority", 1), f"step {step_id} priority")
            batch_size = self._positive_int(step.get("batch_size", 1), f"step {step_id} batch_size")
            generator_type = str(step.get("generator_type", "")).strip()
            if not generator_type:
                raise InitCompileError(f"step {step_id} missing generator_type")
            target_entity_type = str(step.get("target_entity_type", "")).strip()
            if not target_entity_type:
                raise InitCompileError(f"step {step_id} missing target_entity_type")
            self._tool_registry.get_by_generator_type(generator_type)
            normalized_steps.append(
                (
                    index,
                    {
                        **step,
                        "step_id": step_id,
                        "priority": priority,
                        "batch_size": batch_size,
                        "generator_type": generator_type,
                        "target_entity_type": target_entity_type,
                    },
                )
            )

        sorted_steps = sorted(normalized_steps, key=lambda item: (item[1]["priority"], item[0]))
        target_to_step_id: dict[str, str] = {}
        nodes: list[ExecutionDAGNode] = []
        for sorted_index, (_original_index, step) in enumerate(sorted_steps):
            target = step["target_entity_type"]
            depends_on: list[str] = []
            for required_target in self.REQUIRED_TARGETS_BY_TARGET.get(target, ()):
                dependency_step_id = target_to_step_id.get(required_target)
                if dependency_step_id is None:
                    raise InitCompileError(
                        f"step {step['step_id']} requires prior target '{required_target}'"
                    )
                depends_on.append(dependency_step_id)

            tool = self._tool_registry.get_by_generator_type(step["generator_type"])
            nodes.append(
                ExecutionDAGNode(
                    step_id=step["step_id"],
                    generator_type=step["generator_type"],
                    target_entity_type=target,
                    batch_size=step["batch_size"],
                    priority=step["priority"],
                    description=str(step.get("description", "")),
                    depends_on=depends_on,
                    tool_id=tool.tool_id,
                    output_schema_alias=tool.output_schema_alias,
                    provenance={
                        "source": "stage1.execution_plan",
                        "original_index": _original_index,
                        "execution_index": sorted_index,
                    },
                )
            )
            target_to_step_id.setdefault(target, step["step_id"])

        return ExecutionDAG(
            nodes=nodes,
            execution_order=[node.step_id for node in nodes],
            provenance={"source": "stage1.execution_plan"},
        )

    @staticmethod
    def _positive_int(value: Any, label: str) -> int:
        if isinstance(value, bool):
            raise InitCompileError(f"{label} must be a positive integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise InitCompileError(f"{label} must be a positive integer") from exc
        if parsed <= 0:
            raise InitCompileError(f"{label} must be a positive integer")
        return parsed


class SeedResolver:
    SUPPORTED_ENTITY_TYPES = ("location", "character")

    def resolve(self, bundle: RawStage1Bundle) -> tuple[list[ResolvedSeed], list[ResolvedSeed]]:
        instance_seeds = bundle.seed_catalog.get("instance_seeds")
        if not isinstance(instance_seeds, dict):
            raise InitCompileError("seed_catalog.instance_seeds must be an object")
        resolved_by_type: dict[str, list[ResolvedSeed]] = {}
        for entity_type in self.SUPPORTED_ENTITY_TYPES:
            seeds = instance_seeds.get(entity_type, [])
            if not isinstance(seeds, list):
                raise InitCompileError(f"seed_catalog.instance_seeds.{entity_type} must be a list")
            resolved_by_type[entity_type] = self._resolve_entity_seeds(bundle, entity_type, seeds)
        return resolved_by_type["location"], resolved_by_type["character"]

    def _resolve_entity_seeds(
        self,
        bundle: RawStage1Bundle,
        entity_type: str,
        seeds: list[Any],
    ) -> list[ResolvedSeed]:
        resolved: list[ResolvedSeed] = []
        seen_refs: set[str] = set()
        for index, raw_seed in enumerate(seeds):
            if not isinstance(raw_seed, dict):
                raise InitCompileError(f"{entity_type} seed at index {index} must be an object")
            seed_id = str(raw_seed.get("seed_id", "")).strip()
            archetype_id = str(raw_seed.get("archetype_id", "")).strip()
            if not seed_id:
                raise InitCompileError(f"{entity_type} seed at index {index} missing seed_id")
            if not archetype_id:
                raise InitCompileError(f"{entity_type} seed {seed_id} missing archetype_id")
            priority = ExecutionDAGCompiler._positive_int(
                raw_seed.get("generation_priority", 1),
                f"{entity_type} seed {seed_id} generation_priority",
            )
            stable_seed_ref = build_stable_seed_ref(
                world_id=bundle.world_id,
                source_id=bundle.source_id,
                entity_type=entity_type,
                archetype_id=archetype_id,
                seed_id=seed_id,
            )
            if stable_seed_ref in seen_refs:
                raise InitCompileError(f"duplicate resolved seed ref: {stable_seed_ref}")
            seen_refs.add(stable_seed_ref)
            resolved.append(
                ResolvedSeed(
                    seed_id=seed_id,
                    entity_type=entity_type,
                    archetype_id=archetype_id,
                    name=str(raw_seed.get("name", "")),
                    importance=str(raw_seed.get("importance", "")),
                    source_type=str(raw_seed.get("source_type", "")),
                    confidence=float(raw_seed.get("confidence", 0.0) or 0.0),
                    priority=priority,
                    role_in_world=str(raw_seed.get("role_in_world", "")),
                    stable_seed_ref=stable_seed_ref,
                    provenance={
                        "source": "stage1.instance_seed_catalog",
                        "seed_index": index,
                    },
                )
            )
        return resolved


def build_stable_seed_ref(
    world_id: str,
    source_id: str,
    entity_type: str,
    archetype_id: str,
    seed_id: str,
) -> str:
    return ":".join(
        (
            "seed",
            _stable_ref_part(world_id),
            _stable_ref_part(source_id),
            _stable_ref_part(entity_type),
            _stable_ref_part(archetype_id),
            _stable_ref_part(seed_id),
        )
    )


def _stable_ref_part(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", "_", text)
    text = text.replace(":", "_")
    return text or "unknown"
