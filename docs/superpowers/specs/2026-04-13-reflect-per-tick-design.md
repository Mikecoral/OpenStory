# 反思模块每tick执行设计方案

## 背景

当前反思模块（ReflectPlugin）每12个tick才执行一次规划，中间无法根据新情况调整计划。如果在这12个tick期间发生重大事件（如角色死亡、重要任务完成），Agent无法及时响应。

## 目标

将反思逻辑改为每tick执行，新增判断是否需要重新规划剩余hourly plans的功能。

## 设计方案

### 架构

```
每tick → 轻量级存活检查 → 反思逻辑（每tick执行）
                              │
                              ├── 1. 总结短期记忆
                              ├── 2. 检查存活状态
                              ├── 3. 检查LongTask完成（现有Prompt）
                              ├── 4. 调整LongTask（现有Prompt）
                              └── 5. 判断是否需要重新规划（新增）
                                        │
                                        └── 如需要 → 重生成剩余hourly plans
```

### 改动点

#### 1. BasicReflectPlugin.py

- 移除 `execute()` 方法中12 tick周期限制 `if (current_tick + 1) % 12 == 0`
- 新增 `_should_replan()` 方法：LLM判断是否需要重新规划
- 新增 `_replan_remaining()` 方法：调用PlanPlugin重新生成剩余hourly plans

#### 2. BasicPlanPlugin.py

- 新增 `replan_remaining_plans()` 方法：只生成当前tick之后剩余的hourly plans

### 新增Prompt设计

```python
prompt = f"""你是一个智能体的计划评估助手。请根据近期记忆，判断是否需要重新规划剩余时间。

当前长期任务：{long_task}

上一tick发生的事件：{last_tick_memory}

当前时间：第{current_day}天 第{current_hour}个时辰（还剩{12-current_hour}个时辰）

剩余未执行计划：{remaining_plans}

判断标准：
1. 上一tick是否发生了重大变化（如重要角色死亡、任务完成、突发事件）
2. 当前任务是否已经失效或偏离
3. 继续执行原计划是否合理

请返回（仅返回结论）：
- 需要重新规划："需要重新规划 | 原因"
- 无需规划："无需规划 | 原因"
"""
```

### 输出捕获

```python
result = await self.model.chat(prompt)
if "需要重新规划" in result:
    await self._replan_remaining(current_tick)
```

### 重新规划范围

只生成当前tick之后剩余的hourly plans，保留已执行的部分。
例如：当前是第5 tick（hour=5），则重新生成6-11这6个hour的计划。

## 文件清单

| 文件 | 改动 |
|------|------|
| `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py` | 移除周期限制，新增判断和重规划方法 |
| `examples/story_of_the_stone/plugins/agent/plan/BasicPlanPlugin.py` | 新增增量规划方法 |
| `examples/story_of_the_stone_en/plugins/agent/reflect/BasicReflectPlugin.py` | 同上（英文版） |
| `examples/story_of_the_stone_en/plugins/agent/plan/BasicPlanPlugin.py` | 同上（英文版） |

## 测试方案

1. 验证每tick都能触发反思逻辑
2. 验证新增Prompt能正常返回判断结果
3. 验证"需要重新规划"能正确捕获
4. 验证剩余hourly plans能正确重新生成