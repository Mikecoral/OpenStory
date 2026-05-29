"""RelationGenerationTool — generates directed relation edges between characters via LLM.

Pipeline: generate → review → validate → fix endpoints → graph validation → (retry) → allocate IDs.

Relation-specific constraints (beyond path tool logic):
- Directed graph: A→B and B→A are independent edges
- Full character coverage: no isolated characters
- Core character density: importance==core characters must appear ≥ 2 times
- Type diversity: ≥ 3 distinct edge types when n_chars ≥ 4
"""

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
    build_generation_prompt,
    build_world_context,
    introspect_schema,
    parse_and_validate,
)
from worldkernel.llm.client import chat_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON parsing helpers (shared pattern with path_generator)
# ---------------------------------------------------------------------------

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


def _try_fix_id(val: str, valid_ids: set[str], id_map: dict[str, str]) -> str | None:
    """Try to fix an invalid character endpoint ID.

    Strategy 1: zero-pad — e:slug:char:1 → e:slug:char:001
    Strategy 2: name match — if LLM used character name instead of ID
    """
    import re
    m = re.match(r"(e:[^:]+:\w+:)(\d+)$", val)
    if m:
        prefix, num = m.group(1), m.group(2)
        candidate = f"{prefix}{int(num):03d}"
        if candidate in valid_ids:
            return candidate
    if val in id_map:
        return id_map[val]
    return None


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


