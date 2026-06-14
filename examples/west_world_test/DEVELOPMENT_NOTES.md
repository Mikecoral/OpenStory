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
- `timeline.jsonl`：每 tick 的完整快照（初始 + 动作结果）。
- `agent_states.jsonl`：逐 agent 逐 tick 的状态。
- `scene_snapshots_public.jsonl` / `scene_snapshots_internal.jsonl`：场景状态（分别对外与内部诊断）。
- `model_traces.jsonl`：完整 prompt/response/parse。
- `raw/llm_requests.jsonl` / `raw/llm_attempts.jsonl`：LLM 调用记录。
- `summary.json`：汇总指标。

可用 `log_cli` 查询。

### Recorder 两种模式

- **Structured**（`WW_RECORDER_MODE=structured`，**当前默认**）：`StructuredLocationRecorder`。LLM 把自由文本动作解析成对已注册对象的 free-form patch（`patches:[{object_id, <任意字段>}]`），走确定性 reducer，保留 before/after ledger。
- **Legacy**（`WW_RECORDER_MODE=legacy`）：原始 Text Recorder，baseline 对照用。

两者并存，支持对比测试。

### 测试覆盖

所有关键模块已有单元测试（98+ passed）：
- `test_location_recorder.py` / `test_structured_location_recorder.py`
- `test_reflect_plugin.py` / `test_worldmap.py`
- `test_sim_plugins.py` / `test_sim_skeleton.py`

## 待办

### Structured Recorder 未解架构缺口

根因：对象所有权锚定在 location 而非 agent/world。已从固定 op-code 白名单升级为 free-form patch + reducer，但仍有结构性限制（需单独 brainstorm）：

- 无法创造/销毁对象（涌现实体，如新倒的酒、地上的血）
- 跨地点对象转移结构不可能（每个 LocationRecorder 独占 object_facts，无跨 recorder 通路）
- `held_by` 不能在 agent 间传递（限死当前 actor 或空）
- 丢失 ambient / 非对象环境态（`dynamic_objects` 现纯由对象派生）

### 正式仿真与 MVE 实验的融合方案

当前 `core/` 是独立的 MVP 对照实验（无需 Ray/Redis）。若要在完整仿真里验证结构化 Recorder 的收益，需设计并执行：

- 同等规模 baseline vs structured 对比跑。
- 用 `summary.json` + `log_cli` 系统对比（准确率、漂移、延迟）。

### 自由文本动作解析的完整覆盖

当前 A/B 测试（`eval/run_free_text_reducer_ab.py`）仍基于固定脚本数据。正式仿真的真实 LLM 动作更自由，解析链路需继续演进：

- 扩大动作类型白名单。
- 改进多步动作拆解与失败回退。
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
