from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from worldkernel.architect import (  # noqa: E402
    BaseStage2Tool,
    FoundationBundleBuildError,
    Stage2ToolResult,
    StepResultStore,
    build_foundation_bundle,
    compile_stage1_init_context,
    create_default_schema_registry,
    create_default_tool_registry,
    load_semantic_repository,
    run_semantic_generation,
    save_semantic_artifacts,
)


SESSION = ROOT / "templates" / "39c96945-a4e0-4f9e-8fa6-80137493f939"


class FakeLocationTool(BaseStage2Tool):
    tool_id = "stage2.location_generator.v1"
    generator_type = "location_generator"
    output_schema_alias = "location_profile"

    async def run(self, request, context):
        return Stage2ToolResult(
            artifact_type="location_profile",
            items=[
                {"identity": {"id": "loc_1", "name": "Great Hall"}},
                {"identity": {"id": "loc_2", "name": "Dormitory"}},
            ],
            produced_refs=["loc_1", "loc_2"],
            provenance={"source_id": context.source_id},
        )


class FakePathTool(BaseStage2Tool):
    tool_id = "stage2.path_generator.v1"
    generator_type = "path_generator"
    output_schema_alias = "path_edge"

    async def run(self, request, context):
        assert "generate_locations" in request.upstream_artifacts
        return Stage2ToolResult(
            artifact_type="path_edge",
            items=[
                {
                    "id": "path_1",
                    "from_location_id": "loc_1",
                    "to_location_id": "loc_2",
                }
            ],
            produced_refs=["path_1"],
            provenance={"source_id": context.source_id},
        )


class FakeCharacterTool(BaseStage2Tool):
    tool_id = "stage2.character_generator.v1"
    generator_type = "character_generator"
    output_schema_alias = "character_profile"

    async def run(self, request, context):
        return Stage2ToolResult(
            artifact_type="character_profile",
            items=[{"identity": {"id": "char_1", "name": "Harry"}, "location_id": "loc_1"}],
            produced_refs=["char_1"],
            provenance={"source_id": context.source_id},
        )


class FakeRelationTool(BaseStage2Tool):
    tool_id = "stage2.relation_generator.v1"
    generator_type = "relation_generator"
    output_schema_alias = "relation_edge"

    async def run(self, request, context):
        assert "generate_characters" in request.upstream_artifacts
        return Stage2ToolResult(
            artifact_type="relation_edge",
            items=[{"id": "rel_1", "source_id": "char_1", "target_id": "loc_1"}],
            produced_refs=["rel_1"],
            provenance={"source_id": context.source_id},
        )


class Stage2SemanticRunnerTests(unittest.TestCase):
    def _init_context(self):
        return compile_stage1_init_context(
            SESSION,
            schema_registry=create_default_schema_registry(),
            tool_registry=create_default_tool_registry(create_default_schema_registry()),
            source_id="primary",
        )

    def test_default_runner_stops_cleanly_on_unimplemented_tool(self) -> None:
        init_context = self._init_context()
        state = run_semantic_generation(
            init_context=init_context,
            schema_registry=create_default_schema_registry(),
            tool_registry=create_default_tool_registry(create_default_schema_registry()),
        )

        self.assertEqual(
            state.execution_order,
            ["generate_locations", "generate_paths", "generate_characters", "generate_relations"],
        )
        self.assertEqual(state.failed_step_id, "generate_locations")
        self.assertEqual(state.completed_steps, [])
        self.assertTrue(state.errors)

    def test_step_result_store_keeps_single_reference(self) -> None:
        store = StepResultStore()
        result = Stage2ToolResult(artifact_type="location_profile", items=[{"id": "loc_1"}])
        store.add_result("generate_locations", result)

        self.assertIs(store.get_step_result("generate_locations"), result)
        self.assertIs(store.list_by_artifact_type("location_profile")[0], result)

    def test_successful_runner_storage_and_repository_flow(self) -> None:
        init_context = self._init_context()
        tool_registry = create_default_tool_registry(create_default_schema_registry())
        tool_registry._tools_by_id["stage2.location_generator.v1"] = FakeLocationTool()
        tool_registry._tools_by_generator_type["location_generator"] = tool_registry._tools_by_id["stage2.location_generator.v1"]
        tool_registry._tools_by_id["stage2.path_generator.v1"] = FakePathTool()
        tool_registry._tools_by_generator_type["path_generator"] = tool_registry._tools_by_id["stage2.path_generator.v1"]
        tool_registry._tools_by_id["stage2.character_generator.v1"] = FakeCharacterTool()
        tool_registry._tools_by_generator_type["character_generator"] = tool_registry._tools_by_id["stage2.character_generator.v1"]
        tool_registry._tools_by_id["stage2.relation_generator.v1"] = FakeRelationTool()
        tool_registry._tools_by_generator_type["relation_generator"] = tool_registry._tools_by_id["stage2.relation_generator.v1"]

        state = run_semantic_generation(
            init_context=init_context,
            schema_registry=create_default_schema_registry(),
            tool_registry=tool_registry,
        )

        self.assertIsNone(state.failed_step_id)
        self.assertEqual(
            state.completed_steps,
            ["generate_locations", "generate_paths", "generate_characters", "generate_relations"],
        )

        bundle = build_foundation_bundle(init_context, state)
        self.assertEqual(bundle.world_id, init_context.world_background.world_id)
        self.assertEqual(bundle.locations[0]["identity"]["id"], "loc_1")
        self.assertEqual(bundle.characters[0]["identity"]["id"], "char_1")

        tmpdir = ROOT / "tests" / "debug_outputs" / "semantic_storage_case"
        report = save_semantic_artifacts(
            world_id=init_context.world_background.world_id,
            init_context=init_context,
            generation_state=state,
            output_root=tmpdir,
            debug=True,
        )
        self.assertTrue(report.success)
        self.assertFalse((tmpdir / "bundle" / "foundation_bundle.json").exists())
        self.assertTrue((tmpdir / "locations" / "locations.json").exists())
        self.assertTrue((tmpdir / "metadata" / "semantic_manifest.json").exists())
        self.assertTrue((tmpdir / "metadata" / "reference_index.json").exists())
        self.assertTrue((tmpdir / "metadata" / "debug" / "init_context.debug.json").exists())

        repository = load_semantic_repository(
            world_id=init_context.world_background.world_id,
            output_root=tmpdir,
        )
        manifest = repository.load_manifest()
        self.assertEqual(manifest.world_id, init_context.world_background.world_id)
        self.assertEqual(repository.get_location("loc_1")["identity"]["name"], "Great Hall")
        self.assertEqual(repository.get_character("char_1")["identity"]["name"], "Harry")
        rebuilt_bundle = repository.build_foundation_bundle()
        self.assertEqual(rebuilt_bundle.path_graph[0]["from_location_id"], "loc_1")
        self.assertEqual(rebuilt_bundle.constraints, init_context.world_background.world_constraints)

        reference_index_text = (tmpdir / "metadata" / "reference_index.json").read_text(encoding="utf-8")
        self.assertNotIn("Great Hall", reference_index_text)

    def test_foundation_bundle_requires_locations_and_characters(self) -> None:
        init_context = self._init_context()
        empty_state = run_semantic_generation(
            init_context=init_context,
            schema_registry=create_default_schema_registry(),
            tool_registry=create_default_tool_registry(create_default_schema_registry()),
        )
        with self.assertRaises(FoundationBundleBuildError):
            build_foundation_bundle(init_context, empty_state)


if __name__ == "__main__":
    unittest.main()