_GENERATION_SYSTEM = (
    "你是一个世界关系网络生成器。"
    "根据已生成的角色列表和世界背景，生成这些角色之间的有向关系网络。"
    "每条关系必须严格遵循给定的 schema 结构，包含所有维度。"
    "edge.from_id 和 edge.to_id 必须使用角色列表中提供的有效 ID，绝不能使用名字。"
    "禁止自环（from_id != to_id）。A→B 与 B→A 是两条独立关系，可同时存在。"
    "每个角色必须至少出现在一条关系的任一端点（不能有孤立角色）。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_GENERATION_USER_TEMPLATE = _load_prompt("relation_generation_user.md")

_REVIEW_SYSTEM = (
    "你是一个世界构建质量评审专家。"
    "你的任务是对生成的角色关系网络进行深度质量反思，从多个维度评估并打分。"
    "如发现问题，必须在 corrected_relations 中提供修正后的完整数据。"
    "如无问题，corrected_relations 与输入保持一致。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_REVIEW_USER_TEMPLATE = _load_prompt("relation_review_user.md")

_RETRY_SYSTEM = (
    "你是一个世界关系网络生成器。"
    "之前生成的关系数据质量不达标，请根据审核反馈重新生成完整的关系列表。"
    "edge.from_id 和 edge.to_id 必须使用角色列表中的有效 ID，不能使用名字。"
    "每个角色必须至少参与一条关系，core 角色至少参与 2 条关系。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_RETRY_USER_TEMPLATE = _load_prompt("relation_retry_user.md")

_QUALITY_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

class RelationGenerationTool(BaseStage2Tool):
    tool_id = "stage2.relation_generator.v1"
    generator_type = "relation_generator"
    output_schema_alias = "relation_edge"
    capabilities = ("generate_relations",)

    async def run(
        self,
        request: Stage2ToolRequest,
        context: Stage2ToolContext,
    ) -> Stage2ToolResult:
        # 0. Get registry
        registry = context.identity_registry
        if registry is None:
            raise RuntimeError("IdentityRegistry not provided in context")

        # 1. Get upstream characters
        characters = request.upstream_characters
        if not characters:
            raise RuntimeError("No upstream character artifacts — generate_characters must run first")

        # 2. Build character summary and auxiliary data
        importance_map = self._build_importance_map(request, registry)
        character_summary = self._build_character_summary(characters, importance_map)
        character_ids = self._extract_character_ids(characters)
        character_id_map = self._build_character_id_map(characters)

        # 3. Resolve schema model
        entry = context.schema_registry.get(
            self.output_schema_alias, source_id=context.source_id,
        )
        ModelClass: type[BaseModel] = entry.model_type

        # 4. Introspect schema
        schema_desc = introspect_schema(ModelClass, schema_entry=entry)

        # 5. Compute relation count bounds
        n_characters = len(characters)
        min_rels, max_rels = self._compute_relation_bounds(n_characters)
        relation_count_hint = f"建议生成 {min_rels}-{max_rels} 条关系"

        # 6. World context
        world_ctx = build_world_context(request)

        all_warnings: list[str] = []
        retry_count = 0
        graph_issues: list[str] = []

        # --- Phase 1: Generate ---
        gen_prompt = build_generation_prompt(_GENERATION_USER_TEMPLATE, {
            **world_ctx,
            "character_summary": character_summary,
            "schema_description": schema_desc,
            "relation_count_hint": relation_count_hint,
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
                "character_summary": character_summary,
                "schema_description": schema_desc,
                "generated_relations_json": json.dumps(gen_data, ensure_ascii=False, indent=2),
                "relation_count_hint": relation_count_hint,
            })
            raw_review = await chat_json(review_prompt, system=_REVIEW_SYSTEM)
            review_result = _safe_json_loads(raw_review)

            if isinstance(review_result, dict) and "review" in review_result:
                review_info = review_result["review"]
                review_score = review_info.get("overall_score")
                issues = review_info.get("issues", [])

                if issues:
                    all_warnings.append(
                        f"review (score={review_score}): "
                        + "; ".join(str(i) for i in issues)
                    )

                corrected = review_result.get("corrected_relations")
                if isinstance(corrected, list) and corrected:
                    gen_data = corrected
                else:
                    all_warnings.append("review returned no corrected_relations, using generation output")

                if review_score is not None and review_score < _QUALITY_THRESHOLD:
                    retry_count += 1
                    retry_data, retry_warnings = await self._retry(
                        gen_data, issues, world_ctx, character_summary,
                        schema_desc, relation_count_hint,
                    )
                    if retry_data:
                        all_warnings.extend(retry_warnings)
                        gen_data = retry_data
                    else:
                        all_warnings.append("retry also failed, using original output")
            else:
                all_warnings.append("review returned unexpected format, using generation output")

        except Exception as review_exc:
            all_warnings.append(f"review step failed ({review_exc}), using unreviewed output")

        # --- Phase 3: Validate ---
        validated, val_warnings = parse_and_validate(gen_data, ModelClass, [])
        all_warnings.extend(val_warnings)

        # --- Phase 3.5: Auto-correct endpoint IDs ---
        validated, fix_warnings = self._fix_endpoint_ids(validated, character_ids, character_id_map)
        all_warnings.extend(fix_warnings)

        # --- Phase 4: Graph validation ---
        graph_issues = self._validate_relation_graph(
            validated, character_ids, importance_map, min_rels, max_rels,
        )
        errors = [i for i in graph_issues if not i.startswith("warn:")]

        if graph_issues:
            all_warnings.extend(f"graph: {issue}" for issue in graph_issues)

        if errors:
            # Hard errors (self-loop / invalid endpoints / isolated characters) → retry
            retry_count += 1
            retry_data, retry_warnings = await self._retry(
                gen_data, graph_issues, world_ctx, character_summary,
                schema_desc, relation_count_hint,
            )
            if retry_data:
                re_validated, re_val_warnings = parse_and_validate(retry_data, ModelClass, [])
                re_validated, re_fix_warnings = self._fix_endpoint_ids(
                    re_validated, character_ids, character_id_map,
                )
                re_graph_issues = self._validate_relation_graph(
                    re_validated, character_ids, importance_map, min_rels, max_rels,
                )
                re_errors = [i for i in re_graph_issues if not i.startswith("warn:")]
                if not re_errors:
                    validated = re_validated
                    all_warnings.extend(re_val_warnings)
                    all_warnings.extend(re_fix_warnings)
                    all_warnings.append("graph validation passed after retry")
                    graph_issues = re_graph_issues
                else:
                    all_warnings.extend(f"graph retry still has: {i}" for i in re_graph_issues)
                    all_warnings.extend(re_val_warnings)
                    all_warnings.append("graph retry failed")
                    raise RuntimeError(
                        f"RelationGenerationTool: graph retry still has issues: {re_graph_issues}. "
                        f"Warnings: {'; '.join(all_warnings)}"
                    )
            else:
                all_warnings.append("graph retry failed")
                raise RuntimeError(
                    f"RelationGenerationTool: graph retry produced no data. "
                    f"Warnings: {'; '.join(all_warnings)}"
                )

        # --- Phase 5: Allocate IDs ---
        if not validated:
            raise RuntimeError(
                f"RelationGenerationTool: produced 0 relations. "
                f"Warnings: {'; '.join(all_warnings)}"
            )
        entity_ids = registry.allocate_for_relations(validated)
        for item, eid in zip(validated, entity_ids):
            edge = getattr(item, "edge", None)
            if edge is not None and hasattr(edge, "id"):
                edge.id = eid

        # --- Phase 6: Build result ---
        quality_summary = {
            "total_characters": n_characters,
            "total_relations": len(validated),
            "relation_count_bounds": [min_rels, max_rels],
            "review_score": review_score,
            "retry_count": retry_count,
            "graph_issues": graph_issues[:5],
        }

        return Stage2ToolResult(
            artifact_type=self.output_schema_alias,
            items=validated,
            produced_refs=entity_ids,
            warnings=all_warnings,
            provenance={
                "tool_id": self.tool_id,
                "quality_summary": quality_summary,
                "dynamic_id_mapping": registry.seed_mapping,
            },
        )

    # ------------------------------------------------------------------
    # Character summary and ID helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_character_summary(
        characters: list[Any],
        importance_map: dict[str, str],
    ) -> str:
        """Build readable character list for prompt. Marks core characters explicitly."""
        lines: list[str] = []
        for char in characters:
            identity = getattr(char, "identity", None)
            if identity is None:
                continue
            cid = getattr(identity, "id", "?")
            name = getattr(identity, "name", "?")
            role = getattr(identity, "role", "?")
            importance = importance_map.get(cid, "")
            importance_tag = f"[{importance}] " if importance else ""
            social = getattr(char, "social_profile", None)
            desc = getattr(social, "reputation", "") if social else ""
            desc_short = desc[:60] + "..." if len(desc) > 60 else desc
            lines.append(f"- **`{cid}`** {importance_tag}— {name}（{role}）: {desc_short}")
        return "\n".join(lines) if lines else "  无角色信息"

    @staticmethod
    def _build_character_id_map(characters: list[Any]) -> dict[str, str]:
        """Build name → entity_id map for auto-correction."""
        id_map: dict[str, str] = {}
        for char in characters:
            identity = getattr(char, "identity", None)
            if identity is not None:
                name = getattr(identity, "name", "")
                cid = getattr(identity, "id", "")
                if name and cid:
                    id_map[name] = cid
        return id_map

    @staticmethod
    def _extract_character_ids(characters: list[Any]) -> set[str]:
        """Extract all character entity IDs."""
        ids: set[str] = set()
        for char in characters:
            identity = getattr(char, "identity", None)
            if identity is not None and hasattr(identity, "id"):
                ids.add(identity.id)
        return ids

    @staticmethod
    def _build_importance_map(
        request: Stage2ToolRequest,
        registry: Any,
    ) -> dict[str, str]:
        """Build entity_id → importance mapping from resolved character seeds."""
        seeds = request.resolved_character_seeds
        if not seeds:
            return {}
        try:
            seed_to_entity = registry.lookup(seeds, "char")
            return {
                seed_to_entity[seed.seed_id]: seed.importance
                for seed in seeds
                if seed.seed_id in seed_to_entity
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Endpoint auto-correction
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_endpoint_ids(
        relations: list[BaseModel],
        character_ids: set[str],
        character_id_map: dict[str, str],
    ) -> tuple[list[BaseModel], list[str]]:
        """Try to fix invalid endpoint IDs in relations."""
        warnings: list[str] = []
        for rel in relations:
            edge = getattr(rel, "edge", None)
            if edge is None:
                continue
            for attr in ("from_id", "to_id"):
                val = getattr(edge, attr, "")
                if val and val not in character_ids:
                    fixed = _try_fix_id(val, character_ids, character_id_map)
                    if fixed:
                        setattr(edge, attr, fixed)
                        warnings.append(f"auto-corrected {attr}: '{val}' -> '{fixed}'")
        return relations, warnings

    # ------------------------------------------------------------------
    # Relation count bounds
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_relation_bounds(n_chars: int) -> tuple[int, int]:
        """Reasonable relation count range for a social network.

        min = n_chars (at least one relation per character on average)
        max = n_chars * 3 (sparse social graph, avoids combinatorial explosion)
        """
        if n_chars <= 1:
            return 0, 0
        return n_chars, n_chars * 3

    # ------------------------------------------------------------------
    # Graph validation — relation-specific constraints
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_relation_graph(
        relations: list[BaseModel],
        character_ids: set[str],
        importance_map: dict[str, str],
        min_rels: int,
        max_rels: int,
    ) -> list[str]:
        """Validate relation network with relation-specific constraints.

        Returns issues. Hard errors have no prefix; soft warnings are prefixed 'warn:'.
        Hard errors trigger retry; warnings are logged but don't block output.
        """
        issues: list[str] = []
        covered: set[str] = set()
        char_degree: dict[str, int] = {cid: 0 for cid in character_ids}
        edge_types: set[str] = set()

        for i, rel in enumerate(relations):
            edge = getattr(rel, "edge", None)
            if edge is None:
                issues.append(f"relation[{i}]: missing edge")
                continue
            src = getattr(edge, "from_id", "")
            dst = getattr(edge, "to_id", "")

            # Hard: endpoint validity
            if src not in character_ids:
                issues.append(f"relation[{i}]: from_id '{src}' not in character set")
            if dst not in character_ids:
                issues.append(f"relation[{i}]: to_id '{dst}' not in character set")
            if src not in character_ids or dst not in character_ids:
                continue

            # Hard: no self-loops
            if src == dst:
                issues.append(f"relation[{i}]: self-loop on '{src}'")
                continue

            # Directed graph — A→B and B→A are distinct (no dedup)
            covered.add(src)
            covered.add(dst)
            char_degree[src] = char_degree.get(src, 0) + 1
            char_degree[dst] = char_degree.get(dst, 0) + 1

            edge_type = getattr(edge, "type", "")
            if edge_type:
                edge_types.add(edge_type)

        # Hard: all characters must appear in at least one relation
        uncovered = character_ids - covered
        if uncovered:
            sample = sorted(uncovered)[:3]
            suffix = "..." if len(uncovered) > 3 else ""
            issues.append(
                f"{len(uncovered)} characters have no relations: "
                + ", ".join(sample) + suffix
            )

        # Soft: relation count range
        n = len(relations)
        if n < min_rels:
            issues.append(f"warn: Too few relations: {n} (expected {min_rels}-{max_rels})")
        elif n > max_rels:
            issues.append(f"warn: Too many relations: {n} (expected {min_rels}-{max_rels})")

        # Soft: type diversity (when enough characters)
        if len(character_ids) >= 4:
            min_types = min(3, len(character_ids) - 1)
            if len(edge_types) < min_types:
                issues.append(
                    f"warn: Low relation type diversity: {len(edge_types)} types "
                    f"(expected >= {min_types}): {edge_types}"
                )

        # Soft: core character density
        for cid, imp in importance_map.items():
            if imp == "core" and cid in character_ids:
                degree = char_degree.get(cid, 0)
                if degree < 2:
                    issues.append(
                        f"warn: Core character '{cid}' appears in only {degree} relation(s) (expected >= 2)"
                    )

        return issues

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def _retry(
        self,
        gen_data: list[Any],
        issues: list[Any],
        world_ctx: dict[str, str],
        character_summary: str,
        schema_desc: str,
        relation_count_hint: str,
    ) -> tuple[list[Any] | None, list[str]]:
        """Retry generation with review/graph feedback."""
        warnings: list[str] = []
        issues_str = "\n".join(f"  - {i}" for i in issues) if issues else "  无具体问题"

        retry_prompt = build_generation_prompt(_RETRY_USER_TEMPLATE, {
            **world_ctx,
            "character_summary": character_summary,
            "schema_description": schema_desc,
            "review_issues": issues_str,
            "relation_count_hint": relation_count_hint,
        })

        try:
            raw_retry = await chat_json(retry_prompt, system=_RETRY_SYSTEM)
            retry_data = _safe_json_loads(raw_retry)
            if not isinstance(retry_data, list):
                retry_data = [retry_data]
            warnings.append("retried due to quality/graph issues")
            return retry_data, warnings
        except Exception as exc:
            warnings.append(f"retry failed ({exc})")
            return None, warnings
