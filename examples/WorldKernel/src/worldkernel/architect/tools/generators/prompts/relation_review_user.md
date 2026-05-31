## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 已生成的角色列表

{{character_summary}}

## 关系 Schema 要求

每条关系只含 `edge` 字段，结构为：`id`（留空）、`from_id`、`to_id`、`type`、`direction`。不包含 `properties` 或其他字段。

## 待审核的关系数据

```json
{{generated_relations_json}}
```

## 建议关系数量

{{relation_count_hint}}

## 审核维度（每个维度 1-5 分）

1. **全角色覆盖**：每个角色是否至少出现在一条关系的任一端点？是否存在孤立角色？（孤立角色严重扣分）
2. **端点有效性**：所有 `edge.from_id` 和 `edge.to_id` 是否都是合法的角色 ID（格式 `e:slug:char:NNN`）？是否有使用名字代替 ID 的情况？
3. **无自环**：是否存在 `edge.from_id == edge.to_id` 的自环？
4. **关系类型质量**：`edge.type` 是否是稳定的身份/社会关系标签（描述两人固有关系），而非事件、动作或场景描述？是否涵盖至少 3 种不同类型，覆盖不同社会维度（权力、情感、对立等）？是否千篇一律？
5. **世界契合度**：关系类型词汇是否真正来自本世界的文化语境（世界名称：{{world_name}}）？是否套用了与世界背景无关的通用标签？不同世界的关系词汇应有本质差异，能让读者一眼感受到"这是哪个世界"。
6. **核心角色密度**：`[core]` 重要度角色是否参与了 ≥ 2 条关系？核心角色是世界社交网络的中心，孤立是不合理的。
7. **双向合理性**：是否存在"同类型关系被拆成两条单向边"的情况（如 A→B 盟友单向 + B→A 盟友单向）？是否存在"互逆角色标签被拆成两条单向边"的情况（应合并为一条 direction=双向 的边）？若有，应合并。从属、对立等语义单向的关系保持单向。
8. **数量合理性**：关系数量是否在建议范围内？

## 输出格式

```json
{
  "review": {
    "scores": {
      "character_coverage": 0,
      "endpoint_validity": 0,
      "no_self_loops": 0,
      "type_quality": 0,
      "world_specificity": 0,
      "core_density": 0,
      "bidirectionality": 0,
      "count_reasonability": 0
    },
    "overall_score": 0.0,
    "issues": ["具体问题描述1", "具体问题描述2"],
    "corrections": [
      {"index": 0, "field": "edge.from_id", "reason": "修正原因", "suggested": "修正后的内容"}
    ]
  },
  "corrected_relations": [...]
}
```

如发现任何问题，在 issues 中列出，在 corrections 中说明具体修正，`corrected_relations` 中输出修正后的完整 JSON 数组。
如无问题，issues 为空数组，corrections 为空数组，`corrected_relations` 原样输出。
