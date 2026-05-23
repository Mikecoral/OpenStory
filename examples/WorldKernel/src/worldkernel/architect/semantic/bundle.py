from __future__ import annotations

from typing import Any

from worldkernel.architect.init.models import InitBuildContext
from worldkernel.architect.semantic.models import FoundationBundle
from worldkernel.architect.semantic.state import SemanticGenerationState


class FoundationBundleBuildError(RuntimeError):
    pass


def _flatten_items(state: SemanticGenerationState, artifact_type: str) -> list[Any]:
    items: list[Any] = []
    for result in state.result_store.list_by_artifact_type(artifact_type):
        items.extend(result.items)
    return items


class FoundationBundleBuilder:
    def build(
        self,
        init_context: InitBuildContext,
        generation_state: SemanticGenerationState,
    ) -> FoundationBundle:
        locations = _flatten_items(generation_state, "location_profile")
        characters = _flatten_items(generation_state, "character_profile")
        path_graph = _flatten_items(generation_state, "path_edge")
        relation_graph = _flatten_items(generation_state, "relation_edge")

        if not locations:
            raise FoundationBundleBuildError("missing location_profile artifacts for foundation bundle")
        if not characters:
            raise FoundationBundleBuildError("missing character_profile artifacts for foundation bundle")

        return FoundationBundle(
            world_id=init_context.world_background.world_id,
            locations=locations,
            characters=characters,
            path_graph=path_graph,
            relation_graph=relation_graph,
            constraints=init_context.world_background.world_constraints,
            provenance={
                "source_id": init_context.world_background.source_id,
                "execution_order": list(generation_state.execution_order),
                "completed_steps": list(generation_state.completed_steps),
            },
        )


def build_foundation_bundle(
    init_context: InitBuildContext,
    generation_state: SemanticGenerationState,
) -> FoundationBundle:
    return FoundationBundleBuilder().build(init_context, generation_state)
