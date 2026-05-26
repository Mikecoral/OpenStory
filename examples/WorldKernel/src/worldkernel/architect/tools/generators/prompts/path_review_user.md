## 世界背景

- 世界名称：{{world_name}}
- 来源与主题：{{world_origin_summary}}
- 主要类型：{{primary}}
- 世界约束：
{{world_constraints}}

## 已生成的地点

{{location_summary}}

## 路径 Schema 要求

{{schema_description}}

## 待审核的路径数据

```json
{{generated_paths_json}}
```

## 审核维度（每个维度 1-5 分）

1. **连通性**：路径网络是否覆盖所有地点？是否存在孤立地点？
2. **空间合理性**：路径距离/时间是否符合两端地点的空间关系？是否存在明显不合理的超长/超短路径？
3. **条件一致性**：访问条件（access_level、danger_level）是否与两端地点的性质匹配？
4. **类型多样性**：路径类型是否多样（走廊、通道、密道等）？是否千篇一律？
5. **无序对唯一性**：是否存在 A→B 和 B→A 的重复边？
6. **无自环**：是否存在 from_id == to_id 的自环？
7. **端点有效性**：from_id 和 to_id 是否都是有效的地点 ID？

## 输出格式

```json
{
  "review": {
    "scores": {
      "connectivity": 0,
      "spatial_reasonability": 0,
      "condition_consistency": 0,
      "type_diversity": 0,
      "edge_uniqueness": 0,
      "no_self_loops": 0,
      "endpoint_validity": 0
    },
    "overall_score": 0.0,
    "issues": ["具体问题描述1", "具体问题描述2"],
    "corrections": [
      {"index": 0, "field": "endpoints.from_id", "reason": "修正原因", "suggested": "修正后的内容"}
    ]
  },
  "corrected_paths": [...]
}
```

如发现任何问题，在 issues 中列出，在 corrections 中说明具体修正，corrected_paths 中输出修正后的完整 JSON 数组。
如无问题，issues 为空数组，corrections 为空数组，corrected_paths 原样输出。
