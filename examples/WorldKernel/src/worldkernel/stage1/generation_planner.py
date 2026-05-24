from __future__ import annotations

import json
import logging
from pathlib import Path

from worldkernel.constraints import GenerationConstraints, truncate_seeds
from worldkernel.llm.client import chat_json
from worldkernel.stage1.types import EntitySeed, GenerationPlan, IntentResult, WorldTemplate

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "plan_generation.md"

_SYSTEM = (
    "你是一个世界生成计划制定模块。"
    "你的职责是根据用户意图和世界模版，"
    "制定世界内容的生成步骤列表，同时生成六类实体模版的语义指引。"
    "不直接生成任何世界内容。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)


def _fmt_archetypes(archetypes: list) -> str:
    return ", ".join(a.type_name for a in archetypes) or "无"


def _fmt_constraints(constraints: list) -> str:
    return ", ".join(c.name for c in constraints) or "无"


async def plan_generation(
    intent: IntentResult,
    world_type: WorldTemplate,
    constraints: GenerationConstraints | None = None,
) -> GenerationPlan:
    type_summary = world_type.world_origin_summary or world_type.primary
    if world_type.secondary:
        type_summary += f"（兼含 {world_type.secondary}）"

    template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        template
        .replace("{{user_goal}}", intent.user_intent or intent.raw_text)
        .replace("{{world_type_summary}}", type_summary)
        .replace("{{tags}}", ", ".join(world_type.tags) or "无")
        .replace("{{location_archetypes}}", _fmt_archetypes(world_type.location_archetypes))
        .replace("{{character_archetypes}}", _fmt_archetypes(world_type.character_archetypes))
        .replace("{{rule_archetypes}}", _fmt_archetypes(world_type.rule_archetypes))
        .replace("{{world_constraints}}", _fmt_constraints(world_type.world_constraints))
    )
    # Inject hard constraints into prompt
    if constraints and (constraints.max_locations > 0 or constraints.max_characters > 0):
        limit_lines: list[str] = []
        if constraints.max_locations > 0:
            limit_lines.append(f"- locations 总数（所有 archetype 合计）不超过 {constraints.max_locations} 个")
        if constraints.max_characters > 0:
            limit_lines.append(f"- characters 总数（所有 archetype 合计）不超过 {constraints.max_characters} 个")
        prompt += "\n\n**硬性约束（必须遵守）：**\n" + "\n".join(limit_lines)

    raw = await chat_json(prompt, system=_SYSTEM)
    data = json.loads(raw)

    # 新格式：顶层含 steps + entity_plan + ontology_hints
    # 容错：LLM 仍返回裸步骤列表时包装为 {"steps": [...]}
    if isinstance(data, list):
        data = {"steps": data}
    elif "steps" not in data and "entity_plan" not in data:
        # 单层包装，如 {"generation_plan": {...}}
        if len(data) == 1:
            data = next(iter(data.values()))

    plan = GenerationPlan.model_validate(data)

    # Post-LLM truncation: enforce limits as safety net
    if constraints:
        loc_flat = [s for seeds in plan.entity_plan.locations.values() for s in seeds]
        char_flat = [s for seeds in plan.entity_plan.characters.values() for s in seeds]
        loc_kept, loc_warns = truncate_seeds(loc_flat, constraints.max_locations, "location")
        char_kept, char_warns = truncate_seeds(char_flat, constraints.max_characters, "character")
        if loc_warns or char_warns:
            plan = _rebuild_plan_with_kept(plan, loc_kept, char_kept)

    return plan


def _rebuild_plan_with_kept(
    plan: GenerationPlan,
    loc_kept: list[EntitySeed],
    char_kept: list[EntitySeed],
) -> GenerationPlan:
    """Rebuild EntityPlan dict structure after truncation."""
    loc_kept_set = set(id(s) for s in loc_kept)
    char_kept_set = set(id(s) for s in char_kept)

    new_locations: dict[str, list[EntitySeed]] = {}
    for archetype_id, seeds in plan.entity_plan.locations.items():
        kept = [s for s in seeds if id(s) in loc_kept_set]
        if kept:
            new_locations[archetype_id] = kept

    new_characters: dict[str, list[EntitySeed]] = {}
    for archetype_id, seeds in plan.entity_plan.characters.items():
        kept = [s for s in seeds if id(s) in char_kept_set]
        if kept:
            new_characters[archetype_id] = kept

    logger.info(
        "Rebuilt plan after truncation: locations %d->%d, characters %d->%d",
        sum(len(v) for v in plan.entity_plan.locations.values()),
        sum(len(v) for v in new_locations.values()),
        sum(len(v) for v in plan.entity_plan.characters.values()),
        sum(len(v) for v in new_characters.values()),
    )

    return plan.model_copy(update={
        "entity_plan": plan.entity_plan.model_copy(update={
            "locations": new_locations,
            "characters": new_characters,
        }),
    })
