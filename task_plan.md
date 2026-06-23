# 任务计划：Tick-Atomic Recorder 并发重构

## 目标
将 `StructuredLocationRecorder` 的并发模型从"即时处理"改为"冻结-收集-批处理"，使同一 tick 内所有 agent 的动作视为同时发生。

## 设计文档
`docs/superpowers/specs/2026-06-14-west-world-tick-atomic-recorder-design.md`

---

## 阶段

### 阶段 1：`StructuredLocationRecorder` 核心重构
**状态：pending**

- [ ] `submit_action()` 改为只入队，返回占位 judgement（`status="queued"`）
- [ ] 新增 `_intent_queue: List[Dict]` 和 `_pending_feedback: Dict[str, Dict]`
- [ ] 新增 `_batch_resolve(intents)` 方法：构造 batch prompt → `_chat_json` → 解析 `actions[]` → 验证每条 patches
- [ ] `tick_update()` 改为：drain queue → 调 `_batch_resolve` → 原子 apply → 写 `_pending_feedback`
- [ ] 新增 `read_feedback(agent_id)` 方法：返回并清除对应条目
- [ ] `snapshot()` / `restore()` 新增 `intent_queue` 和 `pending_feedback` 字段

### 阶段 2：`LocationRecorderPlugin` 适配
**状态：pending**

- [ ] `submit_action()` 去掉 `asyncio.to_thread`，直接同步入队
- [ ] 新增 async `read_feedback(agent_id)` 方法，透传给 recorder

### 阶段 3：Agent 插件适配
**状态：pending**

- [ ] `WestWorldPerceivePlugin`：perceive 开头调 `read_feedback`，写入 state `feedback`
- [ ] `WestWorldInvokePlugin`：`do` 分支去掉读取 result 并写 feedback 的逻辑

### 阶段 4：测试更新与新增
**状态：pending**

- [ ] 更新 `test_structured_location_recorder.py`：submit_action 返回 queued，需调 tick_update 后再断言
- [ ] 更新 `test_location_recorder_plugin.py`：补充 tick_update + read_feedback 路径
- [ ] 新增：单 agent 入队 → tick_update → read_feedback 完整路径
- [ ] 新增：两 agent 争抢同一对象（mock LLM 返回冲突裁决）
- [ ] 新增：tick 内冻结验证
- [ ] 新增：batch LLM 整体失败 → unresolved
- [ ] 新增：单条 patch 非法 → 只该条 unresolved
- [ ] 新增：snapshot/restore 含新字段
- [ ] 新增：move 不入队验证

### 阶段 5：回归验证
**状态：pending**

- [ ] 全量 `pytest examples/west_world_test/tests -q` 通过
- [ ] DEVELOPMENT_NOTES.md 更新

---

## 决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| Phase 2 触发时机 | 下一 tick 开头 tick_update | Recorder 每 tick 只更新一次，语义最干净 |
| 冲突处理 | LLM 仲裁 | 场景语义丰富，LLM 最适合裁决对象归属 |
| Batch 输出格式 | per-agent 独立块（方案 X） | 与现有单次调用格式兼容，reducer 按数组顺序 apply |
| N=1 退化 | 走同一 batch 路径 | 无特殊分支，代码简洁 |
| move 动作 | 不入队，仍同步 | move 不走 Recorder LLM，无需改变 |

---

## 遇到的错误

| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| — | — | — |
