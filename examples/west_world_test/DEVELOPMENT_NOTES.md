# West World Test - 开发笔记

> 最后更新：2026-06-14
>
> 正式仿真（M0–M3）的状态卡片。只保留「已完成」和「待办」两部分。

## 已完成

### 正式仿真的完整 5 段生命周期（Agent）

- `perceive`：`WestWorldPerceivePlugin` 抓取当前位置可见信息到 `percept`。
- `plan`：`WestWorldPlanPlugin` 基于 percept 用 LLM 做决策，写 `plan_decision` 和 `next_read`。
- `invoke`：`WestWorldInvokePlugin` 执行动作（move/do/stay），传给 Recorder。
- `state`：`BasicStatePlugin` 更新 agent 本地状态。
- `reflect`：`WestWorldReflectPlugin` 每 tick 累积短期记忆，每 `WW_REFLECT_INTERVAL`（默认 6）tick 用 LLM 总结进长期记忆并清空。

都已在 `registry_sim.py` 和 `configs_sim/agents_config.yaml` 注册且写入 `component_order`。

### 地图与资源管理

- `worldmap/loader.py`：`get_world_map(path)` 带 `@lru_cache`，确保地图单例加载；`default_map_path()` 提供相对安全的路径解析。
- 所有插件使用 `get_world_map()` 替代各自 load，避免重复加载。

### 结构化日志与快照系统

每次正式仿真在 `output/sim_runs/<run_id>/` 下生成：

- `manifest.json` / `provenance.json`：元数据与运行环境。
- `timeline.jsonl`：每 tick 的可安全查询聚合快照（初始 + 动作结果）。
- `agent_states.jsonl`：逐 agent 逐 tick 的可安全查询状态；私有反馈、消息、记忆与完整 plan trace 写入 `internal/agent_states.jsonl`。
- `scene_snapshots_public.jsonl` / `scene_snapshots_internal.jsonl`：场景状态（分别对外与内部诊断）。
- `model_traces.jsonl` / `raw/llm_requests.jsonl`：可安全查询的调用摘要，不含 prompt、模型原始输出和隐藏场景信息。
- `internal/model_traces.jsonl`：内部诊断用完整 prompt/response/parse；不可对外暴露。
- `raw/llm_attempts.jsonl`：ModelRouter 调用尝试记录。
- `summary.json`：汇总所有 agent 与 Recorder 调用的 token、延迟、失败和重试指标。

可用 `log_cli` 查询。

### Recorder 两种模式

- **Structured**（`WW_RECORDER_MODE=structured`，**当前默认**）：`StructuredLocationRecorder`。LLM 把自由文本动作解析成对已注册对象的 free-form patch（`patches:[{object_id, <任意字段>}]`），走确定性 reducer；世界级 registry ledger 保留对象级 before/after，location fact ledger 只引用本次 registry events，避免重复嵌套完整世界快照。
- **Legacy**（`WW_RECORDER_MODE=legacy`）：原始 Text Recorder，baseline 对照用。

两者并存，支持对比测试。

### 测试覆盖

所有关键模块已有单元测试（当前 `127 passed, 1 skipped`）：
- `test_location_recorder.py` / `test_structured_location_recorder.py`
- `test_reflect_plugin.py` / `test_worldmap.py`
- `test_sim_plugins.py` / `test_sim_skeleton.py`

## 已完成（最近）

### Tick-Atomic Recorder 并发重构

将 Recorder 并发模型从"即时处理"改为"冻结-收集-批处理"，消除同 tick 内的隐式顺序。设计见 `docs/superpowers/specs/2026-06-14-west-world-tick-atomic-recorder-design.md`。

- ✅ `submit_action()` 改为只入队，立即返回 `status="queued"` 占位，不触发 LLM。
- ✅ `tick_update()` 统一处理本 tick 所有意图：drain 队列 → 一次 batch LLM 调用 → 原子 apply patches → 写 `pending_feedback`。
- ✅ 同一地点 N 个 agent 的动作一次 LLM 调用裁决（`_BATCH_PROPOSAL_PROMPT` + `actions[]` 输出），无顺序依赖。
- ✅ `do` 类型全局 event_summary 移动关键词规范化（同单 agent 路径一致）。
- ✅ `read_feedback(agent_id)` 新方法：返回并清除上一 tick 动作的 per-agent feedback。
- ✅ `WestWorldPerceivePlugin`：perceive 开头调 `read_feedback`，替代 invoke 写 state feedback。
- ✅ `WestWorldInvokePlugin`：`do` 分支去掉读取 result 并写 feedback 的逻辑。
- ✅ `snapshot()`/`restore()` 新增 `intent_queue` 和 `pending_feedback` 字段。
- ✅ 测试：136 passed（含 8 个新增用例：tick 冻结验证、双 agent 争抢、batch 失败、单条非法 patch 隔离等）。
- ✅ Qwen3.5-flash non-thinking 修复：`/no_think` 软开关仅 Qwen3 支持，Qwen3.5 需用 `extra_body={"enable_thinking": False}`；修复后测试耗时从 10 分钟降至 44 秒。

### Structured Recorder 对象模型重构

通过 `recorder/world_object_registry.py` 中的 `WorldObjectRegistry` 把对象所有权从 location-anchored 升级为世界级真值源，`StructuredLocationRecorder` 退化为 location 视图。设计见 `docs/superpowers/specs/2026-06-14-west-world-world-object-model-design.md`，实现见 `docs/superpowers/plans/2026-06-14-west-world-world-object-model.md`。

