## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 已生成的角色列表

{{character_summary}}

## 关系 Schema 要求

{{schema_description}}

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
4. **关系类型多样性**：`edge.type` 是否涵盖至少 3 种不同类型（盟友/对立/从属/监视/情感纽带等）？是否千篇一律？
5. **核心角色密度**：`[core]` 重要度角色是否参与了 ≥ 2 条关系？核心角色是世界社交网络的中心，孤立是不合理的。
6. **强度合理性**：`properties.strength` 是否与角色重要性和关系类型匹配？core 角色之间的关系应有 high/medium 强度。
7. **双向合理性**：监视/从属通常单向；盟友/情感纽带应考虑双向是否合理；单向关系是否有合理解释？
8. **世界一致性**：世界特有字段（`trust_level`、`spy_risk_level`、`blood_status_relevance` 等）是否与世界背景和角色身份一致？
9. **数量合理性**：关系数量是否在建议范围内？

## 输出格式

```json
{
  "review": {
    "scores": {
      "character_coverage": 0,
      "endpoint_validity": 0,
      "no_self_loops": 0,
      "type_diversity": 0,
      "core_density": 0,
      "strength_reasonability": 0,
      "bidirectionality": 0,
      "world_consistency": 0,
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
