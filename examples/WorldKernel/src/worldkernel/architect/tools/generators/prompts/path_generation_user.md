## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 规模：{{scope}}
- 标签：{{tags}}
- 仿真起始：{{simulation_start}}
- 世界约束：
{{world_constraints}}

## 已生成的地点

{{location_summary}}

## 路径 Schema 结构

每条路径对象必须包含以下维度：
{{schema_description}}

## 路径数量要求

{{path_count_hint}}

## 输出要求

输出一个 JSON 数组，每个元素对应一条路径。
路径连接两个地点，endpoints.from_id 和 endpoints.to_id 必须使用上方地点列表中的 ID。
禁止自环（from_id != to_id）。
无序对不可重复（A→B 和 B→A 视为同一条边，只保留一条）。
bidirectional=true 表示双向通行，false 表示单向。

世界特有字段应结合世界背景知识合理填写。
路径的距离、时间、访问条件应与两端地点的空间关系一致。

输出格式示例：
```json
[
  {
    "identity": {
      "name": "路径名称",
      "type": "走廊"
    },
    "endpoints": {
      "from_id": "e:world_slug:loc:001",
      "to_id": "e:world_slug:loc:002",
      "bidirectional": true
    },
    "properties": {
      "distance": "短",
      "travel_time": "1分钟",
      "visibility": "公开"
    },
    "conditions": {
      "access_level": "开放",
      "danger_level": "安全",
      "required_items": "无"
    }
  }
]
```
