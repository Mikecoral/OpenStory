"""CharacterGenerationTool — generates character profiles via LLM with quality review."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from worldkernel.architect.tools.base import (
    BaseStage2Tool,
    Stage2ToolContext,
    Stage2ToolRequest,
    Stage2ToolResult,
)
from worldkernel.architect.tools.generators.base_generator import (
    assign_entity_ids,
    batch_seeds,
    build_location_summary,
    build_generation_prompt,
    build_seed_list,
    build_world_context,
    introspect_schema,
    parse_and_validate,
)
from worldkernel.architect.tools.identity_allocator import IdentityRegistry
from worldkernel.llm.client import chat_json

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Any:
    """Parse JSON with multiple fallback strategies for LLM output."""
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    import re
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in [('[', ']'), ('{', '}')]:
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1], strict=False)
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"Failed to parse JSON: {text[:200]}...")


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


_GENERATION_SYSTEM = (
    "你是一个世界角色生成器。"
    "根据世界背景和角色种子信息，为每个种子生成完整的人物档案。"
    "每个角色必须严格遵循给定的 schema 结构，包含所有维度。"
    "identity.id 必须使用种子列表中提供的预分配 id，不可自行编造。"
    "人物性格、动机、背景必须具体饱满，符合其 archetype 特征和 importance 级别。"
    "世界特有字段（如门第、特殊能力等）必须与世界观一致。"
    "core 级种子需要丰富详细的描述，minor 级可以相对简洁。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_GENERATION_USER_TEMPLATE = _load_prompt("character_generation_user.md")

_REVIEW_SYSTEM = (
    "你是一个世界构建质量评审专家。"
    "你的任务是对生成的角色数据进行深度质量反思，从多个维度评估并打分。"
    "如发现问题，必须在 corrected_characters 中提供修正后的完整数据。"
    "如无问题，corrected_characters 与输入保持一致。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_REVIEW_USER_TEMPLATE = _load_prompt("character_review_user.md")

_RETRY_SYSTEM = (
    "你是一个世界角色生成器。"
    "之前生成的角色数据质量不达标，请根据审核反馈重新生成。"
    "identity.id 必须使用种子列表中提供的预分配 id，不可自行编造。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_RETRY_USER_TEMPLATE = _load_prompt("character_retry_user.md")


# ---------------------------------------------------------------------------
# Quality threshold
# ---------------------------------------------------------------------------

_QUALITY_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

class CharacterGenerationTool(BaseStage2Tool):
    tool_id = "stage2.character_generator.v1"
    generator_type = "character_generator"
    output_schema_alias = "character_profile"
    capabilities = ("generate_characters",)

    async def run(
        self,
        request: Stage2ToolRequest,
        context: Stage2ToolContext,
    ) -> Stage2ToolResult:
        registry = context.identity_registry
        if registry is None:
            raise RuntimeError("IdentityRegistry not provided in context")

        entry = context.schema_registry.get(
            self.output_schema_alias, source_id=context.source_id,
        )
        ModelClass: type[BaseModel] = entry.model_type
        schema_desc = introspect_schema(ModelClass, schema_entry=entry)

        world_ctx = build_world_context(request)
        loc_ids = registry.lookup(request.resolved_location_seeds, "loc")
        loc_summary = build_location_summary(request.resolved_location_seeds, pre_allocated_ids=loc_ids)

        batches = batch_seeds(request.resolved_character_seeds, request.batch_size)
        total_batches = len(batches)

        all_items: list[Any] = []
        all_refs: list[str] = []
        all_warnings: list[str] = []
        all_review_scores: list[float] = []
        retry_count = 0
        failed_batches = 0

        for batch_index, batch in enumerate(batches, 1):
            try:
                items, refs, warnings, review_score, retried = await self._process_batch(
                    batch=batch,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    world_ctx=world_ctx,
                    schema_desc=schema_desc,
                    loc_summary=loc_summary,
                    ModelClass=ModelClass,
                    registry=registry,
                )
                if not items:
                    failed_batches += 1
                
                all_items.extend(items)
                all_refs.extend(refs)
                all_warnings.extend(warnings)
                if review_score is not None:
                    all_review_scores.append(review_score)
                if retried:
                    retry_count += 1

            except Exception as exc:
                failed_batches += 1
                all_warnings.append(f"batch {batch_index}/{total_batches} failed with exception: {exc}")

        if not all_items:
            raise RuntimeError(
                f"CharacterGenerationTool: all {total_batches} batches failed, "
                f"no characters generated. Warnings: {'; '.join(all_warnings)}"
            )

        # Overall completeness check + consolidated retry
        total_seeds = len(request.resolved_character_seeds)
        if len(all_items) < total_seeds:
            # Collect missing seeds
            generated_ids: set[str] = set()
            for item in all_items:
                identity = getattr(item, "identity", None)
                if identity and hasattr(identity, "id") and identity.id:
                    generated_ids.add(identity.id)

            all_seeds = request.resolved_character_seeds
            pre_ids = registry.lookup(all_seeds, "char")
            missing_seeds = [
                s for s in all_seeds
                if pre_ids.get(s.seed_id) not in generated_ids
            ]

            if missing_seeds:
                all_warnings.append(
                    f"consolidated retry: {len(missing_seeds)} seeds missing, "
                    f"retrying as one batch"
                )
                try:
                    items, refs, retry_warnings, _score, _retried = await self._process_batch(
                        batch=missing_seeds,
                        batch_index=total_batches + 1,
                        total_batches=total_batches + 1,
                        world_ctx=world_ctx,
                        schema_desc=schema_desc,
                        loc_summary=loc_summary,
                        ModelClass=ModelClass,
                        registry=registry,
                    )
                    all_items.extend(items)
                    all_refs.extend(refs)
                    all_warnings.extend(retry_warnings)
                except Exception as exc:
                    all_warnings.append(f"consolidated retry failed: {exc}")

            # Final check
            if len(all_items) < total_seeds:
                raise RuntimeError(
                    f"CharacterGenerationTool: generated {len(all_items)}/{total_seeds} characters, "
                    f"{total_seeds - len(all_items)} seeds missing after all retries. "
                    f"Warnings: {'; '.join(all_warnings)}"
                )

        quality_summary = self._build_quality_summary(
            total_seeds=len(request.resolved_character_seeds),
            total_generated=len(all_items),
            total_batches=total_batches,
            failed_batches=failed_batches,
            review_scores=all_review_scores,
            retry_count=retry_count,
            warnings=all_warnings,
        )

        return Stage2ToolResult(
            artifact_type=self.output_schema_alias,
            items=all_items,
            produced_refs=all_refs,
            warnings=all_warnings,
            provenance={
                "tool_id": self.tool_id,
                "total_batches": total_batches,
                "failed_batches": failed_batches,
                "total_seeds": len(request.resolved_character_seeds),
                "total_generated": len(all_items),
                "quality_summary": quality_summary,
                "seed_to_entity_mapping": registry.seed_mapping,
            },
        )

    def _unwrap_json_list(self, gen_data: Any) -> list[Any]:
        """防弹拆包：防止大模型外面套壳字典或多层无限列表"""
        if isinstance(gen_data, dict):
            for v in gen_data.values():
                if isinstance(v, list):
                    gen_data = v
                    break
            else:
                gen_data = [gen_data]

        # 无限剥除外层的单元素列表，直到露出真面目
        while isinstance(gen_data, list) and len(gen_data) == 1 and isinstance(gen_data[0], list):
            gen_data = gen_data[0]

        if not isinstance(gen_data, list):
            return [gen_data]
        return gen_data

    async def _process_batch(
        self,
        batch: list,
        batch_index: int,
        total_batches: int,
        world_ctx: dict[str, str],
        schema_desc: str,
        loc_summary: str,
        ModelClass: type[BaseModel],
        registry: IdentityRegistry,
    ) -> tuple[list[Any], list[str], list[str], float | None, bool]:
        warnings: list[str] = []
        retried = False

        pre_ids = registry.lookup(batch, "char")

        gen_prompt = build_generation_prompt(_GENERATION_USER_TEMPLATE, {
            **world_ctx,
            "schema_description": schema_desc,
            "location_seed_summary": loc_summary,
            "seed_list": build_seed_list(batch, pre_ids),
            "batch_index": str(batch_index),
            "total_batches": str(total_batches),
            "seed_count": str(len(batch)),
        })

        raw_gen = await chat_json(gen_prompt, system=_GENERATION_SYSTEM)
        gen_data = self._unwrap_json_list(_safe_json_loads(raw_gen))

        review_score: float | None = None
        try:
            review_prompt = build_generation_prompt(_REVIEW_USER_TEMPLATE, {
                **world_ctx,
                "schema_description": schema_desc,
                "generated_characters_json": json.dumps(gen_data, ensure_ascii=False, indent=2),
            })
            raw_review = await chat_json(review_prompt, system=_REVIEW_SYSTEM)
            review_result = _safe_json_loads(raw_review)

            if isinstance(review_result, dict) and "review" in review_result:
                review_info = review_result["review"]
                review_score = review_info.get("overall_score")
                issues = review_info.get("issues", [])

                # Use corrected characters if available
                corrected = review_result.get("corrected_characters")
                if issues:
                    if isinstance(corrected, list) and corrected:
                        gen_data = corrected
                        warnings.append(
                            f"batch {batch_index} review (score={review_score}): "
                            f"发现 {len(issues)} 个问题并已自动修正"
                        )
                    else:
                        warnings.append(
                            f"batch {batch_index} review (score={review_score}): "
                            + "; ".join(str(i) for i in issues)
                        )
                        warnings.append(f"batch {batch_index}: review returned no corrected_characters")
                elif isinstance(corrected, list) and corrected:
                    gen_data = corrected

                if review_score is not None and review_score < _QUALITY_THRESHOLD:
                    retried = True
                    retry_items, retry_refs, retry_warnings = await self._retry_batch(
                        batch=batch,
                        batch_index=batch_index,
                        total_batches=total_batches,
                        world_ctx=world_ctx,
                        schema_desc=schema_desc,
                        loc_summary=loc_summary,
                        ModelClass=ModelClass,
                        review_issues=issues,
                        registry=registry,
                        pre_ids=pre_ids,
                    )
                    if retry_items:
                        warnings.extend(retry_warnings)
                        return retry_items, retry_refs, warnings, review_score, retried
                    else:
                        warnings.append(f"batch {batch_index}: retry also failed, falling back to original output")

            else:
                warnings.append(f"batch {batch_index}: review returned unexpected format")

        except Exception as review_exc:
            warnings.append(f"batch {batch_index}: review step failed ({review_exc})")

        # 【核心修正】逐个校验，按名称匹配 seed，绝不连坐崩溃
        seed_by_name = {s.name: s for s in batch}
        validated = []
        valid_seeds = []
        for i, item_data in enumerate(gen_data):
            if not isinstance(item_data, dict):
                warnings.append(f"batch {batch_index}: item[{i}] is not a dict, skipped")
                continue

            # 按名称匹配 seed
            item_name = ""
            id_obj = item_data.get("identity")
            if isinstance(id_obj, dict):
                item_name = id_obj.get("name", "")

            matched_seed = seed_by_name.get(item_name)
            if matched_seed is None:
                # fallback: 按位置索引（跳过已使用的 seed）
                used = {s.seed_id for s in valid_seeds}
                for s in batch:
                    if s.seed_id not in used:
                        matched_seed = s
                        warnings.append(f"batch {batch_index}: item '{item_name}' matched by positional fallback")
                        break

            if matched_seed is None:
                warnings.append(f"batch {batch_index}: item[{i}] '{item_name}' has no matching seed, skipped")
                continue

            item_val, item_warns = parse_and_validate([item_data], ModelClass, [matched_seed])
            warnings.extend(item_warns)
            if item_val:
                validated.append(item_val[0])
                valid_seeds.append(matched_seed)

        # 完整性检查 + 缺失种子重试
        if len(validated) < len(batch):
            missing_count = len(batch) - len(validated)
            warnings.append(
                f"batch {batch_index}: generated {len(validated)}/{len(batch)} items, "
                f"{missing_count} missing; retrying for missing seeds"
            )
            generated_names = {getattr(getattr(v, 'identity', None), 'name', '') for v in validated}
            missing_seeds = [s for s in batch if s.name not in generated_names]
            if missing_seeds:
                retry_items, retry_refs, retry_warnings = await self._retry_batch(
                    batch=missing_seeds,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    world_ctx=world_ctx,
                    schema_desc=schema_desc,
                    loc_summary=loc_summary,
                    ModelClass=ModelClass,
                    review_issues=[f"上一轮缺少 {missing_count} 个角色，请为以下种子生成角色"],
                    registry=registry,
                    pre_ids=pre_ids,
                )
                if retry_items:
                    validated.extend(retry_items)
                    valid_seeds.extend(missing_seeds)
                    warnings.extend(retry_warnings)
                else:
                    raise RuntimeError(
                        f"CharacterGenerationTool: batch {batch_index} completeness retry failed, "
                        f"{missing_count} seeds still missing. Warnings: {'; '.join(warnings)}"
                    )

        refs = assign_entity_ids(validated, valid_seeds, registry, "char")

        return validated, refs, warnings, review_score, retried

    async def _retry_batch(
        self,
        batch: list,
        batch_index: int,
        total_batches: int,
        world_ctx: dict[str, str],
        schema_desc: str,
        loc_summary: str,
        ModelClass: type[BaseModel],
        review_issues: list[Any],
        registry: IdentityRegistry,
        pre_ids: dict[str, str],
    ) -> tuple[list[Any], list[str], list[str]]:
        warnings: list[str] = []
        issues_str = "\n".join(f"  - {i}" for i in review_issues) if review_issues else "  无具体问题"

        retry_prompt = build_generation_prompt(_RETRY_USER_TEMPLATE, {
            **world_ctx,
            "schema_description": schema_desc,
            "location_seed_summary": loc_summary,
            "seed_list": build_seed_list(batch, pre_ids),
            "review_issues": issues_str,
            "seed_count": str(len(batch)),
        })

        try:
            raw_retry = await chat_json(retry_prompt, system=_RETRY_SYSTEM)
            retry_data = self._unwrap_json_list(_safe_json_loads(raw_retry))

            seed_by_name = {s.name: s for s in batch}
            validated = []
            valid_seeds = []
            for i, item_data in enumerate(retry_data):
                if not isinstance(item_data, dict):
                    continue
                item_name = ""
                id_obj = item_data.get("identity")
                if isinstance(id_obj, dict):
                    item_name = id_obj.get("name", "")
                matched_seed = seed_by_name.get(item_name)
                if matched_seed is None:
                    used = {s.seed_id for s in valid_seeds}
                    for s in batch:
                        if s.seed_id not in used:
                            matched_seed = s
                            break
                if matched_seed is None:
                    continue
                item_val, item_warns = parse_and_validate([item_data], ModelClass, [matched_seed])
                warnings.extend(item_warns)
                if item_val:
                    validated.append(item_val[0])
                    valid_seeds.append(matched_seed)

            warnings.append(f"batch {batch_index}: retried due to low quality score")
            refs = assign_entity_ids(validated, valid_seeds, registry, "char")

            return validated, refs, warnings

        except Exception as exc:
            warnings.append(f"batch {batch_index}: retry failed ({exc})")
            return [], [], warnings

    @staticmethod
    def _build_quality_summary(
        total_seeds: int,
        total_generated: int,
        total_batches: int,
        failed_batches: int,
        review_scores: list[float],
        retry_count: int,
        warnings: list[str],
    ) -> dict[str, Any]:
        avg_score = sum(review_scores) / len(review_scores) if review_scores else 0.0
        key_issues: list[str] = []
        for w in warnings:
            if "review" in w.lower() and "score=" in w.lower():
                key_issues.append(w)
        return {
            "total_seeds": total_seeds,
            "total_generated": total_generated,
            "batches_processed": total_batches - failed_batches,
            "avg_review_score": round(avg_score, 2),
            "retry_count": retry_count,
            "key_issues": key_issues[:5],
        }