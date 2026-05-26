## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 上一轮审核/校验发现的问题

{{review_issues}}

## 已生成的地点

{{location_summary}}

## 路径 Schema 结构

{{schema_description}}

## 路径数量要求

{{path_count_hint}}

## 输出要求

输出一个 JSON 数组，每个元素对应一条路径。
请特别注意审核反馈中提到的问题，针对性改进。
确保：
- from_id 和 to_id 使用上方地点列表中的有效 ID
- 无自环（from_id != to_id）
- 无序对唯一（A→B 和 B→A 只保留一条）
- 覆盖所有地点（每个地点至少有一条路径连接）
- 图连通（任意两个地点之间可达）
