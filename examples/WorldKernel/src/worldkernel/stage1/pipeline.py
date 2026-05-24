from __future__ import annotations

import json
from pathlib import Path

import yaml

from worldkernel.stage1.types import (
    EntityTemplate,
    GenerationPlan,
    IntentResult,
    WorldTemplate,
)
from worldkernel.stage1.world_spec import SessionInfo
from worldkernel.constraints import GenerationConstraints, load_generation_constraints
from worldkernel.stage1.generation_planner import plan_generation
from worldkernel.stage1.intent_parser import parse_intent
from worldkernel.stage1.ontology_selector import generate_templates
from worldkernel.stage1.world_type_classifier import build_world_template

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"


class Stage1Error(Exception):
    def __init__(self, step: str, cause: Exception) -> None:
        self.step = step
        self.cause = cause
        super().__init__(f"Stage 1 failed at [{step}]: {cause}")


async def run_stage1(
    raw_input: str,
    constraints: GenerationConstraints | None = None,
) -> SessionInfo:
    if constraints is None:
        constraints = load_generation_constraints()
    session = SessionInfo(source_input=raw_input)
    out_dir = _TEMPLATES_DIR / session.session_id

    try:
        intent: IntentResult = await parse_intent(raw_input)
    except Exception as e:
        raise Stage1Error("intent_parser", e) from e

    try:
        world_type: WorldTemplate = await build_world_template(intent)
    except Exception as e:
        raise Stage1Error("world_type_classifier", e) from e

    try:
        plan: GenerationPlan = await plan_generation(intent, world_type, constraints=constraints)
    except Exception as e:
        raise Stage1Error("generation_planner", e) from e

    try:
        templates: dict[str, EntityTemplate] = await generate_templates(intent, world_type, plan)
    except Exception as e:
        raise Stage1Error("ontology_selector", e) from e

    _save_json(out_dir / "generated" / "world_template.json", world_type.model_dump())
    _save_plan(out_dir / "generated" / "plan", plan, world_type, session.session_id)
    _save_templates(out_dir / "generated" / "templates", templates)
    _save_entity_configs(out_dir / "configs", templates)
    _generate_pydantic_models(out_dir / "models", out_dir / "configs")
    _save_schema_manifest(out_dir / "models")
    _save_artifact_manifest(out_dir, session.session_id)

    return session


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _save_plan(plan_dir: Path, plan: GenerationPlan, world_type: WorldTemplate, session_id: str) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)

    _save_json(plan_dir / "ontology_hints.json", plan.ontology_hints.model_dump())

    catalog: dict = {
        "session_id": session_id,
        "instance_seeds": {"location": [], "character": []},
    }
    for archetype_id, seeds in plan.entity_plan.locations.items():
        for s in seeds:
            d = s.model_dump()
            d["archetype_id"] = archetype_id
            d.pop("entity_type", None)
            catalog["instance_seeds"]["location"].append(d)
    for archetype_id, seeds in plan.entity_plan.characters.items():
        for s in seeds:
            d = s.model_dump()
            d["archetype_id"] = archetype_id
            d.pop("entity_type", None)
            catalog["instance_seeds"]["character"].append(d)
    _save_json(plan_dir / "instance_seed_catalog.json", catalog)

    _save_json(plan_dir / "execution_plan.json", {"steps": [s.model_dump() for s in plan.steps]})

    bg = {
        "world_name": world_type.world_name,
        "world_origin_summary": world_type.world_origin_summary,
        "primary": world_type.primary,
        "secondary": world_type.secondary,
        "tags": world_type.tags,
        "scope": world_type.scope,
        "simulation_start": world_type.simulation_start.model_dump(),
        "world_constraints": [c.model_dump() for c in world_type.world_constraints],
    }
    _save_json(plan_dir / "world_background.json", bg)


