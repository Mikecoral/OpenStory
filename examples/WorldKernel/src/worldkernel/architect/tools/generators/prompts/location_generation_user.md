## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 规模：{{scope}}
- 标签：{{tags}}
- 仿真起始：{{simulation_start}}
- 世界约束：
{{world_constraints}}

## 角色种子（供参考，无需生成）
{{character_seed_summary}}

## 地点 Schema 结构

每个地点对象必须包含以下维度：
{{schema_description}}

## 待生成的地点种子（本批次 {{batch_index}}/{{total_batches}}）

{{seed_list}}

## 输出要求

**重要：本批次有 {{seed_count}} 个种子，你必须输出恰好 {{seed_count}} 个地点对象的 JSON 数组。不可遗漏任何种子。生成的地点必须是种子列表中的地点**
输出一个 JSON 数组，每个元素对应一个地点种子。
每个种子已有预分配的 id（见种子列表），生成时 identity.id 必须严格使用该预分配 id。
根据种子的 archetype_id、importance、role_in_world 填充各维度字段。
世界特有字段应结合世界背景知识合理填写。
core 级别的种子应有更丰富详细的描述，minor 级别可以相对简洁。

输出格式示例：
```json
[
  {{
    "identity": {{
      "id": "e:world_name:loc:001",
      "name": "地点名称",
      "type": "archetype_id",
      "description": "详细描述...",
      ...
    }},
    "access": {{
      "permissions": "...",
      "access_level": "...",
      ...
    }},
    "state": {{
      "current_state": "...",
      "ownership": "...",
      "capacity": 0,
      ...
    }}
  }}
]
```