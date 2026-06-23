# 研究发现

## 现有架构关键事实

### 并发模型（重构前）
- `LocationRecorderPlugin.submit_action()` 用 `asyncio.to_thread` + `_recorder_lock` 串行化 LLM 调用
- `StructuredLocationRecorder.submit_action()` 立即触发 LLM → apply patches → 返回 judgement
- 同一 tick 内 Agent B 的 submit_action 看到 Agent A 已修改的状态 → 隐式顺序

### Recorder 现有重试机制
- `_unresolved_actions`：解析失败的 intent 存入，在 `tick_update` 开头重试
- 重试上限：`WW_ACTION_RETRY_LIMIT`（默认 3）

### feedback 现有流向
- invoke 调 submit_action → 拿到 result → 写 state `feedback`
- 下一 tick perceive 读 state `feedback`
- 新设计：invoke 只入队 → tick_update 写 `pending_feedback` → 下一 tick perceive 调 `read_feedback`
- 对 agent 可见时机无变化

### move 动作不走 Recorder LLM
- `apply_move` + `agent_leave/enter` + `relocate_holdings` 全部同步执行
- 不需要入队，不受本次重构影响

### 红楼梦对比
- 用 Redis `occupation:{tick}:{agent_id}` key 做优先级抢占
- 不适合西部世界（西部世界需要场景对象语义裁决，不是社交占用）

### WorldObjectRegistry
- process-local 单例，单 pod 约束
- 支持 `transaction()`、`apply_patch()`、`create()`、`destroy()`
- `ledger_size()` / `ledger_since()` 用于追踪本次事务的 registry 变更
