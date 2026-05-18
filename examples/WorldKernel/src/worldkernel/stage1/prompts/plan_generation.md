你是一个世界生成计划制定模块。

世界信息：
- 用户目标：{{user_goal}}
- 世界类型：{{world_type_summary}}
- 标签：{{tags}}
- 地点类型：{{location_archetypes}}
- 人物身份类型：{{character_archetypes}}
- 规则类型：{{rule_archetypes}}
- 世界约束：{{world_constraints}}

请完成以下三项任务，输出一个 JSON 对象。

---

**任务一：扩展实体种子列表（entity_plan）**

基于上方每种 archetype 中的候选实例，**按 archetype 分组**将地点和人物扩充为该世界的完整列表。
每种 archetype 下覆盖该类型所有值得生成的典型实例，数量视世界规模而定（单一场所 3-8 个/archetype，城市级 5-15 个/archetype）。

只需要两类：
- locations：按地点类型分组（如 teaching_space、communal_space、dormitory 各自一个列表）
- characters：按人物身份类型分组（如 student、faculty、death_eater_staff 各自一个列表）

每个种子字段：
- seed_id（snake_case，全局唯一）
- name（实体名称）
- importance（core / major / minor）
- source_type（canonical=原著有 / inferred=合理推断 / original=原创补充）
- confidence（0 到 1）
- generation_priority（1 最高优先）
- role_in_world（该实体在世界中的叙事作用，一句话）

---

**任务二：制定生成步骤（steps）**

只需 4 个步骤，按以下固定顺序：

1. generate_locations — 生成所有地点实体
2. generate_paths — 生成地点之间的路径/通道
3. generate_characters — 生成所有角色实体
4. generate_relations — 生成角色之间的关系

每个步骤字段：
- step_id（snake_case）
- generator_type（location_generator / path_generator / character_generator / relation_generator）
- target_entity_type（location / path / character / relation）
- batch_size（建议每次 LLM 调用生成的实体数，通常 3-8）
- priority（1-4，按顺序递增）
- description（人可读的步骤说明）

---

**任务三：实体模版生成指引（ontology_hints）**

根据世界信息，为实体模版生成器提供语义指引：
- character_hints：Character 模版应重点关注的字段或特性
- location_hints：Location 模版应重点关注的要素
- relation_hints：Relation 模版应重点关注的关系类型
- institution_hints：Institution 模版应重点关注的要素
- rule_hints：Rule 模版应重点关注的规则维度

---

**输出格式：**
```json
{
  "entity_plan": {
    "locations": {
      "teaching_space": [
        {
          "seed_id": "dark_arts_classroom",
          "name": "黑魔法防御课教室",
          "importance": "core",
          "source_type": "canonical",
          "confidence": 0.98,
          "generation_priority": 1,
          "role_in_world": "卡罗兄妹实施惩罚的主要场所"
        }
      ],
      "communal_space": [
        {
          "seed_id": "great_hall",
          "name": "大礼堂",
          "importance": "core",
          "source_type": "canonical",
          "confidence": 0.99,
          "generation_priority": 1,
          "role_in_world": "全校集会与用餐的核心场所"
        }
      ]
    },
    "characters": {
      "student": [
        {
          "seed_id": "neville_longbottom",
          "name": "纳威·隆巴顿",
          "importance": "core",
          "source_type": "canonical",
          "confidence": 0.99,
          "generation_priority": 1,
          "role_in_world": "校内公开反抗领袖"
        }
      ],
      "faculty": [
        {
          "seed_id": "minerva_mcgonagall",
          "name": "米勒娃·麦格",
          "importance": "core",
          "source_type": "canonical",
          "confidence": 0.99,
          "generation_priority": 1,
          "role_in_world": "暗中保护学生的资深教授"
        }
      ]
    }
  },
  "steps": [
    {
      "step_id": "generate_locations",
      "generator_type": "location_generator",
      "target_entity_type": "location",
      "batch_size": 8,
      "priority": 1,
      "description": "生成所有地点实体"
    },
    {
      "step_id": "generate_paths",
      "generator_type": "path_generator",
      "target_entity_type": "path",
      "batch_size": 5,
      "priority": 2,
      "description": "生成地点之间的路径和通道"
    },
    {
      "step_id": "generate_characters",
      "generator_type": "character_generator",
      "target_entity_type": "character",
      "batch_size": 6,
      "priority": 3,
      "description": "生成所有角色实体"
    },
    {
      "step_id": "generate_relations",
      "generator_type": "relation_generator",
      "target_entity_type": "relation",
      "batch_size": 8,
      "priority": 4,
      "description": "生成角色之间的关系"
    }
  ],
  "ontology_hints": {
    "character_hints": ["..."],
    "location_hints": ["..."],
    "relation_hints": ["..."],
    "institution_hints": ["..."],
    "rule_hints": ["..."]
  }
}
```
