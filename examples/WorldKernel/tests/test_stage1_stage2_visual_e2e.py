"""Stage1 -> Stage2 visual end-to-end test (真实服务器 + 浏览器前端)

启动 uvicorn -> 打开浏览器 -> 用户在 textarea 输入 -> 点击「开始生成」
-> 自动检测新 session -> Stage1 校验 -> Stage2 编译 -> 可视化调试输出。

用法：
    cd examples/WorldKernel
    python tests/test_stage1_stage2_visual_e2e.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from worldkernel.architect import (  # noqa: E402
    compile_stage1_init_context,
    create_default_schema_registry,
    create_default_tool_registry,
    load_stage1_session_schema_source,
)
from worldkernel.architect.semantic import save_semantic_artifacts  # noqa: E402
from worldkernel.architect.semantic.runner import InitDAGRunner  # noqa: E402
from worldkernel.stage1.ontology_selector import _FIXED_DIMENSIONS  # noqa: E402

_TEMPLATES_DIR = _ROOT / "templates"
_SERVER_URL = "http://localhost:8100"
_DEBUG_ROOT = _ROOT / "tests" / "debug_outputs" / "stage1_stage2_visual_e2e"
_ENTITY_KEYS = list(_FIXED_DIMENSIONS.keys())

_EXPECTED_PATHS = [
    "generated/artifact_manifest.json",
    "generated/world_template.json",
    "generated/plan/world_background.json",
    "generated/plan/execution_plan.json",
    "generated/plan/instance_seed_catalog.json",
    "generated/plan/ontology_hints.json",
    "generated/templates/character/index.json",
    "generated/templates/location/index.json",
    "generated/templates/path/index.json",
    "generated/templates/relation/index.json",
    "generated/templates/institution/index.json",
    "generated/templates/rule/index.json",
    "generated/templates/action/index.json",
    "configs/agent/agent.yaml",
    "configs/agent/dims",
    "configs/location/location.yaml",
    "configs/location/dims",
    "configs/path/path.yaml",
    "configs/path/dims",
    "configs/relation/relation.yaml",
    "configs/relation/dims",
    "models/schema_manifest.json",
    "models/agent_model.py",
    "models/location_model.py",
    "models/path_model.py",
    "models/relation_model.py",
]

_DESCRIPTION_MAP = {
    "generated/world_template.json": "Stage1 world type classification output",
    "generated/artifact_manifest.json": "Master artifact manifest for loader",
    "generated/plan/world_background.json": "Compiled world background for Stage2",
    "generated/plan/execution_plan.json": "Generation step ordering (4 steps)",
    "generated/plan/instance_seed_catalog.json": "Seed instances for location / character",
    "generated/plan/ontology_hints.json": "Ontology guidance hints for template generation",
    "models/schema_manifest.json": "Schema registry manifest (4 aliases)",
}


# ---------------------------------------------------------------------------
# Stats & output helpers
# ---------------------------------------------------------------------------


class _Stats:
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, msg: str) -> None:
        self.total += 1
        self.passed += 1
        print(f"  [PASS] {msg}")

    def fail(self, msg: str) -> None:
        self.total += 1
        self.failed += 1
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")


def _sep(title: str = "", width: int = 70) -> None:
    if title:
        pad = max((width - len(title) - 2) // 2, 1)
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print("─" * width)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load(session_dir: Path, rel_path: str) -> dict | list | None:
    p = session_dir / rel_path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _describe_path(rel: str) -> str:
    if rel in _DESCRIPTION_MAP:
        return _DESCRIPTION_MAP[rel]
    parts = rel.replace("\\", "/").split("/")
    if "templates" in parts:
        idx = parts.index("templates")
        if idx + 1 < len(parts):
            entity = parts[idx + 1]
            if len(parts) > idx + 2 and parts[-1] == "index.json":
                return f"Dimension index for {entity}"
            if len(parts) > idx + 2 and parts[-1].endswith(".json"):
                dim = parts[-1].removesuffix(".json")
                return f"Dimension schema: {entity}.{dim}"
    if parts[0] == "configs" and len(parts) >= 2:
        if "dims" in parts:
            dim = parts[-1].removesuffix(".yaml")
            return f"Dimension config: {parts[1]}.{dim}"
        return f"Entity config: {parts[1]}"
    if parts[0] == "models" and parts[-1].endswith("_model.py"):
        name = parts[-1].removesuffix("_model.py")
        return f"Generated Pydantic model: {name}"
    return rel


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    return f"{n / 1024:.1f}KB"


# ---------------------------------------------------------------------------
# Session detection
# ---------------------------------------------------------------------------


def _get_existing_sessions() -> set[str]:
    if not _TEMPLATES_DIR.exists():
        return set()
    return {d.name for d in _TEMPLATES_DIR.iterdir() if d.is_dir()}


def _wait_for_new_session(before: set[str], timeout: float = 600.0) -> str | None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        current = _get_existing_sessions()
        new = current - before
        if new:
            return new.pop()
        time.sleep(1.0)
    return None


def _wait_for_stable(session_dir: Path, timeout: float = 600.0) -> None:
    t0 = time.time()
    prev_count = 0
    stable_since = 0.0
    while time.time() - t0 < timeout:
        count = sum(1 for _ in session_dir.rglob("*.json"))
        if count != prev_count:
            prev_count = count
            stable_since = time.time()
        elif time.time() - stable_since > 5.0 and prev_count > 0:
            return
        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Stage1 validation (from test_stage1.py)
# ---------------------------------------------------------------------------


def _validate_structure(session_dir: Path, stats: _Stats) -> None:
    _sep("结构完整性检查")
    for expected in _EXPECTED_PATHS:
        p = session_dir / expected
        if p.exists():
            stats.ok(f"存在: {expected}")
        else:
            stats.fail(f"缺失: {expected}")


def _validate_world_template(session_dir: Path, stats: _Stats) -> None:
    _sep("world_template.json")
    data = _load(session_dir, "generated/world_template.json")
    if data is None:
        stats.fail("world_template.json 不存在")
        return
    if data.get("primary"):
        stats.ok(f"primary = {data['primary']}")
    else:
        stats.fail("primary 为空")
    for arch_field in ("location_archetypes", "character_archetypes", "rule_archetypes"):
        val = data.get(arch_field, [])
        if len(val) >= 2:
            stats.ok(f"{arch_field} 有 {len(val)} 种类型")
        elif len(val) == 1:
            stats.ok(f"{arch_field} 有 1 种类型（偏少）")
        else:
            stats.fail(f"{arch_field} 为空")
        if val:
            first = val[0]
            seed_keys = [k for k in first if k.startswith("candidate_")]
            if seed_keys and first.get(seed_keys[0]):
                stats.ok(f"{arch_field}[0] 含候选 seed")
            else:
                stats.fail(f"{arch_field}[0] 缺少候选 seed")
    sim = data.get("simulation_start", {})
    if sim.get("trigger_event"):
        stats.ok("simulation_start.trigger_event 非空")
    else:
        stats.fail("simulation_start.trigger_event 为空")
    constraints = data.get("world_constraints", [])
    if len(constraints) >= 2:
        stats.ok(f"world_constraints 有 {len(constraints)} 条")
    else:
        stats.fail("world_constraints 不足 2 条")


def _validate_plan(session_dir: Path, stats: _Stats) -> None:
    _sep("plan/")
    ep = _load(session_dir, "generated/plan/execution_plan.json")
    if ep is None:
        stats.fail("execution_plan.json 不存在")
    else:
        steps = ep.get("steps", [])
        if len(steps) >= 4:
            stats.ok(f"execution_plan.json: {len(steps)} 个步骤")
        else:
            stats.fail(f"execution_plan.json: 步骤数不足 ({len(steps)})")
    hints = _load(session_dir, "generated/plan/ontology_hints.json")
    if hints is None:
        stats.fail("ontology_hints.json 不存在")
    elif hints.get("character_hints"):
        stats.ok("ontology_hints.character_hints 非空")
    else:
        stats.fail("ontology_hints.character_hints 为空")
    catalog = _load(session_dir, "generated/plan/instance_seed_catalog.json")
    if catalog is None:
        stats.fail("instance_seed_catalog.json 不存在")
    else:
        seeds = catalog.get("instance_seeds", {})
        for category in ("location", "character"):
            items = seeds.get(category, [])
            if len(items) >= 3:
                stats.ok(f"instance_seeds/{category}: {len(items)} 个种子")
            else:
                stats.fail(f"instance_seeds/{category}: 种子数不足 ({len(items)})")
    bg = _load(session_dir, "generated/plan/world_background.json")
    if bg is None:
        stats.fail("world_background.json 不存在")
    else:
        if bg.get("world_name"):
            stats.ok(f"world_background.world_name = {bg['world_name']}")
        else:
            stats.fail("world_background.world_name 为空")


def _validate_templates(session_dir: Path, stats: _Stats) -> None:
    _sep("templates/")
    expected_dims = {
        "character": 10, "location": 5, "institution": 6,
        "rule": 4, "action": 4, "relation": 2, "path": 4,
    }
    templates_dir = session_dir / "generated" / "templates"
    if not templates_dir.exists():
        stats.fail("templates/ 目录不存在")
        return
    for entity, min_dims in expected_dims.items():
        ent_dir = templates_dir / entity
        index_path = ent_dir / "index.json"
        if not index_path.exists():
            stats.fail(f"templates/{entity}/index.json 不存在")
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        dims = index.get("dimensions", [])
        if len(dims) >= min_dims:
            stats.ok(f"{entity}: {len(dims)} 个维度")
        else:
            stats.fail(f"{entity}: 维度数不足 ({len(dims)}，期望 ≥{min_dims})")
        for dim_name in dims:
            dim_path = ent_dir / f"{dim_name}.json"
            if not dim_path.exists():
                stats.fail(f"{entity}/{dim_name}.json 不存在")
                continue
            dim_data = json.loads(dim_path.read_text(encoding="utf-8"))
            fields = dim_data.get("fields", [])
            if len(fields) >= 1:
                f0 = fields[0]
                if isinstance(f0, dict) and f0.get("name") and "type" in f0:
                    stats.ok(f"{entity}/{dim_name}: {len(fields)} 个 FieldDef 字段")
                else:
                    stats.fail(f"{entity}/{dim_name}: fields[0] 不是 FieldDef 格式")
            else:
                stats.fail(f"{entity}/{dim_name}: fields 为空")


# ---------------------------------------------------------------------------
# Stage2 compilation & visualization
# ---------------------------------------------------------------------------


def _run_stage2(session_id: str, session_dir: Path, stats: _Stats) -> None:
    dbg = _DEBUG_ROOT / session_id
    dbg.mkdir(parents=True, exist_ok=True)

    _sep("Stage2: Schema Registry")
    schema_registry = create_default_schema_registry()
    load_stage1_session_schema_source(
        session_root=session_dir,
        registry=schema_registry,
        source_id="visual-e2e",
        world_id=session_id,
    )
    tool_registry = create_default_tool_registry(schema_registry)

    for alias in ("location_profile", "character_profile", "path_edge", "relation_edge"):
        entry = schema_registry.get(alias, source_id="visual-e2e")
        if entry is not None:
            stats.ok(f"schema alias '{alias}' 已注册")
        else:
            stats.fail(f"schema alias '{alias}' 未注册")

    schema_snapshot = [
        {
            "alias": e.alias,
            "canonical_name": e.canonical_name,
            "version": e.version,
            "source_id": e.source.source_id,
            "model_file": e.metadata.get("model_file", ""),
        }
        for e in schema_registry.list_entries(source_id="visual-e2e")
    ]
    _write_json(dbg / "schema_registry_snapshot.json", schema_snapshot)

    _sep("Stage2: Compile InitBuildContext")
    init_context = compile_stage1_init_context(
        session_dir,
        tool_registry=tool_registry,
        source_id="visual-e2e",
        world_id=session_id,
    )

    bg_data = _load(session_dir, "generated/plan/world_background.json") or {}
    if init_context.world_background.world_name == bg_data.get("world_name"):
        stats.ok(f"world_name 一致: {init_context.world_background.world_name}")
    else:
        stats.fail("world_name 不一致")
    if len(init_context.execution_dag.nodes) == 4:
        stats.ok("DAG 有 4 个节点")
    else:
        stats.fail(f"DAG 节点数异常: {len(init_context.execution_dag.nodes)}")
    if len(init_context.resolved_location_seeds) >= 1:
        stats.ok(f"location seeds: {len(init_context.resolved_location_seeds)}")
    else:
        stats.fail("location seeds 为空")
    if len(init_context.resolved_character_seeds) >= 1:
        stats.ok(f"character seeds: {len(init_context.resolved_character_seeds)}")
    else:
        stats.fail("character seeds 为空")

    # Seed ID uniqueness validation
    all_seed_ids = (
        [s.seed_id for s in init_context.resolved_location_seeds]
        + [s.seed_id for s in init_context.resolved_character_seeds]
    )
    if len(all_seed_ids) == len(set(all_seed_ids)):
        stats.ok(f"所有 seed_id 唯一 ({len(all_seed_ids)} 个)")
    else:
        stats.fail("存在重复的 seed_id")

    # DAG dependencies
    nodes_by_id = {n.step_id: n for n in init_context.execution_dag.nodes}
    if (nodes_by_id["generate_paths"].depends_on == ["generate_locations"]
            and nodes_by_id["generate_relations"].depends_on == ["generate_characters"]
            and nodes_by_id["generate_locations"].depends_on == []
            and nodes_by_id["generate_characters"].depends_on == []):
        stats.ok("DAG 依赖关系正确 (path->location, relation->character)")
    else:
        stats.fail("DAG 依赖关系异常")

    # Save DAG visualization
    dag_lines = ["# Execution DAG Visualization", "", "## Execution Order"]
    for i, step_id in enumerate(init_context.execution_dag.execution_order, 1):
        node = nodes_by_id[step_id]
        dep_str = f" [depends: {', '.join(node.depends_on)}]" if node.depends_on else ""
        dag_lines.append(
            f"{i}. `{step_id}` -> `{node.tool_id}` (`{node.output_schema_alias}`){dep_str}"
        )
    dag_lines += ["", "## Dependency Graph", ""]
    for node in init_context.execution_dag.nodes:
        for dep in node.depends_on:
            dag_lines.append(f"`{dep}` --> `{node.step_id}`")
    dag_lines += [
        "", "## Node Details", "",
        "| Step ID | Generator Type | Tool ID | Output Schema | Depends On | Batch Size |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for node in init_context.execution_dag.nodes:
        deps = ", ".join(node.depends_on) if node.depends_on else "(none)"
        dag_lines.append(
            f"| {node.step_id} | {node.generator_type} | {node.tool_id} "
            f"| {node.output_schema_alias} | {deps} | {node.batch_size} |"
        )
    _write_text(dbg / "dag_visualization.md", "\n".join(dag_lines))

    # Save seed inventory
    seed_lines = ["# Seed Inventory", "", "## Location Seeds", "",
                  "| Seed ID | Name | Archetype | Importance | Source Type | Priority |",
                  "| --- | --- | --- | --- | --- | --- |"]
    for seed in init_context.resolved_location_seeds:
        seed_lines.append(
            f"| {seed.seed_id} | {seed.name} "
            f"| {seed.archetype_id} | {seed.importance} | {seed.source_type} | {seed.seed.generation_priority} |"
        )
    seed_lines += ["", "## Character Seeds", "",
                    "| Seed ID | Name | Archetype | Importance | Source Type | Priority |",
                    "| --- | --- | --- | --- | --- | --- |"]
    for seed in init_context.resolved_character_seeds:
        seed_lines.append(
            f"| {seed.seed_id} | {seed.name} "
            f"| {seed.archetype_id} | {seed.importance} | {seed.source_type} | {seed.seed.generation_priority} |"
        )
    _write_text(dbg / "seed_inventory.md", "\n".join(seed_lines))

    # Save stage2 context summary
    wb = init_context.world_background
    sim = wb.simulation_start if isinstance(wb.simulation_start, dict) else {}
    ctx_lines = [
        "# Stage2 InitBuildContext Summary", "",
        "## World Background",
        f"- world_id: `{wb.world_id}`",
        f"- world_name: {wb.world_name}",
        f"- source_id: {wb.source_id}",
        f"- primary: {wb.primary}",
        f"- tags: {', '.join(wb.tags) if wb.tags else '(none)'}",
        f"- scope: {wb.scope}",
        f"- simulation_start: {sim.get('time_point', '?')} ({sim.get('trigger_event', '?')})",
        f"- constraints: {len(wb.world_constraints)}", "",
        "## Execution DAG",
        f"- {len(init_context.execution_dag.nodes)} nodes",
        f"- execution order: {' -> '.join(init_context.execution_dag.execution_order)}", "",
        "## Resolved Seeds",
        f"- location seeds: {len(init_context.resolved_location_seeds)}",
        f"- character seeds: {len(init_context.resolved_character_seeds)}", "",
        "## Schema Registry",
        "- 4 registered: location_profile, character_profile, path_edge, relation_edge",
    ]
    _write_text(dbg / "stage2_context_summary.md", "\n".join(ctx_lines))

    # Run InitDAGRunner (real LLM generation)
    _sep("Stage2: Running DAG Generation")
    runner = InitDAGRunner(schema_registry=schema_registry, tool_registry=tool_registry)
    generation_state = asyncio.run(runner.run_async(init_context))

    stage2_out = dbg / "stage2_semantic"
    save_semantic_artifacts(
        world_id=wb.world_id,
        init_context=init_context,
        generation_state=generation_state,
        output_root=stage2_out,
        debug=True,
    )

    # Verify location generation results
    _sep("Stage2: Location Generation Results")
    if "generate_locations" in generation_state.completed_steps:
        stats.ok("generate_locations 步骤完成")
    else:
        stats.fail(f"generate_locations 未完成: {generation_state.errors}")

    loc_result = generation_state.result_store.get_step_result("generate_locations") if generation_state.result_store.has_step_result("generate_locations") else None
    if loc_result:
        n_items = len(loc_result.items)
        n_seeds = len(init_context.resolved_location_seeds)
        if n_items >= 1:
            stats.ok(f"生成 {n_items}/{n_seeds} 个地点")
        else:
            stats.fail("未生成任何地点")

        # identity.id 格式验证 (新格式: e:<world_slug>:loc:<short_id>)
        entity_ids = [item.identity.id for item in loc_result.items if hasattr(item, "identity")]
        id_pattern_ok = all(eid.startswith("e:") and ":loc:" in eid for eid in entity_ids)
        if id_pattern_ok and len(entity_ids) == len(set(entity_ids)):
            stats.ok(f"{len(entity_ids)} 个地点 identity.id 格式正确且无重复")
        else:
            stats.fail(f"identity.id 格式异常或存在重复: {entity_ids[:5]}")

        # seed_ref → entity_id 映射（LLM 可能跳过部分 seed，不强制完整）
        mapping = loc_result.provenance.get("seed_to_entity_mapping", {})
        n_seeds = len(init_context.resolved_location_seeds)
        if len(mapping) >= n_seeds:
            stats.ok(f"seed_to_entity_mapping 完整 ({len(mapping)}/{n_seeds})")
        elif len(mapping) >= 1:
            print(f"  [WARN] seed_to_entity_mapping 部分完成 ({len(mapping)}/{n_seeds}，LLM 跳过了 {n_seeds - len(mapping)} 个 seed)")
        else:
            stats.fail(f"seed_to_entity_mapping 为空 (0/{n_seeds})")

        # 质量分数
        qs = loc_result.provenance.get("quality_summary", {})
        avg = qs.get("avg_review_score", 0)
        if avg >= 3.0:
            stats.ok(f"平均质量评分: {avg}")
        else:
            stats.fail(f"平均质量评分过低: {avg}")

        # 保存生成的地点数据
        _write_json(dbg / "stage2_locations.json", [
            item.model_dump() for item in loc_result.items
        ])

        # 保存 seed 映射
        _write_json(dbg / "seed_to_entity_mapping.json", mapping)

        # 详细信息输出
        _sep("Stage2: 地点生成详情")
        if loc_result.items:
            # 每个地点的关键字段表
            print(f"  {'#':<3} {'ID':<30} {'Name':<20} {'Type':<20} {'Importance':<10} {'Description (前50字)'}")
            print(f"  {'─'*3} {'─'*30} {'─'*20} {'─'*20} {'─'*10} {'─'*50}")
            for i, item in enumerate(loc_result.items, 1):
                identity = getattr(item, "identity", None)
                if identity:
                    eid = getattr(identity, "id", "?")
                    name = getattr(identity, "name", "?")
                    loc_type = getattr(identity, "type", "?")
                    desc = getattr(identity, "description", "")
                    desc_preview = desc[:50] + "..." if len(desc) > 50 else desc
                else:
                    eid, name, loc_type, desc_preview = "?", "?", "?", ""
                importance = "?"
                for seed in init_context.resolved_location_seeds:
                    if seed.name == name:
                        importance = seed.importance
                        break
                print(f"  {i:<3} {eid:<30} {name:<20} {loc_type:<20} {importance:<10} {desc_preview}")

            # 质量评分详情
            if qs:
                _sep("质量评分详情")
                print(f"  总分: {qs.get('avg_review_score', 'N/A')}")
                print(f"  种子数: {qs.get('total_seeds', 'N/A')}")
                print(f"  生成数: {qs.get('total_generated', 'N/A')}")
                print(f"  批次数: {qs.get('batches_processed', 'N/A')}")
                print(f"  重试次数: {qs.get('retry_count', 'N/A')}")
                key_issues = qs.get("key_issues", [])
                if key_issues:
                    print("  关键问题:")
                    for issue in key_issues:
                        print(f"    - {issue}")

            # 生成警告
            gen_warnings = loc_result.warnings
            if gen_warnings:
                _sep("生成警告")
                for w in gen_warnings:
                    print(f"  [WARN] {w}")
        else:
            print("  (无生成的地点数据)")
    else:
        stats.fail("无法获取 generate_locations 结果")

    # Verify character generation results
    _sep("Stage2: Character Generation Results")
    if "generate_characters" in generation_state.completed_steps:
        stats.ok("generate_characters 步骤完成")
    else:
        stats.fail(f"generate_characters 未完成: {generation_state.errors}")

    char_result = generation_state.result_store.get_step_result("generate_characters") if generation_state.result_store.has_step_result("generate_characters") else None
    if char_result:
        n_items = len(char_result.items)
        n_seeds = len(init_context.resolved_character_seeds)
        if n_items >= 1:
            stats.ok(f"生成 {n_items}/{n_seeds} 个角色")
        else:
            stats.fail("未生成任何角色")

        # identity.id 格式验证
        entity_ids = [item.identity.id for item in char_result.items if hasattr(item, "identity")]
        id_pattern_ok = all(eid.startswith("e:") and ":char:" in eid for eid in entity_ids)
        if id_pattern_ok and len(entity_ids) == len(set(entity_ids)):
            stats.ok(f"{len(entity_ids)} 个角色 identity.id 格式正确且无重复")
        else:
            stats.fail(f"identity.id 格式异常或存在重复: {entity_ids[:5]}")

        # seed_to_entity mapping
        mapping = char_result.provenance.get("seed_to_entity_mapping", {})
        if len(mapping) >= n_seeds:
            stats.ok(f"seed_to_entity_mapping 完整 ({len(mapping)}/{n_seeds})")
        elif len(mapping) >= 1:
            print(f"  [WARN] seed_to_entity_mapping 部分完成 ({len(mapping)}/{n_seeds})")
        else:
            stats.fail(f"seed_to_entity_mapping 为空 (0/{n_seeds})")

        # 质量分数
        qs = char_result.provenance.get("quality_summary", {})
        avg = qs.get("avg_review_score", 0)
        if avg >= 3.0:
            stats.ok(f"平均质量评分: {avg}")
        else:
            stats.fail(f"平均质量评分过低: {avg}")

        # 保存角色数据
        _write_json(dbg / "stage2_characters.json", [
            item.model_dump() for item in char_result.items
        ])

        # 详情输出
        _sep("Stage2: 角色生成详情")
        if char_result.items:
            print(f"  {'#':<3} {'ID':<30} {'Name':<20} {'Role':<20} {'Importance':<10}")
            print(f"  {'─'*3} {'─'*30} {'─'*20} {'─'*20} {'─'*10}")
            for i, item in enumerate(char_result.items, 1):
                identity = getattr(item, "identity", None)
                if identity:
                    eid = getattr(identity, "id", "?")
                    name = getattr(identity, "name", "?")
                    role = getattr(identity, "role", "?")
                else:
                    eid, name, role = "?", "?", "?"
                importance = "?"
                for seed in init_context.resolved_character_seeds:
                    if seed.name == name:
                        importance = seed.importance
                        break
                print(f"  {i:<3} {eid:<30} {name:<20} {role:<20} {importance:<10}")

            if qs:
                _sep("角色质量评分详情")
                print(f"  总分: {qs.get('avg_review_score', 'N/A')}")
                print(f"  种子数: {qs.get('total_seeds', 'N/A')}")
                print(f"  生成数: {qs.get('total_generated', 'N/A')}")
                print(f"  重试次数: {qs.get('retry_count', 'N/A')}")

            gen_warnings = char_result.warnings
            if gen_warnings:
                _sep("角色生成警告")
                for w in gen_warnings:
                    print(f"  [WARN] {w}")
    else:
        stats.fail("无法获取 generate_characters 结果")
    # Wave 1: [generate_characters, generate_locations] (sorted, parallel)
    # Wave 2: [generate_paths, generate_relations] (sorted, parallel)
    # The DAG's execution_order from Stage1 may differ; what matters is that
    # the runner's actual execution_order respects dependencies.
    expected_dag_steps = {"generate_locations", "generate_paths", "generate_characters", "generate_relations"}
    actual_steps = set(init_context.execution_dag.execution_order)
    if actual_steps == expected_dag_steps:
        stats.ok(f"DAG 包含全部 4 个步骤")
    else:
        stats.fail(f"DAG 步骤不完整: {actual_steps}")

    # Verify wave ordering: location/character before paths/relations
    if generation_state.completed_steps:
        completed = generation_state.completed_steps
        loc_idx = completed.index("generate_locations") if "generate_locations" in completed else -1
        char_idx = completed.index("generate_characters") if "generate_characters" in completed else -1
        path_idx = completed.index("generate_paths") if "generate_paths" in completed else -1
        rel_idx = completed.index("generate_relations") if "generate_relations" in completed else -1

        wave_order_ok = True
        if loc_idx >= 0 and path_idx >= 0 and path_idx < loc_idx:
            wave_order_ok = False
        if char_idx >= 0 and rel_idx >= 0 and rel_idx < char_idx:
            wave_order_ok = False

        if wave_order_ok:
            stats.ok(f"波次顺序正确: {' -> '.join(completed)}")
        else:
            stats.fail(f"波次顺序异常: {completed}")
    else:
        stats.fail("无已完成步骤")

    # Flow summary
    wt_data = _load(session_dir, "generated/world_template.json") or {}
    sc_data = _load(session_dir, "generated/plan/instance_seed_catalog.json") or {}
    ep_data = _load(session_dir, "generated/plan/execution_plan.json") or {}
    sm_data = _load(session_dir, "models/schema_manifest.json") or {}
    aliases = {s["alias"] for s in sm_data.get("schemas", [])}

    # Build location generation summary
    loc_summary = "N/A"
    if loc_result:
        n_items = len(loc_result.items)
        qs = loc_result.provenance.get("quality_summary", {})
        avg = qs.get("avg_review_score", 0)
        loc_summary = f"{n_items} locations generated, avg_score={avg}"

    # Build character generation summary
    char_summary = "N/A"
    if char_result:
        n_items = len(char_result.items)
        qs = char_result.provenance.get("quality_summary", {})
        avg = qs.get("avg_review_score", 0)
        char_summary = f"{n_items} characters generated, avg_score={avg}"

    summary_lines = [
        "# Stage1 -> Stage2 Visual E2E Flow Summary", "",
        "## Input",
        f"- session_id: {session_id}",
        f"- world_name: {wt_data.get('world_name', '?')}",
        f"- world_type_primary: {wt_data.get('primary', '?')}", "",
        "## Stage1 Results",
        f"- entity_templates_generated: {len(_ENTITY_KEYS)} ({', '.join(_ENTITY_KEYS)})",
        f"- location_seeds: {len(sc_data.get('instance_seeds', {}).get('location', []))}",
        f"- character_seeds: {len(sc_data.get('instance_seeds', {}).get('character', []))}",
        f"- generation_steps: {len(ep_data.get('steps', []))}", "",
        "## Stage2 Compilation",
        f"- execution_order: {', '.join(init_context.execution_dag.execution_order)}",
        f"- resolved_location_seeds: {len(init_context.resolved_location_seeds)}",
        f"- resolved_character_seeds: {len(init_context.resolved_character_seeds)}",
        f"- schema_aliases: {', '.join(sorted(aliases))}", "",
        "## Stage2 Location Generation",
        f"- completed_steps: {', '.join(generation_state.completed_steps)}",
        f"- result: {loc_summary}",
        f"- errors: {generation_state.errors or '(none)'}", "",
        "## Stage2 Character Generation",
        f"- result: {char_summary}", "",
        "## Debug Outputs",
        "- `dag_visualization.md`: DAG dependency graph",
        "- `seed_inventory.md`: Resolved seed table",
        "- `stage2_context_summary.md`: InitBuildContext summary",
        "- `schema_registry_snapshot.json`: Registered schemas",
        "- `stage2_locations.json`: Generated location data",
        "- `stage2_semantic/`: Full semantic generation debug output",
    ]
    _write_text(dbg / "flow_summary.md", "\n".join(summary_lines))
    stats.ok(f"调试输出已保存至: {dbg}")


# ---------------------------------------------------------------------------
# Artifact index
# ---------------------------------------------------------------------------


def _build_artifact_index(session_id: str, session_dir: Path) -> None:
    dbg = _DEBUG_ROOT / session_id
    lines = [
        "# Stage1 Artifact Index", "",
        f"- Session: `{session_id}`",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
        "| Path | Size | Description |",
        "| --- | --- | --- |",
    ]
    for f in sorted(session_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(session_dir)).replace("\\", "/")
        lines.append(f"| `{rel}` | {_human_size(f.stat().st_size)} | {_describe_path(rel)} |")
    _write_text(dbg / "stage1_artifact_index.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# Per-step dumps
# ---------------------------------------------------------------------------


def _save_per_step_dumps(session_id: str, session_dir: Path) -> None:
    step_dir = _DEBUG_ROOT / session_id / "stage1_per_step"

    wt = _load(session_dir, "generated/world_template.json")
    if wt:
        _write_json(step_dir / "02_world_template.json", wt)

    bg = _load(session_dir, "generated/plan/world_background.json")
    if bg:
        _write_json(step_dir / "03_world_background.json", bg)

    ep = _load(session_dir, "generated/plan/execution_plan.json")
    if ep:
        _write_json(step_dir / "04_execution_plan.json", ep)

    sc = _load(session_dir, "generated/plan/instance_seed_catalog.json")
    if sc:
        _write_json(step_dir / "05_instance_seed_catalog.json", sc)

    oh = _load(session_dir, "generated/plan/ontology_hints.json")
    if oh:
        _write_json(step_dir / "06_ontology_hints.json", oh)

    templates_summary: dict[str, dict] = {}
    for entity_key in _ENTITY_KEYS:
        idx_path = session_dir / "generated" / "templates" / entity_key / "index.json"
        if not idx_path.exists():
            continue
        idx_data = json.loads(idx_path.read_text("utf-8"))
        dims = idx_data.get("dimensions", [])
        dim_details: dict[str, int] = {}
        for dim_name in dims:
            dim_path = session_dir / "generated" / "templates" / entity_key / f"{dim_name}.json"
            if dim_path.exists():
                dim_data = json.loads(dim_path.read_text("utf-8"))
                dim_details[dim_name] = len(dim_data.get("fields", []))
        templates_summary[entity_key] = {"dimensions": dims, "field_counts": dim_details}
    _write_json(step_dir / "07_entity_templates_summary.json", templates_summary)

    sm = _load(session_dir, "models/schema_manifest.json")
    if sm:
        _write_json(step_dir / "08_schema_manifest.json", sm)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _start_server() -> threading.Thread:
    import uvicorn
    from worldkernel.server import app

    config = uvicorn.Config(app, host="0.0.0.0", port=8100, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def main() -> None:
    print("启动 WorldKernel 服务器...")
    _start_server()
    time.sleep(2.0)

    before = _get_existing_sessions()

    print(f"打开浏览器: {_SERVER_URL}")
    webbrowser.open(_SERVER_URL)

    print("\n在浏览器中输入世界创建需求并点击「开始生成」")
    print("脚本正在监测 templates/ 目录，检测到新 session 后自动校验...")
    print("按 Ctrl+C 退出\n")

    try:
        while True:
            session_id = _wait_for_new_session(before, timeout=600.0)
            if session_id is None:
                print("等待超时，未检测到新 session")
                continue

            session_dir = _TEMPLATES_DIR / session_id
            stats = _Stats()

            _sep(f"检测到新 session: {session_id}")
            print("  等待文件写入完成...")
            _wait_for_stable(session_dir)

            all_files = sorted(
                str(f.relative_to(session_dir)).replace("\\", "/")
                for f in session_dir.rglob("*") if f.is_file()
            )
            print(f"  共 {len(all_files)} 个文件")

            # Stage1 validation
            _validate_structure(session_dir, stats)
            _validate_world_template(session_dir, stats)
            _validate_plan(session_dir, stats)
            _validate_templates(session_dir, stats)

            # Artifact index + per-step dumps
            _build_artifact_index(session_id, session_dir)
            _save_per_step_dumps(session_id, session_dir)

            # Stage2 compilation & visualization
            _run_stage2(session_id, session_dir, stats)

            # Final report
            _sep("测试结果")
            print(f"  总计: {stats.total}  通过: {stats.passed}  失败: {stats.failed}")
            if stats.errors:
                print(f"\n  失败项:")
                for err in stats.errors:
                    print(f"    - {err}")
            if stats.failed == 0:
                print("\n  Stage1 -> Stage2 端到端测试全部通过")
            else:
                print(f"\n  有 {stats.failed} 项失败，请检查")
            _sep()

            before.add(session_id)
            print("\n继续监测中... 可在浏览器中再次提交，或按 Ctrl+C 退出\n")

    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
