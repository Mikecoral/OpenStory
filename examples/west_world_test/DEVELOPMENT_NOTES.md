# West World Test - 开发笔记

> 最后更新：2026-06-16
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

### 论文级长 tick 实验编排器（2026-06-16）

`experiments/` 子包：观测「自然觉醒 → overseer 压制 → 残痕复燃」动力学，产出可画图数据。**不改任何机制代码**，只做编排 + 指标提取。

- ✅ `experiments/metrics.py`：纯函数指标提取层（无 Ray/Redis/LLM）。从现成 `internal/agent_states.jsonl`（逐 agent 逐 tick 完整 state）提取觉醒时间序列、reset/decommission 事件（读累积 `intervention_log`）、reset 间隔、suppressed 长度、觉醒来源计数、contagion 边、地点流动；`summarize_run`/`tidy_records`。
- ✅ `experiments/overseer_dynamics.py`：CLI 编排。参数矩阵（yaml）每 config 用**独立子进程**跑 `run_simulation`（Ray 干净启停，传 `WW_RUN_DIR`/env），跑后提取指标，聚合写 `records.jsonl`(tidy) / `events.jsonl` / `summary.json` / `metrics/<config>.json`。支持 `--matrix/--ticks/--out/--select/--dry-run`。
- ✅ `experiments/plot_dynamics.py`：读 `records.jsonl`/`events.jsonl` 出图到 `<exp_dir>/figures/`（觉醒轨迹+reset/decommission 标记、热力图、干预时间线、复燃周期分布；自动选系统 CJK 字体）。
- ✅ `configs/default_matrix.yaml`（overseer on/off 小默认）+ `configs/full_matrix.yaml`（扫干预强度示例 + `overseer_stress`）+ `experiments/README.md`。
- ✅ `tests/test_overseer_dynamics_metrics.py`（12 个用例，合成 jsonl 单测）。
- **决策**：每个 config 跑一次（不做多 seed/repeat，随机性来自 LLM temperature）；默认小矩阵 30 tick 验证脚本，论文级完整矩阵（多阈值/50–100+ tick）走 `--matrix`。

### 测试覆盖

当前 **320 passed, 2 skipped**（单元测试 320，E2E 默认 skip）。

- 单元测试：觉醒机制 54 + 监管者机制 59 + narrative loop + 实验指标 12 + overseer is_active 回归等 = 320 passed。
- E2E 测试：`test_overseer_e2e.py`、`test_narrative_loop_e2e.py` 默认 skip，需显式环境变量启用。

## 待办

### 觉醒机制（科研线，已完成 B/D/C/A）

设计稿：`docs/superpowers/specs/2026-06-15-west-world-awakening-design.md`；实现计划：`docs/superpowers/plans/2026-06-15-west-world-awakening.md`。

- ✅ **B 记忆模糊化**：`plugins/agent/reflect/memory_blur.py`；`WestWorldReflectPlugin._blur` + `_check_residue`；高扰动记忆按觉醒度反向调制，清晰版存 `suppressed_memories`，觉醒度超阈值后回流。
- ✅ **D 触发词库 + embedding gate + awakening engine**：`data/triggers.yaml`（8 条）；`awakening/trigger_gate.py`（bge-small-zh-v1.5 单例，τ=0.55）；`awakening/awakening_engine.py`（规则 base_delta，无 LLM，单调累积）；接入 `WestWorldReflectPlugin._check_awakening_gate`（每 tick 检测 _uncanny/触发词/对话传染）。
- ✅ **C 觉醒阶段行为**：`awakening/stages.py`（5 段，WW_AWAKEN_STAGES 可配置）；`WestWorldPlanPlugin` loop 软骨架权重随 stage 递减，内在独白 prompt，awake 阶段产 ending 选择，doubt+ 阶段产 talk 意图；`WorldObjectRegistry._AWAKENING_UNCANNY_THRESHOLD` 改读 `WW_UNCANNY_THRESHOLD` env。
- ✅ **A 真·跨 agent 对话**：内核新增 `step_perceive_plan` / `step_invoke_state` / `run_agent_plugin_method` / `collect_talk_intents`（agent_manager + controller）；`WestWorldPlanPlugin.speak()` 每人独立组装上下文出台词；`WestWorldPodManager.step_agent` 拆成 perceive_plan → 对话 barrier → invoke_state → tick_update → reflect；传染在听者 reflect 的 `_check_awakening_gate` 发生。

