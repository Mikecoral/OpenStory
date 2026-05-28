## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 规模：{{scope}}
- 标签：{{tags}}
- 仿真起始：{{simulation_start}}
- 世界约束：
{{world_constraints}}

## 已生成的角色列表（含 ID）

以下是本世界中已生成的角色，格式为 `- **\`ID\`** [重要度] — 名称（角色类型）: 声誉/描述`。
**edge.from_id 和 edge.to_id 必须使用 ID 栏的值（如 `e:world_name:char:001`），绝不能使用名字。**

{{character_summary}}

## 关系 Schema 结构

每条关系对象必须包含以下维度：
{{schema_description}}

## 关系数量要求

{{relation_count_hint}}

## 输出要求

输出一个 JSON 数组，每个元素对应一条有向关系边。

1. **端点 ID 严格绑定**：`edge.from_id` 和 `edge.to_id` 必须使用上方角色列表中的 ID（如 `e:world_name:char:001`），绝不能使用角色名字或其他格式。
2. **禁止自环**：`edge.from_id != edge.to_id`。
3. **全角色覆盖**：每个角色必须至少出现在一条关系的任一端点，不能有孤立角色。
4. **核心角色密度**：`[core]` 重要度的角色必须参与 ≥ 2 条关系（可以是 from 或 to）。
5. **关系类型多样**：`edge.type` 至少涵盖 3 种不同类型（如盟友、对立、从属、监视、中立、情感纽带等）。
6. **有向关系**：A→B 与 B→A 是两条独立关系，可同时存在，也可只有单向。监视、从属等关系通常单向；盟友、情感纽带等可考虑双向。
7. **世界一致性**：世界特有字段（如 `trust_level`、`spy_risk_level` 等）应与世界背景和角色身份吻合。

输出格式示例：
```json
[
  {
    "edge": {
      "from_id": "e:world_name:char:001",
      "to_id": "e:world_name:char:003",
      "type": "监视",
      "direction": "单向",
      "trust_level": "low",
      "spy_risk_level": "high"
    },
    "properties": {
      "strength": "strong",
      "description": "A 秘密监视 B 的行动",
      "emotional_tone": "suspicious",
      "power_dynamic": "superior-subordinate"
    }
  }
]
```
