from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from worldkernel.architect import (  # noqa: E402
    InitBuildContext,
    ResolvedSeed,
    compile_stage1_init_context,
    create_default_schema_registry,
    create_default_tool_registry,
)


DEFAULT_SESSION_ROOT = ROOT / "templates" / "39c96945-a4e0-4f9e-8fa6-80137493f939"


def main() -> None:
    args = _parse_args()
    session_root = _resolve_session_root(args.session_root)
    schema_registry = create_default_schema_registry()
    tool_registry = create_default_tool_registry(schema_registry)
    context = compile_stage1_init_context(
        session_root=session_root,
        schema_registry=schema_registry,
        tool_registry=tool_registry,
        source_id=args.source_id,
    )
    if args.output:
        output_path = _resolve_output_path(args.output)
        _write_full_json(context, output_path)
        print(f"saved full JSON: {output_path}")

    if args.full_json:
        print(json.dumps(context.model_dump(), ensure_ascii=False, indent=2))
        return

    _print_summary(context, session_root=session_root, limit=args.limit)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize Stage2 InitBuildContext compiled from Stage1 JSON outputs."
    )
    parser.add_argument(
        "--session-root",
        default=str(DEFAULT_SESSION_ROOT),
        help="Stage1 session root. Defaults to the bundled Hogwarts sample session.",
    )
    parser.add_argument(
        "--source-id",
        default="primary",
        help="Schema/source namespace used for stable seed refs.",
    )
    parser.add_argument(
        "--full-json",
        action="store_true",
        help="Print the full InitBuildContext JSON instead of a compact summary.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of location/character seed examples to show in summary mode.",
    )
    parser.add_argument(
        "--output",
        help="Write the full InitBuildContext JSON to this file.",
    )
    return parser.parse_args()


def _resolve_session_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _resolve_output_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _write_full_json(context: InitBuildContext, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(context.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_summary(context: InitBuildContext, session_root: Path, limit: int) -> None:
    world = context.world_background
    dag = context.execution_dag

    print("Stage2 Init Compile Debug View")
    print("=" * 80)
    print(f"session_root: {session_root}")
    print(f"world_id:     {world.world_id}")
    print(f"source_id:    {world.source_id}")
    print(f"world_name:   {world.world_name}")
    print(f"type:         {world.primary}" + (f" / {world.secondary}" if world.secondary else ""))
    print(f"scope:        {world.scope}")
    print(f"constraints:  {len(world.world_constraints)}")
    print()

    print("Execution DAG")
    print("-" * 80)
    print("order:", " -> ".join(dag.execution_order))
    print()
    for node in dag.nodes:
        depends_on = ", ".join(node.depends_on) if node.depends_on else "-"
        print(f"[{node.priority}] {node.step_id}")
        print(f"  generator:     {node.generator_type}")
        print(f"  target:        {node.target_entity_type}")
        print(f"  batch_size:    {node.batch_size}")
        print(f"  depends_on:    {depends_on}")
        print(f"  tool_id:       {node.tool_id}")
        print(f"  output_schema: {node.output_schema_alias}")
    print()

    print("Resolved Seeds")
    print("-" * 80)
    print(f"locations:  {len(context.resolved_location_seeds)}")
    _print_seed_examples(context.resolved_location_seeds, limit=limit)
    print()
    print(f"characters: {len(context.resolved_character_seeds)}")
    _print_seed_examples(context.resolved_character_seeds, limit=limit)
    print()

    print("Provenance")
    print("-" * 80)
    for key, value in context.provenance.items():
        print(f"{key}: {value}")


def _print_seed_examples(seeds: list[ResolvedSeed], limit: int) -> None:
    for seed in seeds[: max(limit, 0)]:
        print(f"  - {seed.seed_id} ({seed.name})")
        print(f"    entity_type:     {seed.entity_type}")
        print(f"    archetype_id:    {seed.archetype_id}")
        print(f"    priority:        {seed.priority}")
        print(f"    stable_seed_ref: {seed.stable_seed_ref}")


if __name__ == "__main__":
    main()
