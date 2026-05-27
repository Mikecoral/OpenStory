## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 上一轮审核发现的问题

{{review_issues}}

## 角色 Schema 结构

{{schema_description}}

## 核心地点参考（用于为角色分配 state.location）
{{location_seed_summary}}

## 待重新生成的角色种子

{{seed_list}}

## 输出要求

输出一个 JSON 数组，每个元素对应一个角色种子。
1. `identity.id` 必须严格使用预分配 id。
2. **`state.position` 必须严格填入空对象 {}！**
3. **`state.location` 必须绑定具体地点，格式必须为 {"location_id": "对应的地点ID"}！**
4. **所有需要嵌套对象的字段（如 knowledge 等），必须输出为合法的 JSON 对象（字典），绝不能直接输出纯文本字符串！**

请特别注意审核反馈中提到的问题，针对性改进。