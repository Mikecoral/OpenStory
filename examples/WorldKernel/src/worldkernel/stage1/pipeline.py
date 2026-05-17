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


async def run_stage1(raw_input: str) -> SessionInfo:
    session = SessionInfo(source_input=raw_input)
    out_dir = _TEMPLATES_DIR / session.session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        intent: IntentResult = await parse_intent(raw_input)
    except Exception as e:
        raise Stage1Error("intent_parser", e) from e

    try:
        world_type: WorldTemplate = await build_world_template(intent)
    except Exception as e:
        raise Stage1Error("world_type_classifier", e) from e

    try:
        plan: GenerationPlan = await plan_generation(intent, world_type)
    except Exception as e:
        raise Stage1Error("generation_planner", e) from e

    try:
        templates: dict[str, EntityTemplate] = await generate_templates(intent, world_type, plan)
    except Exception as e:
        raise Stage1Error("ontology_selector", e) from e

    _save_json(out_dir / "generated" / "world_template.json", world_type.model_dump())
    _save_plan(out_dir / "generated" / "plan", plan)
    _save_templates(out_dir / "generated" / "templates", templates)
    _save_agent_config(out_dir / "configs" / "agent", templates)

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


def _save_plan(plan_dir: Path, plan: GenerationPlan) -> None:
    _save_json(plan_dir / "steps.json", [s.model_dump() for s in plan.steps])
    _save_json(plan_dir / "ontology_hints.json", plan.ontology_hints.model_dump())

    for category, archetype_dict in [
        ("locations", plan.entity_plan.locations),
        ("characters", plan.entity_plan.characters),
        ("institutions", plan.entity_plan.institutions),
        ("rules", plan.entity_plan.rules),
    ]:
        for archetype_id, seeds in archetype_dict.items():
            _save_json(
                plan_dir / "entity_plan" / category / f"{archetype_id}.json",
                [s.model_dump() for s in seeds],
            )


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
    identity:       IdentityDim
    social_profile: SocialProfileDim
    capabilities:   CapabilitiesDim

  # ── 性格特质 ──────────────────────────────────────────────
  personality:
    personality:    PersonalityDim

  # ── 价值观与记忆 ──────────────────────────────────────────
  values:
    goals:          GoalsDim
    memories:       MemoriesDim

  # ── 运行时状态 ──────────────────────────────────────────────
  state:
    state:          StateDim
"""

_AGENT_DIMS = ["identity", "social_profile", "capabilities",
               "personality", "goals", "memories", "state"]

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
    content: dict = {"name": f"{dim_title}Dim"}

    groups = _FIELD_GROUPS.get(dim_name, [])
    grouped_names: set[str] = set()
    sub_type_defs: list[tuple[str, dict]] = []

    for sub_type_name, parent_field, members in groups:
        grouped_names.update(orig for orig, _ in members)
        content[parent_field] = {"type": sub_type_name}

        sub_def: dict = {}
        for orig_name, new_name in members:
            field = next((f for f in fields if f.name == orig_name), None)
            if field:
                entry: dict = {"type": field.type}
                if field.ref:
                    entry["ref"] = field.ref
                sub_def[new_name] = entry
        sub_type_defs.append((sub_type_name, sub_def))

    for f in fields:
        if f.name in grouped_names:
            continue
        entry: dict = {"type": f.type}
        if f.ref:
            entry["ref"] = f.ref
        if not f.required:
            entry["option"] = True
        content[f.name] = entry

    for sub_name, sub_def in sub_type_defs:
        content[sub_name] = sub_def

    return content


def _save_agent_config(configs_dir: Path, templates: dict[str, EntityTemplate]) -> None:
    char_template = templates.get("character")
    if not char_template:
        return

    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / "agent.yaml").write_text(_AGENT_YAML_TEMPLATE, encoding="utf-8")

    dims_dir = configs_dir / "dims"
    dims_dir.mkdir(parents=True, exist_ok=True)

    for dim_name in _AGENT_DIMS:
        dim_data = char_template.dimensions.get(dim_name)
        if not dim_data:
            continue
        dim_content = _build_dim_yaml(dim_name, dim_data.fields)
        _save_yaml(dims_dir / f"{dim_name}.yaml", dim_content)
