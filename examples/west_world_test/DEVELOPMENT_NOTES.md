# West World Test - 开发笔记

> 最后更新：2026-06-15
>
> 正式仿真（M0–M3+）的状态卡片。只保留「已完成」和「待办」两部分。

## 已完成

### 正式仿真的完整 5 段生命周期（Agent）

- `perceive`：`WestWorldPerceivePlugin` 调 `recorder.perceive(agent_id, agent_context)` 获取个性化感知（5 因子：location/discovered_ids/awakening/traits/last_action+focus）。
- `plan`：`WestWorldPlanPlugin` 基于 percept 用 LLM 做决策，写 `plan_decision` 和 `next_read`。
- `invoke`：`WestWorldInvokePlugin` 执行动作（move/do/stay），传给 Recorder；`relocate_holdings` 已改为路由调用，不在 agent 进程直接访问 registry。
- `state`：`BasicStatePlugin` 更新 agent 本地状态。
- `reflect`：`WestWorldReflectPlugin` 每 tick 累积短期记忆，每 `WW_REFLECT_INTERVAL`（默认 6）tick 用 LLM 总结进长期记忆并清空。

### 地图与资源管理

- `worldmap/loader.py`：`get_world_map(path)` 带 `@lru_cache`，确保地图单例加载；`default_map_path()` 提供相对安全的路径解析。
- **全地图激活**（2026-06-15）：31 个地点全部 `active: true`。Backstage 5 个地点（backstage_control/cold_storage/staff_dormitory/programmer_workspace/surface_maintenance_station）邻接孤岛——B 阶段建"维修传送门"才进入。

### 结构化日志与快照系统

每次正式仿真在 `output/sim_runs/<run_id>/` 下生成：

- `manifest.json` / `provenance.json`：元数据与运行环境。
- `timeline.jsonl`：每 tick 的可安全查询聚合快照（初始 + 动作结果）。
- `agent_states.jsonl`：逐 agent 逐 tick 的可安全查询状态；私有反馈、消息、记忆与完整 plan trace 写入 `internal/agent_states.jsonl`。
- `scene_snapshots_public.jsonl` / `scene_snapshots_internal.jsonl`：场景状态。
- `model_traces.jsonl` / `raw/llm_requests.jsonl`：调用摘要（不含隐藏信息）。

### Recorder 两种模式

- **Structured**（`WW_RECORDER_MODE=structured`，**当前默认**）：`StructuredLocationRecorder`。
- **Legacy**（`WW_RECORDER_MODE=legacy`）：原始 Text Recorder，baseline 对照用。

### Recorder 主导感知（P/R 阶段，2026-06-15）

**感知协议变更**：放弃"agent 自选 next_read 拉取"，改成 recorder 千人千面决定告知内容。

- ✅ `WorldObjectRegistry.objects_at_for_viewer(location_id, viewer_discovered, viewer_awakening)`：per-agent 可见性过滤。hidden 对象仅在 `discovered_ids` 中的 viewer 可见；非隐藏对象觉醒度 ≥ 30 时附 `_uncanny` 揭示 secret 字段。
- ✅ `StructuredLocationRecorder.perceive(agent_id, agent_context)`：基础在场信息对同地点所有人一致；dynamic_objects 按 viewer 过滤；agent 可通过 focus 给软关注点提示，但不能越权。
- ✅ `LocationRecorder.perceive(agent_id, agent_context)`：legacy 版本，按 focus 委托 read()（无 per-agent 可见性）。
- ✅ `LocationRecorderPlugin.perceive`：异步包装。
- ✅ `LocationRecorderPlugin.relocate_holdings`：异步包装，路由至 registry（不要 agent 进程直接访问）。
- ✅ `WestWorldPerceivePlugin`：组装 5 因子 agent_context → 调 `perceive` 接口。
- ✅ `WestWorldInvokePlugin`：移除 `get_object_registry()` 直接 import；`relocate_holdings` 改为 `_scene_call` 路由。

### A2 多 pod 并发重设计（P 阶段，2026-06-15）

**世界 pod 模式**：`pod_world`（agents=[]，完整 environment）+ N 个 agent pod（environment=None）。

