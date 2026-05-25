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
如无问题，issues 为空数组，corrections 为空数组，corrected_locations 原样输出。