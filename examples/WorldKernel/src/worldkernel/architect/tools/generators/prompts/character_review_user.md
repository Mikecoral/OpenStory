## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 角色 Schema 要求

{{schema_description}}

## 待审核的角色数据

{{generated_characters_json}}

## 审核维度（每个维度 1-5 分）

1. **性格饱满度**：人物的 traits, values 和 speech_style 是否符合设定？是否过于单薄？
2. **世界一致性**：角色的背景、门第、特殊能力是否与世界约束保持一致？
3. **原型契合度**：角色是否准确体现了其 role/archetype 的特征？
4. **区分度**：同类角色之间是否有足够差异化？
5. **层级合理性**：core/major/minor 的重要性差异是否在动机复杂度和人设深度上体现出来？
6. **地点绑定合规性**：`state.position` 是否严格留空为 {}？`state.location` 是否正确绑定了地点，且格式严格为 {"location_id": "具体的地点ID"}？
7. **对象格式合规性**：诸如 knowledge 等复合对象字段，是否正确使用了 JSON 字典（如 {"description": "..."}），而不是纯文本字符串？

## 输出格式

请严格输出以下 JSON 格式：

{
  "review": {
    "scores": {
      "personality_richness": 0,
      "world_consistency": 0,
      "archetype_fit": 0,
      "differentiation": 0,
      "importance_tiering": 0,
      "location_binding_compliance": 0,
      "object_format_compliance": 0
    },
    "overall_score": 0.0,
    "issues": ["具体问题描述1", "具体问题描述2"],
    "corrections": [
      {"index": 0, "field": "state.location", "reason": "修正原因", "suggested": {"location_id": "e:xxx"}}
    ]
  },
  "corrected_characters": []
}

如发现任何问题，在 issues 中列出，在 corrections 中说明具体修正，corrected_characters 中输出修正后的完整 JSON 数组。