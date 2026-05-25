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
每个种子已有预分配的 id（见种子列表），生成时 identity.id 必须严格使用该预分配 id。
请特别注意审核反馈中提到的问题，针对性改进。