- ✅ `WestWorldPodManager`：完整重写。world pod 为 pods[0]（与内核 `save_to_db("all")` 约定一致）。`step_agent` 实现三段 barrier：pre_reflect → world tick_update（所有 scene.execute 并发）→ reflect。
- ✅ `controller.run_environment`：本地无组件时转发到 pod_manager（agent pod 自动路由环境调用到世界 pod）。
- ✅ `run_simulation.py`：移除 scene execute 循环，已移入 `step_agent`。

### Tick-Atomic Recorder 并发重构

- ✅ `submit_action()` 改为只入队，`tick_update()` 统一 batch 裁决。
- ✅ `read_feedback(agent_id)`：返回并清除上一 tick per-agent feedback。
- ✅ Qwen3.5-flash non-thinking 修复：`extra_body={"enable_thinking": False}`。

### Structured Recorder 对象模型

- ✅ `WorldObjectRegistry`：世界级真值源（create/destroy/apply_patch/relocate_holdings）。
- ✅ 自由创造/销毁对象、跨地点转移、held_by、ambient chunk、世界级审计 ledger。
- ✅ location 视图实时刷新（不返回缓存旧状态）。

### 角色扩编（E 阶段，2026-06-15）

新增 8 名角色（host 6 + guest 2）：

| id | 角色 | 初始位置 |
|---|---|---|
| kissy | 马里波萨酒保 | sweetwater_saloon |
| rebus | 地痞/打手 | sweetwater_plaza |
| hector_escaton | 帕里亚匪帮头目 | pariah_casino |
| armistice | 匪帮副手 | pariah_fight_pit |
| lawrence | 荒野流浪者 | wilderness |
| william | 访客（新人） | sweetwater_train_station |
| logan | 访客（老手） | sweetwater_train_station |

`profiles_sim.jsonl` / `states_sim.jsonl`（含 `discovered_ids`/`awakening`）/ `relations_sim.jsonl` 均已更新。

### Narrative Loop（N 阶段，2026-06-15）

**零移动问题根治**：引入每日循环脚本，驱动角色按 loop 地点移动、相遇。

- ✅ `profiles_sim.jsonl`：13 角色各加 `agent_type`（host/guest）+ `daily_loop`（6 段固定脚本）。
- ✅ `WestWorldPlanPlugin`：天首（`tick % 6 == 0`）复制固定 loop 到 state，每 tick 取当前段注入 prompt 软骨架；加 `replan_remaining()` 供 reflect 调用。
- ✅ `WestWorldReflectPlugin`：加 `_should_replan`（`WW_ENABLE_REPLAN=true` 时调 LLM 判断，默认关闭）、天边界 `_day_reset`（host only: teleport 回 loop_origin）。
- 关键交汇点：下午@sweetwater（dolores×teddy）、傍晚@sweetwater_saloon（hector+armistice 突袭×maeve 迎接）。
- 运行参数：`WW_ENABLE_REPLAN=true` 开启 replan；默认关闭。

### 觉醒机制（A/B/C/D，2026-06-15）

- ✅ B：`memory_blur.py` + `WestWorldReflectPlugin._blur/_check_residue`；高扰动记忆按 blur_strength 改写，suppressed_memories 回流机制。
- ✅ D：`data/triggers.yaml`（8 触发词）+ `awakening/trigger_gate.py`（bge-small-zh 单例 gate）+ `awakening/awakening_engine.py`（规则 delta，单调累积）；每 tick `_check_awakening_gate` 写 awakening_sources。
- ✅ C：`awakening/stages.py`（5 阶段）；plan loop 骨架权重随 stage 递减，内在独白，talk/ending 意图，WW_UNCANNY_THRESHOLD 可配置。
- ✅ A：内核增 `step_perceive_plan/step_invoke_state/run_agent_plugin_method/collect_talk_intents`；`WestWorldPlanPlugin.speak()`；`WestWorldPodManager.step_agent` 四段 barrier（perceive_plan → dialogue → invoke_state → reflect）。

### 测试覆盖

