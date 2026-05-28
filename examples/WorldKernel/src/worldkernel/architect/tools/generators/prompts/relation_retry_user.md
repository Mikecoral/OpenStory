## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 已生成的角色列表

{{character_summary}}

## 上一轮审核/图验证发现的问题

{{review_issues}}

## 关系 Schema 结构

{{schema_description}}

## 关系数量要求

{{relation_count_hint}}

## 输出要求

输出一个 JSON 数组，包含重新生成的完整关系列表（不是增量补丁）。

**请针对上方问题做出改进，特别注意：**

1. `edge.from_id` 和 `edge.to_id` 必须使用上方角色列表中的 ID（如 `e:world_name:char:001`），**绝不能使用名字**。
2. 禁止自环（`from_id != to_id`）。
3. **每个角色必须至少出现在一条关系的任一端点**，不能有孤立角色。
4. **`[core]` 重要度角色必须参与 ≥ 2 条关系**。
5. **`edge.type` 至少涵盖 3 种不同类型**（盟友/对立/从属/监视/情感纽带等）。
6. 有向关系：A→B 与 B→A 是两条独立的关系，可以同时存在，也可以只有单向。

只输出合法 JSON 数组，不输出任何解释文字。
