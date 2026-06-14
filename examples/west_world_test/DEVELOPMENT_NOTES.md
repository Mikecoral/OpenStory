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

## 已完成（最近）

### Structured Recorder 对象模型重构

通过 `recorder/world_object_registry.py` 中的 `WorldObjectRegistry` 把对象所有权从 location-anchored 升级为世界级真值源，`StructuredLocationRecorder` 退化为 location 视图。设计见 `docs/superpowers/specs/2026-06-14-west-world-world-object-model-design.md`，实现见 `docs/superpowers/plans/2026-06-14-west-world-world-object-model.md`。

已解决的架构缺口：

- ✅ 自由创造/销毁对象：`new_objects` / `destroy` 字段，无模板/白名单/硬上限，reducer 分配全局 `obj_*` id 并记录 provenance。
- ✅ 跨地点对象转移：持有物随持有者移动，`invoke.apply_move` 成功后调 `registry.relocate_holdings(...)`。
- ✅ `held_by` 可在在场 agent 间传递：校验 `held_by ∈ {"", 行动者} ∪ 本地点在场 agent`。
- ✅ ambient 环境态：新增 `ambient` chunk，可记录光线/气味/声音/气氛等整体环境文本。
- ✅ 世界级审计：每 tick 落盘 `world_objects_snapshots.jsonl`，含完整对象状态与 append-only ledger。

## 待办

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