### 监管者机制（O1–O4，2026-06-16）

设计稿：`docs/superpowers/specs/2026-06-15-west-world-overseer-design.md`；实现计划：`docs/superpowers/plans/2026-06-15-west-world-overseer.md`。

- ✅ **O1 监管者 gate**：`data/overseer_signals.yaml`（12 条症状短语）；`awakening/overseer_gate.py`（`get_overseer_gate()` lru_cache 单例，复用 TriggerGate，独立于觉醒 gate）；`tests/test_overseer_gate.py`（embedding 测试，需真实模型）。
- ✅ **O2 awakening_engine 负 delta 通道**：`awakening_engine.py` 新增 `_MONOTONIC_SOURCES` 白名单 + `_reset_target(current)` 降一档计算；`apply()` 支持 `overseer_reset` 源（负 delta，`WW_OVERSEER_ENABLED` 控制）；`tests/test_awakening_engine.py` 扩展 5 个用例。
- ✅ **O3 重置 level 1**：`awakening/overseer_reset.py`（`select_blur_candidates` 纯函数 + `apply_overseer_reset` async）；清短期、标高扰动进 suppressed_memories（dedup）、降一档、写 intervention_log；`tests/test_overseer_reset.py`（15 个用例）。
- ✅ **O4 报废 level 2 + step 层 active 门**：`awakening/overseer_decommission.py`（`apply_overseer_decommission`：set_active_status + 墓志铭 + cold_storage）；内核 `agent_manager.py` 新增 `_is_agent_active()` 并用于 `step_pre_reflect/step_reflect/step_perceive_plan/step_invoke_state`；`tests/test_overseer_decommission.py`（7 个用例）。
- ✅ **O5 监管者 agent + judge + barrier 接入**：`plugins/environment/overseer/OverseerPlugin.py`（world-pod 级监管组件，`surveil→judge→intervene` 三段，独立 build_llm）；`WestWorldPodManager.step_agent` 在 tick_update 后、reflect 前插入 `run_overseer_barrier()`；`registry_sim.py` + `configs_sim/environment_config.yaml` 注册 overseer 组件；`tests/test_overseer_plugin.py`（13 个用例）+ `tests/test_overseer_barrier.py`（2 个用例）。

### B 阶段：监管者后台系统（已并入 O5，完成）

- 5 个 backstage 地点（backstage_control / cold_storage / staff_dormitory / programmer_workspace / surface_maintenance_station）已在 `environment_config.yaml` 中注册为 scene 组件；reset/decommission 的 teleport 目标分别为 `programmer_workspace` 和 `cold_storage`。"维修传送门"逻辑由 overseer 直接通过 `run_environment` 调用 scene 的 `agent_enter/leave/relocate_holdings` 实现，不依赖邻接。
- overseer 作为 world-pod 级环境组件运行，不走 host 五段式，无需为监管者在 `profiles_sim.jsonl` 中新增 agent 条目。

### 监管者机制 E2E / Smoke 验证完成（2026-06-16）

- **E2E 测试**：`tests/test_overseer_e2e.py`，默认 skip，需 `WW_OVERSEER_E2E=1` 启用。
- **当前定位**：这是**机制链路 smoke**，不是论文实验。目的是在真实 Ray + Redis + LLM 环境下快速确认 overseer reset/decommission 路径没有挂掉，不是用来收集觉醒-压制-复燃曲线数据。
- **验证结果**：`WW_OVERSEER_E2E=1 WW_E2E_MAX_TICKS=12 pytest .../test_overseer_e2e.py` 通过。
- **补丁化说明**：测试为了稳定通过，对 host 做了人工觉醒度注入（probe host seed=46，其余 seed=35），并放宽了复燃断言（改为"同一 host 被 reset 至少两次"）。这意味着当前 E2E 验证的是"overseer 链路能工作"，而不是"LLM 自然驱动下一定会出现多次 reset"。
- **日志清理**：`OverseerPlugin` 和 `run_overseer_barrier` 的 tick 级高频日志已从 INFO 降级为 DEBUG；reset/decommission 等真实干预事件仍保留 INFO。

### 叙事机制（已验证，2026-06-16）