def _save_templates(templates_dir: Path, templates: dict[str, EntityTemplate]) -> None:
    for entity_key, entity_template in templates.items():
        ent_dir = templates_dir / entity_key
        dim_names = list(entity_template.dimensions.keys())
        _save_json(ent_dir / "index.json", {"dimensions": dim_names})
        for dim_name, dim_data in entity_template.dimensions.items():
            _save_json(ent_dir / f"{dim_name}.json", dim_data.model_dump())


_AGENT_YAML_TEMPLATE = """\
# ============================================================
#  Agent 全局配置模版
#  定义 Agent 实体的维度组成，每个维度引用独立的类型定义文件
#  此文件结构固定，不随世界变化
# ============================================================

name: Agent
entity_type: character

dimensions:

  # ── 角色档案 ──────────────────────────────────────────────
  profile:
    identity:
      type: IdentityDim
      path: dims/identity.yaml
    social_profile:
      type: SocialProfileDim
      path: dims/social_profile.yaml
    capabilities:
      type: CapabilitiesDim
      path: dims/capabilities.yaml

  # ── 性格特质 ──────────────────────────────────────────────
  personality:
    personality:
      type: PersonalityDim
      path: dims/personality.yaml

  # ── 价值观与记忆 ──────────────────────────────────────────
  values:
    goals:
      type: GoalsDim
      path: dims/goals.yaml
    memories:
      type: MemoriesDim
      path: dims/memories.yaml

  # ── 运行时状态 ──────────────────────────────────────────────
  state:
    state:
      type: StateDim
      path: dims/state.yaml
"""

_LOCATION_YAML_TEMPLATE = """\
# ============================================================
#  Location 全局配置模版
#  定义 Location 实体的维度组成
# ============================================================

name: Location
entity_type: location

dimensions:

  # ── 地点档案 ──────────────────────────────────────────────
  profile:
    identity:
      type: IdentityDim
      path: dims/identity.yaml

  # ── 访问控制 ──────────────────────────────────────────────
  access:
    access:
      type: AccessDim
      path: dims/access.yaml

  # ── 运行时状态 ──────────────────────────────────────────────
  state:
    state:
      type: StateDim
      path: dims/state.yaml
"""

_PATH_YAML_TEMPLATE = """\
# ============================================================
#  Path 全局配置模版
#  定义地点路径/通道实体的维度组成
# ============================================================

name: Path
entity_type: path

dimensions:

  # ── 路径档案 ──────────────────────────────────────────────
  profile:
    identity:
      type: IdentityDim
      path: dims/identity.yaml

  # ── 端点连接 ──────────────────────────────────────────────
  endpoints:
    endpoints:
      type: EndpointsDim
      path: dims/endpoints.yaml

  # ── 路径属性 ──────────────────────────────────────────────
  properties:
    properties:
      type: PropertiesDim
      path: dims/properties.yaml

  # ── 通行条件 ──────────────────────────────────────────────
  conditions:
    conditions:
      type: ConditionsDim
      path: dims/conditions.yaml
"""

_RELATION_YAML_TEMPLATE = """\
# ============================================================
#  Relation 全局配置模版
#  定义关系实体的维度组成
# ============================================================

name: Relation
entity_type: relation

dimensions:

  # ── 关系边 ────────────────────────────────────────────────
  edge:
    edge:
      type: EdgeDim
      path: dims/edge.yaml

  # ── 关系属性 ──────────────────────────────────────────────
  properties:
    properties:
      type: PropertiesDim
      path: dims/properties.yaml
"""

_ENTITY_CONFIGS: list[dict] = [
    {
        "dir_name": "agent",
        "source_entity": "character",
        "template": _AGENT_YAML_TEMPLATE,
        "main_file": "agent.yaml",
        "dims": ["identity", "social_profile", "capabilities",
                 "personality", "goals", "memories", "state"],
    },
    {
        "dir_name": "location",
        "source_entity": "location",
        "template": _LOCATION_YAML_TEMPLATE,
        "main_file": "location.yaml",
        "dims": ["identity", "access", "state"],
    },
    {
        "dir_name": "path",
        "source_entity": "path",
        "template": _PATH_YAML_TEMPLATE,
        "main_file": "path.yaml",
        "dims": ["identity", "endpoints", "properties", "conditions"],
    },
    {
        "dir_name": "relation",
        "source_entity": "relation",
        "template": _RELATION_YAML_TEMPLATE,
        "main_file": "relation.yaml",
        "dims": ["edge", "properties"],
    },
]

