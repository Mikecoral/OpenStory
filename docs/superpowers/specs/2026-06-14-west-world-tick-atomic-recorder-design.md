# West World Tick-Atomic Recorder 并发设计

> 创建日期：2026-06-14
> 适用范围：`examples/west_world_test/` 正式仿真（structured recorder 模式）

## 背景与问题

当前 `StructuredLocationRecorder.submit_action()` 在 agent invoke 阶段被调用时，立即触发 LLM、写入 `WorldObjectRegistry`，再返回结果。地点级 `asyncio.Lock` 保证同一地点的写入串行，但这造成：

- 同一 tick 内，Agent B 的 `submit_action` 看到的是 Agent A 已修改过的世界状态
- tick 内出现隐式因果顺序，违反"同一 tick 内所有事情同时发生"的语义

## 设计目标

**tick 是系统最小时间单位**。同一 tick 内所有 agent 的动作视为同时发生：

1. invoke 阶段只收集意图，不触发 LLM、不改状态
2. 所有意图在下一 tick 开头（`tick_update`）统一处理
3. 同一地点的多个意图一次 LLM 调用裁决，消除顺序依赖
4. 不同地点并发处理

## 整体架构：两阶段模型

```
Tick N
├── [环境 execute]  tick_update(N)
│     └── 处理 pending_queue[N-1] 中所有入队的 intents
│           ├── 按 location 分组
│           ├── 各 location 并发发起 batch LLM 调用（基于 pre-tick 快照）
│           ├── 验证 + 原子 apply 所有 patches
│           └── 写入 pending_feedback[agent_id]
│
├── [Agent perceive]  read_feedback(agent_id) 读取上一 tick 动作结果
├── [Agent plan]      LLM 决策
├── [Agent invoke]    submit_action() → 只入队，立即返回占位
├── [Agent state]     更新本地状态
└── [Agent reflect]   记忆整理
```

**关键性质：**
- Recorder 世界状态在 tick N 内完全冻结，只在 `tick_update` 开头原子更新一次
- 不同地点的 batch LLM 调用通过 `asyncio.gather` 并发发出
- 同一地点 N 个 agent 的动作由一次 LLM 调用语义裁决，无隐式顺序
- feedback 对 agent 的可见时机与现在相同（invoke 提交 → 下一 tick perceive 读取）

## 数据结构

### 入队 intent 格式

```python
{
    "agent_id": "dolores",
    "action_text": "拿起桌上的左轮手枪",
    "action_type": "do",
    "tick": 5,
}
```

### Batch LLM Prompt 新增输入

在现有单 agent prompt 基础上，将"角色 / 动作类型 / 动作"改为：

```
角色动作列表（按提交顺序，顺序不代表优先级，由你裁决）：
[
  {"agent_id": "dolores", "action_type": "do", "action_text": "拿起桌上的左轮手枪"},
  {"agent_id": "teddy",   "action_type": "do", "action_text": "也想拿那把枪"}
]
```

可见对象、隐藏秘密、在场角色字段保持不变，均取自 pre-tick 快照。

### Batch LLM 输出格式

```json
{
  "actions": [
    {
      "agent_id": "dolores",
      "permission": true,
      "reason": "",
      "private_feedback": "你拿起了左轮手枪，沉甸甸的。",
      "patches": [{"object_id": "obj_3", "held_by": "dolores", "state": "被持有"}],
      "new_objects": [],
      "destroy": []
    },
    {
      "agent_id": "teddy",
      "permission": false,
      "reason": "枪已被 dolores 取走",
      "private_feedback": "你伸手时枪已不在桌上。",
      "patches": [],
      "new_objects": [],
      "destroy": []
    }
  ],
  "ambient": "空气中弥漫着火药气息。",
  "broadcast_level": "location",
  "event_summary": "dolores 拿走了左轮手枪，teddy 未能如愿。"
}
```

每条 `actions[i]` 的字段含义与现有单次调用返回值完全一致。全局字段 `ambient / broadcast_level / event_summary` 描述本 tick 该地点整体事件。

### `pending_feedback`

```python
# StructuredLocationRecorder 上新增
self._intent_queue: List[Dict[str, Any]] = []
self._pending_feedback: Dict[str, Dict[str, Any]] = {}
# key: agent_id，value: 完整 judgement dict（与现有 submit_action 返回值同格式）
```