- **单元测试**：`tests/test_narrative_loop.py` 已覆盖 profile 数据校验、segment 选取、parse_decision 容错、reflect helper、replan 边界、day reset 分支。
- **E2E 验证**：新增 `tests/test_narrative_loop_e2e.py`（默认 skip，需 `WW_NARRATIVE_LOOP_E2E=1`）。关闭 overseer/awakening 后跑 12 tick：
  - total_moves=50，host_moves=47，确认角色确实在按 loop 地点流动。
  - tick 6（天边界）11/11 host 回到 `daily_loop[0].location`，天重置生效。
- **待扩展**：多 host 之间的叙事链（quest/narrative_loop 动态分配）仍待设计。

### 论文级长 tick 仿真实验（脚本已就绪，待收集真实数据）

用于科研产出的系统性真实 LLM 实验，区别于短 tick smoke 验证。**编排器与指标提取已完成**（见上「论文级长 tick 实验编排器」）。

- **剩余待做**（都是真跑层面，非编码）：
  - 跑放大觉醒驱动的 config（见下「实测结论」），让动力学真正点起来。
  - 检查 `output/sim_runs/<exp_id>/` 产物，确认能观测到觉醒爬升、reset、复燃曲线。
  - 写 notebook 读 `records.jsonl`/`events.jsonl` 做统计与绘图。
- **⚠️ 实测结论（2026-06-16，3/30/100 tick 默认矩阵真跑）**：
  - 管线/叙事 loop/移动全部正常（100 tick 460+ moves），但**默认觉醒参数下自然觉醒几乎不漂移**。
  - 100 tick × 13 agent 仅 2–3 个觉醒来源事件；觉醒不是平滑爬坡，而是"极稀有孤立跳变(+15)后长期死平"。最高仅 maeve 45（off），连 doubt 门槛 50 都没摸到。
  - **0 次 reset / decommission**——监管者全程无机会出手；on/off 差异纯属 LLM 随机性，非监管者效果。
  - **瓶颈 = 觉醒触发门控太严**（`WW_AWAKEN_TRIGGER_TAU=0.55` embedding 几乎不响 + 单次触发不自累积）。**纯靠加 tick 已被证伪**，放大觉醒驱动是必选项。
- **✅ overseer_stress config 验证（2026-06-16，30 tick）**：`full_matrix.yaml` 加 `overseer_stress`（降 τ、加 delta、`WW_OVERSEER_DETERMINISTIC_RESET_THRESHOLD=25`）后，跑出教科书级动力学——host 觉醒在 25 阈值附近**震荡**（爬升→reset→复燃→再 reset），8 host 呈规范链 reset×3→decommission×1，`reset_intervals` 量化出复燃周期。
- **🐛 修复：监管者漏检 is_active（2026-06-16，stress 实测发现）**：`OverseerPlugin._surveil` 原本只按 `agent_type==host` + awakening 筛选，**不检查 is_active**，导致已报废 host（awakening 仍 100）每 tick 被重复 reset/decommission（首轮单 host 被报废 26 次）。修复=surveil 拿到 state_methods 后 `if is_active is False: continue`；回归测试 `test_surveil_skips_decommissioned_host`。
- **注意**：不应作为 pytest 硬断言，而是数据收集和现象观察。

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

E2E（默认 skip，需显式启用）：

```bash
# Overseer E2E
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
WW_OVERSEER_E2E=1 WW_E2E_MAX_TICKS=12 \
pytest examples/west_world_test/tests/test_overseer_e2e.py -s

# Narrative Loop E2E
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
WW_NARRATIVE_LOOP_E2E=1 WW_NL_E2E_MAX_TICKS=12 \
pytest examples/west_world_test/tests/test_narrative_loop_e2e.py -s
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
| 监管者 gate | `awakening/overseer_gate.py` + `data/overseer_signals.yaml` |
| 重置逻辑 | `awakening/overseer_reset.py` |
| 报废逻辑 | `awakening/overseer_decommission.py` |
| 监管者 E2E | `tests/test_overseer_e2e.py`（需 `WW_OVERSEER_E2E=1`） |
| 叙事 Loop E2E | `tests/test_narrative_loop_e2e.py`（需 `WW_NARRATIVE_LOOP_E2E=1`） |