_STAGE2_SCHEMA_ALIASES_BY_DIR_NAME: dict[str, tuple[str, str]] = {
    "location": ("location_profile", "Stage1 generated location model."),
    "agent": (
        "character_profile",
        "Stage1 generated agent model used as the Stage2 character schema.",
    ),
    "path": ("path_edge", "Stage1 generated path model."),
    "relation": ("relation_edge", "Stage1 generated relation model."),
}

_FIELD_GROUPS: dict[str, list[tuple[str, str, list[tuple[str, str]]]]] = {
    "state": [
        ("LocationRef", "location", [("location_id", "location_id")]),
        ("Position", "position", [("position_x", "x"), ("position_y", "y")]),
    ],
    "memories": [
        ("KnowledgeBase", "knowledge",
         [("world_knowledge", "world_knowledge"), ("social_knowledge", "social_knowledge")]),
    ],
}


def _build_dim_yaml(dim_name: str, fields: list) -> dict:
    dim_title = dim_name.title().replace("_", "")
    content: dict = {"dim_name": f"{dim_title}Dim"}

    groups = _FIELD_GROUPS.get(dim_name, [])
    grouped_names: set[str] = set()

    for _sub_type_name, parent_field, members in groups:
        sub_def: dict = {}
        matched_names: set[str] = set()
        for orig_name, new_name in members:
            field = next((f for f in fields if f.name == orig_name), None)
            if field:
                entry: dict = {"type": field.type}
                if field.ref:
                    entry["ref"] = field.ref
                sub_def[new_name] = entry
                matched_names.add(orig_name)
        if sub_def:
            grouped_names.update(matched_names)
            content[parent_field] = sub_def

    for f in fields:
        if f.name in grouped_names:
            continue
        entry: dict = {"type": f.type}
        if f.ref:
            entry["ref"] = f.ref
        if not f.required:
            entry["option"] = True
        content[f.name] = entry

    return content


def _save_entity_configs(configs_dir: Path, templates: dict[str, EntityTemplate]) -> None:
    for cfg in _ENTITY_CONFIGS:
        entity_template = templates.get(cfg["source_entity"])
        if not entity_template:
            continue

        ent_cfg_dir = configs_dir / cfg["dir_name"]
        ent_cfg_dir.mkdir(parents=True, exist_ok=True)
        (ent_cfg_dir / cfg["main_file"]).write_text(cfg["template"], encoding="utf-8")

        dims_dir = ent_cfg_dir / "dims"
        dims_dir.mkdir(parents=True, exist_ok=True)

        for dim_name in cfg["dims"]:
            dim_data = entity_template.dimensions.get(dim_name)
            if not dim_data:
                continue
            dim_content = _build_dim_yaml(dim_name, dim_data.fields)
            _save_yaml(dims_dir / f"{dim_name}.yaml", dim_content)


# ── Pydantic 模型代码生成 ─────────────────────────────────────────────

_PY_TYPE_MAP: dict[str, tuple[str, str]] = {
    "str": ("str", '""'),
    "int": ("int", "0"),
    "float": ("float", "0.0"),
    "bool": ("bool", "False"),
    "list_str": ("list[str]", "[]"),
}