## 各模块改动

### `StructuredLocationRecorder`

| 方法 | 改动 |
|---|---|
| `submit_action()` | 只做入队：append 到 `_intent_queue`，返回占位 judgement（`permission=None, status="queued"`） |
| `tick_update()` | drain `_intent_queue` → 调 `_batch_resolve()` → apply → 写 `_pending_feedback` |
| `_batch_resolve()` | 新方法：构造 batch prompt，调 `_chat_json`，解析 `actions[]`，验证每条 patches（复用现有 `_validate_patches` 等） |
| `read_feedback()` | 新方法：返回并清除 `_pending_feedback[agent_id]`，无条目返回 `None` |

### `LocationRecorderPlugin`（scene plugin）

| 方法 | 改动 |
|---|---|
| `submit_action()` | 去掉 `asyncio.to_thread`，直接同步入队（无 LLM），锁只保护 append |
| `execute()` | 保持现有 `asyncio.to_thread(recorder.tick_update, tick)`，内部并发由 recorder 管理 |
| `read_feedback()` | 新 async 方法，透传给 recorder |

### `WestWorldPerceivePlugin`

perceive 开头新增：

```python
feedback = await self._scene_call(controller, location, "read_feedback", agent_id)
if feedback:
    await state_plugin.set_state("feedback", feedback.get("private_feedback", ""))
```

### `WestWorldInvokePlugin`

`do` 分支：去掉读取 `result` 并写 feedback 到 state 的逻辑。`move` 分支不变（不走 Recorder LLM，仍同步执行）。

## 错误处理与边界情况

### Batch LLM 解析失败

- 整个 batch 失败（返回 None 或格式错误）：所有 intent 进 `_unresolved_actions`，按现有重试逻辑处理；`pending_feedback` 写入 `status="unresolved"` 占位。
- 单条 `actions[i]` patch 非法：该条单独进 unresolved，其余正常 apply，不因一条失败回滚全部。

### N=1 退化情况

只有一个 agent 入队时，`_batch_resolve` 仍走 batch 路径（`actions` 数组只有一项），输出格式一致，无特殊分支。

### move 动作不入队

`move` 在 invoke 阶段仍同步执行（`agent_leave/enter`、`record_event`、`relocate_holdings`），不进 `_intent_queue`。只有 `do` 类型入队。

### `_intent_queue` 生命周期

每次 `tick_update` 开头原子 drain（swap 出来处理），处理期间新进来的 append 属于下一 tick，不混入本次处理。

### snapshot / restore

`snapshot()` 新增 `intent_queue` 和 `pending_feedback` 字段；`restore()` 同步恢复，确保 rollback 语义完整。

### 单 pod 约束

不变。`WorldObjectRegistry` 仍是 process-local 单例，batch resolve 在同一进程内串行写入 registry。

## 测试策略

### 现有测试影响

- `test_structured_location_recorder.py`：`submit_action` 语义改变（返回 `status="queued"`），所有直接断言返回值的用例需在调用 `tick_update` 后断言；补充 `read_feedback` 路径。
- `test_location_recorder_plugin.py`：`submit_action` 不再阻塞，需补充 `tick_update` + `read_feedback` 集成路径。
- 其余测试（registry、sim plugins、logging）：不受影响。

### 新增测试用例

| 用例 | 验证点 |
|---|---|
| 单 agent 入队 → tick_update → read_feedback | N=1 退化路径正确，feedback 内容等价于现有单次调用 |
| 两 agent 争抢同一对象 | LLM 裁决后只有一方 `permission=True`，对象 `held_by` 唯一，两方各得正确 feedback |
| tick 内冻结验证 | Agent A 入队后，B 读取 `dynamic_objects` 看不到 A 的变化；tick_update 后双方都能看到 |
| Batch LLM 整体失败 | 所有 intent 进 unresolved，pending_feedback 有占位，下一 tick 重试 |
| 单条 patch 非法 | 只该条进 unresolved，其余正常 apply |
| snapshot/restore | 含 intent_queue 和 pending_feedback 的快照恢复后状态一致 |
| move 不入队 | move 动作同步执行，不出现在 intent_queue |

所有测试使用 mock LLM（`FakeLLM`），不依赖真实模型，保持现有 `pytest` 风格。
