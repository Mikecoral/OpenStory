from __future__ import annotations

import sys
import unittest
import asyncio
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from worldkernel.architect import (  # noqa: E402
    BaseStage2Tool,
    LocationGenerationTool,
    SchemaAmbiguityError,
    SchemaEntry,
    SchemaLoadError,
    SchemaSource,
    Stage2ToolContext,
    Stage2ToolRequest,
    ToolNotFoundError,
    ToolRegistryError,
    create_default_schema_registry,
    create_default_tool_registry,
    load_stage1_schema_source,
    load_stage1_session_schema_source,
)


SESSION_A = ROOT / "templates" / "39c96945-a4e0-4f9e-8fa6-80137493f939"
SESSION_B = ROOT / "templates" / "e87d1e32-92a5-417a-9698-7bd738a9a69a"


class Stage2SchemaRegistryTests(unittest.TestCase):
    def test_loads_stage1_dynamic_models_with_aliases(self) -> None:
        registry = load_stage1_session_schema_source(SESSION_A)

        location_entry = registry.get("location_profile", source_id="primary")
        character_entry = registry.get("character_profile", source_id="primary")
        self.assertEqual(location_entry.canonical_name, "LocationModel")
        self.assertEqual(character_entry.canonical_name, "AgentModel")
        self.assertEqual(character_entry.model_type.__name__, "AgentModel")

        validated = registry.validate(
            "location_profile",
            {"identity": {"id": "loc-1", "name": "Great Hall"}},
            source_id="primary",
        )
        self.assertEqual(validated.identity.id, "loc-1")
        self.assertEqual(validated.identity.name, "Great Hall")

    def test_dynamic_model_validation_rejects_invalid_payload(self) -> None:
        registry = load_stage1_session_schema_source(SESSION_A)

        with self.assertRaises(ValidationError):
            registry.validate(
                "location_profile",
                {"state": {"capacity": "not-an-int"}},
                source_id="primary",
            )

    def test_multiple_schema_sources_can_share_aliases(self) -> None:
        registry = create_default_schema_registry()
        load_stage1_session_schema_source(SESSION_A, registry=registry, source_id="main", world_id="big-world")
        load_stage1_session_schema_source(SESSION_B, registry=registry, source_id="sub", world_id="small-world")

        self.assertEqual(len(registry.list_entries(alias="location_profile")), 2)
        with self.assertRaises(SchemaAmbiguityError):
            registry.get("location_profile")

        main_location = registry.get("location_profile", source_id="main")
        sub_location = registry.get("location_profile", source_id="sub")
        self.assertNotEqual(main_location.model_type, sub_location.model_type)

    def test_missing_default_model_file_raises_unless_partial_allowed(self) -> None:
        source = SchemaSource(
            source_id="incomplete",
            root_dir=ROOT / "templates" / "b53c6009-4c24-4d3f-9f96-be2a2c4327cc",
        )
        registry = create_default_schema_registry()

        with self.assertRaises(SchemaLoadError):
            load_stage1_schema_source(source, registry)

        partial_source = source.model_copy(update={"allow_partial": True})
        load_stage1_schema_source(partial_source, registry)
        self.assertEqual(registry.list_entries(source_id="incomplete"), [])

    def test_same_source_alias_version_cannot_be_registered_twice(self) -> None:
        registry = load_stage1_session_schema_source(SESSION_A)
        existing = registry.get("location_profile", source_id="primary")

        with self.assertRaises(Exception):
            registry.register(
                SchemaEntry(
                    alias=existing.alias,
                    version=existing.version,
                    model_type=existing.model_type,
                    source=existing.source,
                )
            )


class Stage2ToolRegistryTests(unittest.TestCase):
    def test_default_tools_are_callable_tool_objects(self) -> None:
        schema_registry = create_default_schema_registry()
        tool_registry = create_default_tool_registry(schema_registry)

        location_tool = tool_registry.get_by_generator_type("location_generator")
        self.assertIsInstance(location_tool, LocationGenerationTool)
        self.assertTrue(hasattr(location_tool, "run"))
        self.assertEqual(location_tool.output_schema_alias, "location_profile")
        self.assertEqual(
            tool_registry.get_by_generator_type("character_generator").output_schema_alias,
            "character_profile",
        )
        self.assertEqual(
            tool_registry.get_by_generator_type("path_generator").output_schema_alias,
            "path_edge",
        )
        self.assertEqual(
            tool_registry.get_by_generator_type("relation_generator").output_schema_alias,
            "relation_edge",
        )

    def test_tool_run_is_intentionally_unimplemented(self) -> None:
        schema_registry = create_default_schema_registry()
        tool_registry = create_default_tool_registry(schema_registry)
        tool = tool_registry.get_by_generator_type("location_generator")
        request = Stage2ToolRequest(generator_type="location_generator")
        context = Stage2ToolContext(schema_registry=schema_registry, source_id="primary")

        with self.assertRaises(NotImplementedError):
            asyncio.run(tool.run(request, context))

    def test_unknown_generator_type_and_schema_alias_raise(self) -> None:
        schema_registry = create_default_schema_registry()
        tool_registry = create_default_tool_registry(schema_registry)

        with self.assertRaises(ToolNotFoundError):
            tool_registry.get_by_generator_type("unknown_generator")

        class BadSchemaTool(BaseStage2Tool):
            tool_id = "bad-tool"
            generator_type = "bad_generator"
            output_schema_alias = "missing_schema_alias"

        with self.assertRaises(ToolRegistryError):
            tool_registry.register(BadSchemaTool())

    def test_duplicate_tool_id_or_generator_type_raise(self) -> None:
        schema_registry = create_default_schema_registry()
        tool_registry = create_default_tool_registry(schema_registry)

        with self.assertRaises(ToolRegistryError):
            tool_registry.register(LocationGenerationTool())

        class DuplicateGeneratorTool(BaseStage2Tool):
            tool_id = "stage2.location_generator.duplicate"
            generator_type = "location_generator"
            output_schema_alias = "location_profile"

        with self.assertRaises(ToolRegistryError):
            tool_registry.register(DuplicateGeneratorTool())


if __name__ == "__main__":
    unittest.main()
