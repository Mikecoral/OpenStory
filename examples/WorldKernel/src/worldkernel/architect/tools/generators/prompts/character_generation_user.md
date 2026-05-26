## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 规模：{{scope}}
- 标签：{{tags}}
- 仿真起始：{{simulation_start}}
- 世界约束：
{{world_constraints}}

## 地点种子（供参考，用于为角色分配居住地/阵营等）
{{location_seed_summary}}

## 角色 Schema 结构

每个角色对象必须包含以下维度：
{{schema_description}}

## 待生成的角色种子（本批次 {{batch_index}}/{{total_batches}}）

{{seed_list}}

## 输出要求

输出一个 JSON 数组，每个元素对应一个角色种子。
1. **自身 ID 严格绑定：** 必须严格使用上方种子列表中的预分配 id。
2. **位置字段强制留空（空对象代替 Null）：** Schema 中如果存在 `state.position`、`state.location` 等表示位置的字段，**绝对不能填 null 或字符串**，请务必填入一个空对象 `{}`，系统会在后续自动绑定。
3. **复杂嵌套对象必须是字典：** 凡是类型为 `XXXGroup`（如 `KnowledgeGroup`）或明显需要嵌套对象的字段，**绝不能只填一个纯文本字符串**，必须填入一个合理的 JSON 字典。

输出格式示例：
```json
[
  {
    "identity": {
      "id": "e:world_name:char:001",
      "name": "角色名称",
      "role": "archetype_id"
    },
    "personality": {
      "traits": ["..."],
      "values": ["..."]
    },
    "state": {
      "position": {},
      "location": {}
    }
  }
]