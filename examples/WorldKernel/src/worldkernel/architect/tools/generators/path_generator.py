"""PathGenerationTool — generates path edges between locations via LLM with quality review and graph validation."""

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
    """Try to fix an invalid endpoint ID.

    Strategy 1: zero-pad — e:slug:loc:1 → e:slug:loc:001
    Strategy 2: name match — if LLM used location name instead of ID
    """
    import re
    # Strategy 1: zero-pad
    m = re.match(r"(e:[^:]+:\w+:)(\d+)$", val)
    if m:
        prefix, num = m.group(1), m.group(2)
        candidate = f"{prefix}{int(num):03d}"
        if candidate in valid_ids:
            return candidate
    # Strategy 2: name match
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
    "你是一个世界路径网络生成器。"
    "根据已生成的地点列表和世界背景，生成连接这些地点的路径网络。"
    "每条路径必须严格遵循给定的 schema 结构，包含所有维度。"
    "endpoints.from_id 和 endpoints.to_id 必须使用地点列表中提供的有效 ID。"
    "禁止自环，无序对不可重复。"
    "路径的访问条件应与两端地点的空间关系一致。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_GENERATION_USER_TEMPLATE = _load_prompt("path_generation_user.md")

_REVIEW_SYSTEM = (
    "你是一个世界构建质量评审专家。"
    "你的任务是对生成的路径网络进行深度质量反思，从多个维度评估并打分。"
    "如发现问题，必须在 corrected_paths 中提供修正后的完整数据。"
    "如无问题，corrected_paths 与输入保持一致。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_REVIEW_USER_TEMPLATE = _load_prompt("path_review_user.md")

_RETRY_SYSTEM = (
    "你是一个世界路径网络生成器。"
    "之前生成的路径数据质量不达标，请根据审核反馈重新生成。"
    "endpoints.from_id 和 endpoints.to_id 必须使用地点列表中提供的有效 ID。"
    "只输出合法 JSON，不输出任何解释、标注或额外文字。"
)

_RETRY_USER_TEMPLATE = _load_prompt("path_retry_user.md")


# ---------------------------------------------------------------------------
# Quality threshold
# ---------------------------------------------------------------------------

_QUALITY_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

class PathGenerationTool(BaseStage2Tool):
    tool_id = "stage2.path_generator.v1"
    generator_type = "path_generator"
    output_schema_alias = "path_edge"
    capabilities = ("generate_paths",)

    async def run(
        self,
        request: Stage2ToolRequest,
        context: Stage2ToolContext,
    ) -> Stage2ToolResult:
        # 0. Get registry
        registry = context.identity_registry
        if registry is None:
            raise RuntimeError("IdentityRegistry not provided in context")

        # 1. Get upstream locations
        locations = request.upstream_locations
        if not locations:
            raise RuntimeError("No upstream location artifacts — generate_locations must run first")

        # 2. Build location summary for prompt
        location_summary = self._build_location_summary(locations)
        location_ids = self._extract_location_ids(locations)
        location_id_map = self._build_location_id_map(locations)

        # 3. Resolve schema model
        entry = context.schema_registry.get(
            self.output_schema_alias, source_id=context.source_id,
        )
        ModelClass: type[BaseModel] = entry.model_type

        # 4. Introspect schema
        schema_desc = introspect_schema(ModelClass, schema_entry=entry)

        # 5. Compute path count bounds
        n_locations = len(locations)
        min_paths, max_paths = self._compute_path_bounds(n_locations)
        path_count_hint = f"建议生成 {min_paths}-{max_paths} 条路径"

        # 6. Prepare world context
        world_ctx = build_world_context(request)

        all_warnings: list[str] = []
        retry_count = 0

        # --- Phase 1: Generate ---
        gen_prompt = build_generation_prompt(_GENERATION_USER_TEMPLATE, {
            **world_ctx,
            "location_summary": location_summary,
            "schema_description": schema_desc,
            "path_count_hint": path_count_hint,
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
                "location_summary": location_summary,
                "schema_description": schema_desc,
                "generated_paths_json": json.dumps(gen_data, ensure_ascii=False, indent=2),
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

                corrected = review_result.get("corrected_paths")
                if isinstance(corrected, list) and corrected:
                    gen_data = corrected
                else:
                    all_warnings.append("review returned no corrected_paths, using generation output")

                if review_score is not None and review_score < _QUALITY_THRESHOLD:
                    retry_count += 1
                    retry_data, retry_warnings = await self._retry(
                        gen_data, issues, world_ctx, location_summary,
                        schema_desc, path_count_hint,
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
        validated, fix_warnings = self._fix_endpoint_ids(validated, location_ids, location_id_map)
        all_warnings.extend(fix_warnings)

        # --- Phase 3.7: Dedup ---
        validated, dedup_warnings = self._dedup_paths(validated)
        all_warnings.extend(dedup_warnings)

        # --- Phase 4: Graph validation ---
        graph_issues = self._validate_path_graph(
            validated, location_ids, min_paths, max_paths,
        )
        if graph_issues:
            all_warnings.extend(f"graph: {issue}" for issue in graph_issues)

            # Retry with graph feedback
            retry_count += 1
            retry_data, retry_warnings = await self._retry(
                gen_data, graph_issues, world_ctx, location_summary,
                schema_desc, path_count_hint,
            )
            if retry_data:
                re_validated, re_val_warnings = parse_and_validate(retry_data, ModelClass, [])
                re_validated, re_fix_warnings = self._fix_endpoint_ids(
                    re_validated, location_ids, location_id_map,
                )
                all_warnings.extend(re_fix_warnings)
                re_validated, re_dedup_warnings = self._dedup_paths(re_validated)
                all_warnings.extend(re_dedup_warnings)
                re_graph_issues = self._validate_path_graph(
                    re_validated, location_ids, min_paths, max_paths,
                )
                if not re_graph_issues:
                    validated = re_validated
                    all_warnings.extend(re_val_warnings)
                    all_warnings.append("graph validation passed after retry")
                else:
                    all_warnings.extend(f"graph retry still has: {i}" for i in re_graph_issues)
                    all_warnings.extend(re_val_warnings)
                    all_warnings.append("graph retry failed")
                    raise RuntimeError(
                        f"PathGenerationTool: graph retry still has issues: {re_graph_issues}. "
                        f"Warnings: {'; '.join(all_warnings)}"
                    )
            else:
                all_warnings.append("graph retry failed")
                raise RuntimeError(
                    f"PathGenerationTool: graph retry produced no data. "
                    f"Warnings: {'; '.join(all_warnings)}"
                )

        # --- Phase 5: Allocate IDs ---
        if not validated:
            raise RuntimeError(
                f"PathGenerationTool: produced 0 paths. "
                f"Warnings: {'; '.join(all_warnings)}"
            )
        entity_ids = registry.allocate_for_paths(validated)
        for item, eid in zip(validated, entity_ids):
            identity = getattr(item, "identity", None)
            if identity is not None and hasattr(identity, "id"):
                identity.id = eid

        # --- Phase 6: Build result ---
        quality_summary = {
            "total_locations": n_locations,
            "total_paths": len(validated),
            "path_count_bounds": [min_paths, max_paths],
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
    # Location summary
    # ------------------------------------------------------------------

    @staticmethod
    def _build_location_summary(locations: list[Any]) -> str:
        """Build a readable summary of upstream locations for the prompt.

        ID is placed first and bolded to maximize LLM attention.
        """
        lines: list[str] = []
        for loc in locations:
            identity = getattr(loc, "identity", None)
            if identity is None:
                continue
            lid = getattr(identity, "id", "?")
            name = getattr(identity, "name", "?")
            loc_type = getattr(identity, "type", "?")
            desc = getattr(identity, "description", "")
            desc_short = desc[:80] + "..." if len(desc) > 80 else desc
            lines.append(f"- **`{lid}`** — {name}（类型: {loc_type}）: {desc_short}")
        return "\n".join(lines) if lines else "  无地点信息"

    @staticmethod
    def _build_location_id_map(locations: list[Any]) -> dict[str, str]:
        """Build a mapping from location name to entity ID for auto-correction."""
        id_map: dict[str, str] = {}
        for loc in locations:
            identity = getattr(loc, "identity", None)
            if identity is not None:
                name = getattr(identity, "name", "")
                lid = getattr(identity, "id", "")
                if name and lid:
                    id_map[name] = lid
        return id_map

    @staticmethod
    def _extract_location_ids(locations: list[Any]) -> set[str]:
        """Extract all location entity IDs."""
        ids: set[str] = set()
        for loc in locations:
            identity = getattr(loc, "identity", None)
            if identity is not None and hasattr(identity, "id"):
                ids.add(identity.id)
        return ids

    # ------------------------------------------------------------------
    # Endpoint auto-correction
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_endpoint_ids(
        paths: list[BaseModel],
        location_ids: set[str],
        location_id_map: dict[str, str],
    ) -> tuple[list[BaseModel], list[str]]:
        """Try to fix invalid endpoint IDs. Returns (paths, warnings)."""
        import re
        warnings: list[str] = []
        for path in paths:
            ep = getattr(path, "endpoints", None)
            if ep is None:
                continue
            for attr in ("from_id", "to_id"):
                val = getattr(ep, attr, "")
                if val and val not in location_ids:
                    fixed = _try_fix_id(val, location_ids, location_id_map)
                    if fixed:
                        setattr(ep, attr, fixed)
                        warnings.append(f"auto-corrected {attr}: '{val}' -> '{fixed}'")
        return paths, warnings

    # ------------------------------------------------------------------
    # Dedup
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_paths(paths: list[BaseModel]) -> tuple[list[BaseModel], list[str]]:
        """Remove duplicate undirected edges, keeping first occurrence."""
        seen: set[tuple[str, str]] = set()
        deduped: list[BaseModel] = []
        warnings: list[str] = []
        for i, path in enumerate(paths):
            ep = getattr(path, "endpoints", None)
            if ep is None:
                deduped.append(path)
                continue
            src = getattr(ep, "from_id", "")
            dst = getattr(ep, "to_id", "")
            edge = (min(src, dst), max(src, dst))
            if edge in seen:
                warnings.append(f"dedup: removed duplicate edge {src}<->{dst} at index {i}")
                continue
            seen.add(edge)
            deduped.append(path)
        return deduped, warnings

    # ------------------------------------------------------------------
    # Path count bounds
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_path_bounds(n_locations: int) -> tuple[int, int]:
        """Compute reasonable path count range based on location count.

        min = n-1 (spanning tree, ensures connectivity)
        max = min(n*2, n*(n-1)/2) (sparse graph, never exceeds complete graph)
        """
        if n_locations <= 1:
            return 0, 0
        min_paths = n_locations - 1
        max_paths = min(n_locations * 2, n_locations * (n_locations - 1) // 2)
        return min_paths, max_paths

    # ------------------------------------------------------------------
    # Graph validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_path_graph(
        paths: list[BaseModel],
        location_ids: set[str],
        min_paths: int,
        max_paths: int,
    ) -> list[str]:
        """Validate path network topology. Returns list of issues."""
        from collections import defaultdict
        issues: list[str] = []

        # 0. Count bounds
        n = len(paths)
        n_locs = len(location_ids)
        if n < min_paths:
            issues.append(f"Too few paths: {n} (expected {min_paths}-{max_paths})")
        elif n > max_paths:
            issues.append(f"Too many paths: {n} (expected {min_paths}-{max_paths})")

        edges: set[tuple[str, str]] = set()
        covered: set[str] = set()

        for i, path in enumerate(paths):
            ep = getattr(path, "endpoints", None)
            if ep is None:
                issues.append(f"path[{i}]: missing endpoints")
                continue
            src = getattr(ep, "from_id", "")
            dst = getattr(ep, "to_id", "")

            # 1. Endpoint validity — skip invalid edges entirely
            if src not in location_ids:
                issues.append(f"path[{i}]: from_id '{src}' not in location set")
            if dst not in location_ids:
                issues.append(f"path[{i}]: to_id '{dst}' not in location set")
            if src not in location_ids or dst not in location_ids:
                continue  # don't add invalid edges to graph

            # 2. No self-loops
            if src == dst:
                issues.append(f"path[{i}]: self-loop on '{src}'")
                continue

            # 3. Undirected edge dedup (A-B and B-A are the same edge)
            edge = (min(src, dst), max(src, dst))
            if edge in edges:
                issues.append(f"path[{i}]: duplicate edge {src}<->{dst}")
            edges.add(edge)

            covered.add(src)
            covered.add(dst)

        # 4. Coverage: every location must have at least one path
        uncovered = location_ids - covered
        if uncovered:
            issues.append(f"{len(uncovered)} locations have no paths: {uncovered}")

        # 5. Connectivity: BFS check (only valid edges in adj)
        if edges and n_locs > 1:
            adj: dict[str, set[str]] = defaultdict(set)
            for a, b in edges:
                adj[a].add(b)
                adj[b].add(a)
            visited: set[str] = set()
            queue = [next(iter(location_ids))]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                queue.extend(adj.get(node, set()) - visited)
            if visited != location_ids:
                issues.append(
                    f"Graph not connected: {len(visited)}/{n_locs} reachable"
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
        location_summary: str,
        schema_desc: str,
        path_count_hint: str,
    ) -> tuple[list[Any] | None, list[str]]:
        """Retry generation with review/graph feedback."""
        warnings: list[str] = []
        issues_str = "\n".join(f"  - {i}" for i in issues) if issues else "  无具体问题"

        retry_prompt = build_generation_prompt(_RETRY_USER_TEMPLATE, {
            **world_ctx,
            "location_summary": location_summary,
            "schema_description": schema_desc,
            "review_issues": issues_str,
            "path_count_hint": path_count_hint,
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
