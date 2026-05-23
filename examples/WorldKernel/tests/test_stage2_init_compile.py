from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from worldkernel.architect import (  # noqa: E402
    BaseStage2Tool,
    ExecutionDAGCompiler,
    InitCompileError,
    InitInputLoadError,
    InitInputLoader,
    SeedResolver,
    compile_stage1_init_context,
    create_default_schema_registry,
    create_default_tool_registry,
)


SESSION = ROOT / "templates" / "39c96945-a4e0-4f9e-8fa6-80137493f939"
PLAN_DIR = SESSION / "generated" / "plan"


class Stage2InitLoaderTests(unittest.TestCase):
    def test_loads_stage1_three_json_files(self) -> None:
        bundle = InitInputLoader.from_session_root(SESSION, source_id="primary")

        self.assertEqual(bundle.source_id, "primary")
        self.assertEqual(bundle.world_id, "39c96945-a4e0-4f9e-8fa6-80137493f939")
        self.assertIn("world_constraints", bundle.world_background)
        self.assertGreaterEqual(len(bundle.execution_plan["steps"]), 4)
        self.assertIn("location", bundle.seed_catalog["instance_seeds"])

    def test_missing_required_file_raises(self) -> None:
        with self.assertRaises(InitInputLoadError):
            InitInputLoader.from_paths(
                world_background_path=PLAN_DIR / "missing_world_background.json",
                execution_plan_path=PLAN_DIR / "execution_plan.json",
                seed_catalog_path=PLAN_DIR / "instance_seed_catalog.json",
            )

    def test_missing_steps_or_instance_seeds_raises(self) -> None:
        with self.assertRaises(InitInputLoadError):
            InitInputLoader.from_paths(
                world_background_path=PLAN_DIR / "world_background.json",
                execution_plan_path=SESSION / "generated" / "world_template.json",
                seed_catalog_path=PLAN_DIR / "instance_seed_catalog.json",
            )

        with self.assertRaises(InitInputLoadError):
            InitInputLoader.from_paths(
                world_background_path=PLAN_DIR / "world_background.json",
                execution_plan_path=PLAN_DIR / "execution_plan.json",
                seed_catalog_path=PLAN_DIR / "world_background.json",
            )

class Stage2InitCompilerTests(unittest.TestCase):
    def _bundle(self):
        return InitInputLoader.from_session_root(SESSION, source_id="main")

    def _tool_registry(self):
        return create_default_tool_registry(create_default_schema_registry())

    def test_compiles_execution_plan_to_stable_dag(self) -> None:
        dag = ExecutionDAGCompiler(self._tool_registry()).compile(self._bundle())

        self.assertEqual(
            dag.execution_order,
            ["generate_locations", "generate_paths", "generate_characters", "generate_relations"],
        )
        self.assertEqual(len(dag.nodes), 4)
        self.assertEqual(dag.nodes[1].depends_on, ["generate_locations"])
        self.assertEqual(dag.nodes[3].depends_on, ["generate_characters"])
        self.assertEqual(dag.nodes[0].tool_id, "stage2.location_generator.v1")

    def test_unknown_generator_type_is_rejected(self) -> None:
        bundle = self._bundle()
        bundle.execution_plan["steps"][0]["generator_type"] = "unknown_generator"

        with self.assertRaises(Exception):
            ExecutionDAGCompiler(self._tool_registry()).compile(bundle)

    def test_duplicate_step_id_and_invalid_priority_are_rejected(self) -> None:
        bundle = self._bundle()
        bundle.execution_plan["steps"][1]["step_id"] = bundle.execution_plan["steps"][0]["step_id"]
        with self.assertRaises(InitCompileError):
            ExecutionDAGCompiler(self._tool_registry()).compile(bundle)

        bundle = self._bundle()
        bundle.execution_plan["steps"][0]["priority"] = 0
        with self.assertRaises(InitCompileError):
            ExecutionDAGCompiler(self._tool_registry()).compile(bundle)

    def test_resolves_seeds_with_stable_refs(self) -> None:
        locations_a, characters_a = SeedResolver().resolve(self._bundle())
        locations_b, characters_b = SeedResolver().resolve(self._bundle())

        self.assertGreater(len(locations_a), 0)
        self.assertGreater(len(characters_a), 0)
        self.assertEqual(locations_a[0].stable_seed_ref, locations_b[0].stable_seed_ref)
        self.assertEqual(characters_a[0].stable_seed_ref, characters_b[0].stable_seed_ref)
        self.assertTrue(locations_a[0].stable_seed_ref.startswith("seed:39c96945"))
        self.assertIn(":main:location:", locations_a[0].stable_seed_ref)

    def test_compile_pipeline_does_not_call_tool_run(self) -> None:
        class ExplodingLocationTool(BaseStage2Tool):
            tool_id = "stage2.location_generator.v1"
            generator_type = "location_generator"
            output_schema_alias = "location_profile"

            async def run(self, request, context):
                raise AssertionError("compile pipeline must not execute tools")

        tool_registry = self._tool_registry()
        tool_registry._tools_by_id["stage2.location_generator.v1"] = ExplodingLocationTool()
        tool_registry._tools_by_generator_type["location_generator"] = ExplodingLocationTool()

        context = compile_stage1_init_context(
            SESSION,
            schema_registry=create_default_schema_registry(),
            tool_registry=tool_registry,
            source_id="main",
        )

        self.assertEqual(context.world_background.source_id, "main")
        self.assertGreater(len(context.resolved_location_seeds), 0)
        self.assertGreater(len(context.resolved_character_seeds), 0)
        self.assertEqual(len(context.execution_dag.nodes), 4)

    def test_different_source_ids_produce_different_seed_refs(self) -> None:
        context_a = compile_stage1_init_context(
            SESSION,
            schema_registry=create_default_schema_registry(),
            tool_registry=self._tool_registry(),
            source_id="main",
        )
        context_b = compile_stage1_init_context(
            SESSION,
            schema_registry=create_default_schema_registry(),
            tool_registry=self._tool_registry(),
            source_id="sub",
        )

        self.assertNotEqual(
            context_a.resolved_location_seeds[0].stable_seed_ref,
            context_b.resolved_location_seeds[0].stable_seed_ref,
        )


if __name__ == "__main__":
    unittest.main()