已解决的架构缺口：

- ✅ 自由创造/销毁对象：`new_objects` / `destroy` 字段，无模板/白名单/硬上限，reducer 分配全局 `obj_*` id 并记录 provenance。
- ✅ 跨地点对象转移：持有物随持有者移动，`invoke.apply_move` 成功后调 `registry.relocate_holdings(...)`。
- ✅ `held_by` 可在在场 agent 间传递：校验 `held_by ∈ {"", 行动者} ∪ 本地点在场 agent`。
- ✅ ambient 环境态：新增 `ambient` chunk，可记录光线/气味/声音/气氛等整体环境文本。
- ✅ 世界级审计：每 tick 落盘 `world_objects_snapshots.jsonl`，含完整对象状态与 append-only ledger。

### 正确性与可观测性修复

- ✅ location 视图实时刷新：对象被转移后，旧地点与新地点读取时都会从 registry 重绘 `dynamic_objects`，不再返回缓存旧状态。
- ✅ 消息进入决策链：agent 收到的消息在下一次 perceive 中消费一次，并进入 plan prompt。
- ✅ 广播范围生效：只有 `broadcast_level=location` 的事件会进入地点公共 `recent_events`。
- ✅ 快照恢复接口：registry、structured recorder 和 scene plugin 支持显式恢复快照。
- ✅ 单 pod 安全约束：当前 process-local 世界真值仅允许单 pod；初始化或动态加人将产生第二 pod 时直接报错，避免静默分裂世界状态。
- ✅ 日志统计与脱敏：Recorder 调用计入 token、延迟、失败与重试汇总；失败尝试与最终失败业务请求分开计数；包含隐藏场景的完整请求仅写入 `internal/`。
- ✅ Recorder 不再阻塞 pod：同步 Recorder/模型请求通过工作线程执行，地点级锁保证同一地点的写入、读取、进出场与快照一致。
- ✅ `do` 不再静默丢失：解析失败或非法提案写入 `fact_ledger` 的 `unresolved` 记录，并按 `WW_ACTION_RETRY_LIMIT`（默认 3）有限重试；失败原因返回给行动者。
- ✅ 角色对话真实投递：plan 可输出 `recipient_ids`；Invoke 校验接收者在同一地点后，通过 Kernel Messager 投递并在下一 tick 进入接收者感知。
- ✅ `do` / `move` 语义隔离：plan 与 Recorder prompt 明确禁止 `do` 跨地点移动；Recorder 对声称离场/到达的 `do` 公共事件进行确定性规范化；真实 `move` 由系统向起点与终点写入权威事件。
- ✅ 正式仿真反馈修复：过滤 Kernel Messager 回送给发送者的自消息；非法 `broadcast_level` 自动规范化；Recorder 默认使用 `/no_think`，与 agent Plan Router 保持一致。
- ✅ 正式仿真启动清理：移除西部世界未使用且不满足当前抽象接口的红楼梦 Action Plugin 注册；移动与通信继续由 Invoke / Kernel Messager 负责。

## 待办

### 暂缓：正式仿真 legacy / structured 同协议对比

只有用户明确要求时才设计或执行；平时不主动询问、不作为默认下一步。

### 多 pod 共享世界真值

当前通过 fail-fast 保证单 pod 下的正确性。若后续需要超过单 pod 容量，应把 `WorldObjectRegistry` 和 scene 状态迁移到共享服务，而不是移除安全检查。

### 框架级 rollback 集成

当前已提供 registry / recorder / scene 的显式 restore 接口，但尚未接入 AgentKernel 的统一持久化与 rollback 生命周期。

### 自由文本动作解析的完整覆盖

当前 A/B 测试（`eval/run_free_text_reducer_ab.py`）仍基于固定脚本数据。正式仿真的真实 LLM 动作更自由，解析链路需继续演进：

- 扩大动作类型白名单。
- 改进多步动作拆解；当前失败动作会持久化并有限重试，但尚未提供人工对账/重新入队工具。
- 定期与真实数据对比评估。

---

## 快速参考

### 运行正式仿真

```bash
# Baseline（legacy Recorder）
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
WW_MAX_TICKS=10 python -m examples.west_world_test.run_simulation

# Structured Recorder
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
WW_RECORDER_MODE=structured WW_MAX_TICKS=10 \
python -m examples.west_world_test.run_simulation
```

依赖：Redis 在线 + `models_config.yaml` 可用。

### 运行测试

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
pytest examples/west_world_test/tests -q
```

### 查询日志

```bash
python -m examples.west_world_test.log_cli summary <run_id>
python -m examples.west_world_test.log_cli tick <run_id> <tick_num>
python -m examples.west_world_test.log_cli agent <run_id> <agent_id>
```

### 关键源码位置

| 模块 | 路径 |
|---|---|
| Agent 生命周期 | `plugins/agent/{perceive,plan,invoke,reflect}/` |
| Recorder（两种） | `recorder/{location_recorder.py,structured_location_recorder.py}` |
| 环境场景 | `plugins/environment/scene/LocationRecorderPlugin.py` |
| 地图加载器 | `worldmap/loader.py`（真值数据在 `data/map/locations.yaml`） |
| 注册表与配置 | `registry_sim.py` / `configs_sim/` |