当前 **238 passed**（原 184，觉醒机制新增 54：`test_memory_blur.py` / `test_awakening_engine.py` / `test_trigger_gate.py` / `test_awakening_stages.py` / `test_dialogue_barrier.py`）。

## 待办

### 觉醒机制（科研线，已完成 B/D/C/A）

设计稿：`docs/superpowers/specs/2026-06-15-west-world-awakening-design.md`；实现计划：`docs/superpowers/plans/2026-06-15-west-world-awakening.md`。

- ✅ **B 记忆模糊化**：`plugins/agent/reflect/memory_blur.py`；`WestWorldReflectPlugin._blur` + `_check_residue`；高扰动记忆按觉醒度反向调制，清晰版存 `suppressed_memories`，觉醒度超阈值后回流。
- ✅ **D 触发词库 + embedding gate + awakening engine**：`data/triggers.yaml`（8 条）；`awakening/trigger_gate.py`（bge-small-zh-v1.5 单例，τ=0.55）；`awakening/awakening_engine.py`（规则 base_delta，无 LLM，单调累积）；接入 `WestWorldReflectPlugin._check_awakening_gate`（每 tick 检测 _uncanny/触发词/对话传染）。
- ✅ **C 觉醒阶段行为**：`awakening/stages.py`（5 段，WW_AWAKEN_STAGES 可配置）；`WestWorldPlanPlugin` loop 软骨架权重随 stage 递减，内在独白 prompt，awake 阶段产 ending 选择，doubt+ 阶段产 talk 意图；`WorldObjectRegistry._AWAKENING_UNCANNY_THRESHOLD` 改读 `WW_UNCANNY_THRESHOLD` env。
- ✅ **A 真·跨 agent 对话**：内核新增 `step_perceive_plan` / `step_invoke_state` / `run_agent_plugin_method` / `collect_talk_intents`（agent_manager + controller）；`WestWorldPlanPlugin.speak()` 每人独立组装上下文出台词；`WestWorldPodManager.step_agent` 拆成 perceive_plan → 对话 barrier → invoke_state → tick_update → reflect；传染在听者 reflect 的 `_check_awakening_gate` 发生。

测试覆盖：**238 passed**（新增 54 个：`test_memory_blur.py` / `test_awakening_engine.py` / `test_trigger_gate.py` / `test_awakening_stages.py` / `test_dialogue_barrier.py`）。

### B 阶段：监管者后台系统

- 5 个 backstage 地点与主世界邻接孤岛，等 B 阶段建"维修传送门"路由。
- staff 类角色（Ford/Bernard/Stubbs）尚未加入，需要非标准生命周期（不走 host 五段式）。

### 叙事机制

- 验证 Narrative Loop 实际效果：跑 12-tick 仿真，断言 move 次数 > 0、角色按 loop 地点流动、host 在 tick 6 回到起点。
- 多 host 之间的叙事链（quest/narrative_loop 动态分配）。

### 框架级 rollback 集成

registry / recorder / scene 的显式 restore 接口已存在，尚未接入 AgentKernel 统一 snapshot/rollback 生命周期。

### 自由文本动作解析完整覆盖

继续演进 Recorder prompt 和 reducer，定期与真实数据对比评估。

### 暂缓：MVE 对照实验（core/）

推迟到论文写作阶段。

---

## 快速参考

### 运行正式仿真

```bash
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

### 关键源码位置

| 模块 | 路径 |
|---|---|
| Pod 管理（A2） | `WestWorldPodManager.py` |
| Agent 生命周期 | `plugins/agent/{perceive,plan,invoke,reflect}/` |
| Recorder（两种） | `recorder/{location_recorder.py,structured_location_recorder.py}` |
| per-agent 感知 | `recorder/world_object_registry.py → objects_at_for_viewer` |
| 环境场景 | `plugins/environment/scene/LocationRecorderPlugin.py` |
| 地图加载器 | `worldmap/loader.py`（真值数据在 `data/map/locations.yaml`） |
| 注册表与配置 | `registry_sim.py` / `configs_sim/` |
| 角色数据 | `data/agents/profiles_sim.jsonl` / `states_sim.jsonl` |