def _to_class_name(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


def _generate_pydantic_models(models_dir: Path, configs_dir: Path) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)

    for cfg in _ENTITY_CONFIGS:
        dims_dir = configs_dir / cfg["dir_name"] / "dims"
        if not dims_dir.exists():
            continue

        entity_name = _to_class_name(cfg["dir_name"])
        model_class_name = f"{entity_name}Model"

        lines: list[str] = [
            f'"""Auto-generated {entity_name} Pydantic model."""',
            "from pydantic import BaseModel",
            "",
            "",
        ]

        dim_classes: list[tuple[str, str]] = []

        for dim_name in cfg["dims"]:
            dim_file = dims_dir / f"{dim_name}.yaml"
            if not dim_file.exists():
                continue

            dim_data = yaml.safe_load(dim_file.read_text(encoding="utf-8"))
            dim_class_name = dim_data.get("dim_name", _to_class_name(dim_name) + "Dim")

            nested_groups: list[tuple[str, str, dict]] = []
            flat_fields: list[tuple[str, dict]] = []

            for key, val in dim_data.items():
                if key == "dim_name":
                    continue
                if isinstance(val, dict) and "type" not in val:
                    if val:
                        group_class = _to_class_name(key) + "Group"
                        nested_groups.append((key, group_class, val))
                elif isinstance(val, dict) and "type" in val:
                    flat_fields.append((key, val))

            for _field_name, group_class, group_fields in nested_groups:
                lines.append(f"class {group_class}(BaseModel):")
                for fname, fval in group_fields.items():
                    ftype = fval.get("type", "str")
                    py_type, default = _PY_TYPE_MAP.get(ftype, ("str", '""'))
                    lines.append(f"    {fname}: {py_type} = {default}")
                lines.append("")
                lines.append("")

            lines.append(f"class {dim_class_name}(BaseModel):")
            has_fields = False
            for field_name, group_class, _group_fields in nested_groups:
                lines.append(f"    {field_name}: {group_class} = {group_class}()")
                has_fields = True
            for fname, fval in flat_fields:
                ftype = fval.get("type", "str")
                py_type, default = _PY_TYPE_MAP.get(ftype, ("str", '""'))
                comment = "  # world-specific" if fval.get("option") else ""
                lines.append(f"    {fname}: {py_type} = {default}{comment}")
                has_fields = True
            if not has_fields:
                lines.append("    pass")
            lines.append("")
            lines.append("")

            dim_classes.append((dim_class_name, dim_name))

        lines.append(f"class {model_class_name}(BaseModel):")
        for dim_class_name, dim_field_name in dim_classes:
            lines.append(f"    {dim_field_name}: {dim_class_name} = {dim_class_name}()")
        lines.append("")

        model_file = models_dir / f"{cfg['dir_name']}_model.py"
        model_file.write_text("\n".join(lines), encoding="utf-8")


def _save_schema_manifest(models_dir: Path) -> None:
    manifest = {
        "schemas": [
            {
                "alias": alias,
                "file": f"{cfg['dir_name']}_model.py",
                "class_name": f"{_to_class_name(cfg['dir_name'])}Model",
                "version": "v1",
                "description": description,
            }
            for cfg in _ENTITY_CONFIGS
            if cfg["dir_name"] in _STAGE2_SCHEMA_ALIASES_BY_DIR_NAME
            for alias, description in [_STAGE2_SCHEMA_ALIASES_BY_DIR_NAME[cfg["dir_name"]]]
        ]
    }
    _save_json(models_dir / "schema_manifest.json", manifest)


def _save_artifact_manifest(session_root: Path, session_id: str) -> None:
    manifest = {
        "session_id": session_id,
        "world_id": session_id,
        "world_background_path": "generated/plan/world_background.json",
        "execution_plan_path": "generated/plan/execution_plan.json",
        "instance_seed_catalog_path": "generated/plan/instance_seed_catalog.json",
        "world_template_path": "generated/world_template.json",
        "schema_manifest_path": "models/schema_manifest.json",
        "provenance": {
            "source": "stage1.pipeline",
            "session_root": str(session_root),
        },
    }
    _save_json(session_root / "generated" / "artifact_manifest.json", manifest)
