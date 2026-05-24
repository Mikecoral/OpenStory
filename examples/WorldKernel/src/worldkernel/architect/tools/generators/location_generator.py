"""LocationGenerationTool — generates location profiles via LLM with quality review."""

from __future__ import annotations

import json
import logging
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
    build_character_summary,
    build_generation_prompt,
    build_seed_list,
    build_world_context,
    introspect_schema,
    parse_and_validate,
)
from worldkernel.architect.tools.identity_allocator import IdentityAllocator
from worldkernel.llm.client import chat_json

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Any:
    """Parse JSON with multiple fallback strategies for LLM output."""
    # Strategy 1: strict=False
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    # Strategy 2: remove trailing commas before } or ]
    import re
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass
    # Strategy 3: try to find the outermost array/object and parse just that
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

_GENERATION_SYSTEM = (
    "你是一个世界地点生成器。"
    "根据世界背景和地点种子信息，为每个种子生成完整的地点档案。"
    "每个地点必须严格遵循给定的 schema 结构，包含所有维度。"
    "id 字段必须使用提供的 stable_seed_ref，不可自行编造。"
    "描述必须具体、有画面感，不能泛泛而谈。"
    "必须体现种子的 archetype 特征和 importance 级别差异。"
    "世界特有字段必须与世界观一致。"
    "core 级种子需要丰富详细的描述，minor 级可以相对简洁。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_GENERATION_USER_TEMPLATE = """\
## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 规模：{{scope}}
- 标签：{{tags}}
- 仿真起始：{{simulation_start}}
- 世界约束：
{{world_constraints}}

## 角色种子（供参考，无需生成）
{{character_seed_summary}}

## 地点 Schema 结构

每个地点对象必须包含以下维度：
{{schema_description}}

## 待生成的地点种子（本批次 {{batch_index}}/{{total_batches}}）

{{seed_list}}

## 输出要求

输出一个 JSON 数组，每个元素对应一个地点种子。
每个地点的 identity.id 必须严格等于该种子的 stable_seed_ref。
根据种子的 archetype_id、importance、role_in_world 填充各维度字段。
世界特有字段应结合世界背景知识合理填写。
core 级别的种子应有更丰富详细的描述，minor 级别可以相对简洁。

输出格式示例：
```json
[
  {{
    "identity": {{
      "id": "seed:...",
      "name": "地点名称",
      "type": "archetype_id",
      "description": "详细描述...",
      ...
    }},
    "access": {{
      "permissions": "...",
      "access_level": "...",
      ...
    }},
    "state": {{
      "current_state": "...",
      "ownership": "...",
      "capacity": 0,
      ...
    }}
  }}
]
```"""

_REVIEW_SYSTEM = (
    "你是一个世界构建质量评审专家。"
    "你的任务是对生成的地点数据进行深度质量反思，从多个维度评估并打分。"
    "如发现问题，必须在 corrected_locations 中提供修正后的完整数据。"
    "如无问题，corrected_locations 与输入保持一致。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_REVIEW_USER_TEMPLATE = """\
## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 地点 Schema 要求

{{schema_description}}

## 待审核的地点数据

```json
{{generated_locations_json}}
```

## 审核维度（每个维度 1-5 分）

1. **叙事丰富度**：描述是否有画面感和沉浸感？是否让人能想象出这个地点的样子？
2. **世界一致性**：地点是否与世界约束保持一致？是否存在违反世界观的设定？
3. **原型契合度**：地点是否准确体现了其 archetype 的特征？
4. **区分度**：同一 archetype 下的不同地点是否有足够差异？（不能雷同）
5. **层级合理性**：core/major/minor 的重要性差异是否在描述深度和字段丰富度上体现出来？
6. **社交网络关联**：description 中是否合理提及了可能的 resident_npcs 或相关角色？
7. **access/state 合理性**：访问控制和状态描述是否符合该地点在叙事中的定位？

## 输出格式

```json
{{
  "review": {{
    "scores": {{
      "narrative_richness": 0,
      "world_consistency": 0,
      "archetype_fit": 0,
      "differentiation": 0,
      "importance_tiering": 0,
      "social_links": 0,
      "access_state_fit": 0
    }},
    "overall_score": 0.0,
    "issues": ["具体问题描述1", "具体问题描述2"],
    "corrections": [
      {{"index": 0, "field": "identity.description", "reason": "修正原因", "suggested": "修正后的内容"}}
    ]
  }},
  "corrected_locations": [...]
}}
```

如发现任何问题，在 issues 中列出，在 corrections 中说明具体修正，corrected_locations 中输出修正后的完整 JSON 数组。
如无问题，issues 为空数组，corrections 为空数组，corrected_locations 原样输出。"""

_RETRY_SYSTEM = (
    "你是一个世界地点生成器。"
    "之前生成的地点数据质量不达标，请根据审核反馈重新生成。"
    "id 字段必须使用提供的 stable_seed_ref，不可自行编造。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_RETRY_USER_TEMPLATE = """\
## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 上一轮审核发现的问题

{{review_issues}}

## 地点 Schema 结构

{{schema_description}}

## 角色种子（供参考）
{{character_seed_summary}}

## 待重新生成的地点种子

{{seed_list}}

## 输出要求

输出一个 JSON 数组，每个元素对应一个地点种子。
每个地点的 identity.id 必须严格等于该种子的 stable_seed_ref。
请特别注意审核反馈中提到的问题，针对性改进。
"""


# ---------------------------------------------------------------------------
# Quality threshold
# ---------------------------------------------------------------------------

_QUALITY_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

class LocationGenerationTool(BaseStage2Tool):
    tool_id = "stage2.location_generator.v1"
    generator_type = "location_generator"
    output_schema_alias = "location_profile"
    capabilities = ("generate_locations",)

    async def run(
        self,
        request: Stage2ToolRequest,
        context: Stage2ToolContext,
    ) -> Stage2ToolResult:
        # 0. Get allocator
        allocator = context.identity_allocator
        if allocator is None:
            raise RuntimeError("IdentityAllocator not provided in context")

        # 1. Resolve schema model
        entry = context.schema_registry.get(
            self.output_schema_alias, source_id=context.source_id,
        )
        ModelClass: type[BaseModel] = entry.model_type

        # 2. Introspect schema (with template metadata for required/optional distinction)
        schema_desc = introspect_schema(ModelClass, schema_entry=entry)

        # 3. Prepare world context
        world_ctx = build_world_context(request)
        char_summary = build_character_summary(request.resolved_character_seeds)

        # 4. Batch seeds
        batches = batch_seeds(request.resolved_location_seeds, request.batch_size)
        total_batches = len(batches)

        all_items: list[Any] = []
        all_refs: list[str] = []
        all_warnings: list[str] = []
        all_review_scores: list[float] = []
        retry_count = 0
        failed_batches = 0

        # 5. Process each batch
        for batch_index, batch in enumerate(batches, 1):
            try:
                items, refs, warnings, review_score, retried = await self._process_batch(
                    batch=batch,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    world_ctx=world_ctx,
                    schema_desc=schema_desc,
                    char_summary=char_summary,
                    ModelClass=ModelClass,
                    allocator=allocator,
                )
                all_items.extend(items)
                all_refs.extend(refs)
                all_warnings.extend(warnings)
                if review_score is not None:
                    all_review_scores.append(review_score)
                if retried:
                    retry_count += 1

            except Exception as exc:
                failed_batches += 1
                all_warnings.append(f"batch {batch_index}/{total_batches} failed: {exc}")

        # 6. Fail if nothing generated
        if not all_items:
            raise RuntimeError(
                f"LocationGenerationTool: all {total_batches} batches failed, "
                "no locations generated"
            )

        # 7. Build quality summary
        quality_summary = self._build_quality_summary(
            total_seeds=len(request.resolved_location_seeds),
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
                "total_seeds": len(request.resolved_location_seeds),
                "total_generated": len(all_items),
                "quality_summary": quality_summary,
                "seed_to_entity_mapping": allocator.seed_mapping,
            },
        )

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    async def _process_batch(
        self,
        batch: list,
        batch_index: int,
        total_batches: int,
        world_ctx: dict[str, str],
        schema_desc: str,
        char_summary: str,
        ModelClass: type[BaseModel],
        allocator: IdentityAllocator,
    ) -> tuple[list[Any], list[str], list[str], float | None, bool]:
        """Generate, review, and validate a single batch. Returns (items, refs, warnings, score, retried)."""
        warnings: list[str] = []
        retried = False

        # --- Phase 1: Generate ---
        gen_prompt = build_generation_prompt(_GENERATION_USER_TEMPLATE, {
            **world_ctx,
            "schema_description": schema_desc,
            "character_seed_summary": char_summary,
            "seed_list": build_seed_list(batch),
            "batch_index": str(batch_index),
            "total_batches": str(total_batches),
        })

        raw_gen = await chat_json(gen_prompt, system=_GENERATION_SYSTEM)
        gen_data = _safe_json_loads(raw_gen)
        if not isinstance(gen_data, list):
            gen_data = [gen_data]

        # --- Phase 2: Quality review ---
        review_score: float | None = None
        try:
            review_prompt = build_generation_prompt(_REVIEW_USER_TEMPLATE, {
                **world_ctx,
                "schema_description": schema_desc,
                "generated_locations_json": json.dumps(gen_data, ensure_ascii=False, indent=2),
            })
            raw_review = await chat_json(review_prompt, system=_REVIEW_SYSTEM)
            review_result = _safe_json_loads(raw_review)

            if isinstance(review_result, dict) and "review" in review_result:
                review_info = review_result["review"]
                review_score = review_info.get("overall_score")
                issues = review_info.get("issues", [])

                if issues:
                    warnings.append(
                        f"batch {batch_index} review (score={review_score}): "
                        + "; ".join(str(i) for i in issues)
                    )

                # Use corrected locations if available
                corrected = review_result.get("corrected_locations")
                if isinstance(corrected, list) and corrected:
                    gen_data = corrected
                else:
                    warnings.append(
                        f"batch {batch_index}: review returned no corrected_locations, "
                        "using generation output"
                    )

                # Retry if quality is below threshold
                if review_score is not None and review_score < _QUALITY_THRESHOLD:
                    retried = True
                    retry_items, retry_refs, retry_warnings = await self._retry_batch(
                        batch=batch,
                        batch_index=batch_index,
                        total_batches=total_batches,
                        world_ctx=world_ctx,
                        schema_desc=schema_desc,
                        char_summary=char_summary,
                        ModelClass=ModelClass,
                        review_issues=issues,
                    )
                    if retry_items:
                        warnings.extend(retry_warnings)
                        return retry_items, retry_refs, warnings, review_score, retried
                    else:
                        warnings.append(
                            f"batch {batch_index}: retry also failed, using original output"
                        )

            else:
                warnings.append(
                    f"batch {batch_index}: review returned unexpected format, "
                    "using generation output"
                )

        except Exception as review_exc:
            warnings.append(
                f"batch {batch_index}: review step failed ({review_exc}), "
                "using unreviewed output"
            )

        # --- Phase 3: Validate ---
        validated, val_warnings = parse_and_validate(gen_data, ModelClass, batch)
        warnings.extend(val_warnings)

        # --- Phase 4: Allocate entity IDs ---
        refs = assign_entity_ids(validated, batch, allocator, "loc")

        return validated, refs, warnings, review_score, retried

    # ------------------------------------------------------------------
    # Retry on low quality
    # ------------------------------------------------------------------

    async def _retry_batch(
        self,
        batch: list,
        batch_index: int,
        total_batches: int,
        world_ctx: dict[str, str],
        schema_desc: str,
        char_summary: str,
        ModelClass: type[BaseModel],
        review_issues: list[Any],
    ) -> tuple[list[Any], list[str], list[str]]:
        """Retry generation with review feedback incorporated into the prompt."""
        warnings: list[str] = []
        issues_str = "\n".join(f"  - {i}" for i in review_issues) if review_issues else "  无具体问题"

        retry_prompt = build_generation_prompt(_RETRY_USER_TEMPLATE, {
            **world_ctx,
            "schema_description": schema_desc,
            "character_seed_summary": char_summary,
            "seed_list": build_seed_list(batch),
            "review_issues": issues_str,
        })

        try:
            raw_retry = await chat_json(retry_prompt, system=_RETRY_SYSTEM)
            retry_data = _safe_json_loads(raw_retry)
            if not isinstance(retry_data, list):
                retry_data = [retry_data]

            validated, val_warnings = parse_and_validate(retry_data, ModelClass, batch)
            warnings.extend(val_warnings)
            warnings.append(f"batch {batch_index}: retried due to low quality score")

            refs: list[str] = []
            for item in validated:
                identity = getattr(item, "identity", None)
                if identity and hasattr(identity, "id"):
                    refs.append(identity.id)

            return validated, refs, warnings

        except Exception as exc:
            warnings.append(f"batch {batch_index}: retry failed ({exc})")
            return [], [], warnings

    # ------------------------------------------------------------------
    # Quality summary
    # ------------------------------------------------------------------

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
        # Extract key issues from warnings (review-related)
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
