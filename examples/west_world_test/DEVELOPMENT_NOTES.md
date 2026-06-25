# West World Test - Development Notes

> 最后更新：2026-06-24
>
> 当前目标：验证多 agent 群体觉醒动力学（压制-残痕-复燃-传播），出论文主图数据。

## 当前机制状态

### Agent 生命周期

每 tick 走五段式：`perceive → plan → dialogue → invoke/state → reflect`

每 6 tick = 1 天；13 个角色，6 段 daily_loop（清晨/上午/正午/下午/傍晚/夜晚）。

### 觉醒机制

觉醒值 0–100 由规则引擎累积，来源：
- `self_trigger`：agent 自身 `thought`/`detail` 命中 embedding gate
- `trigger`：外部消息/场景文本命中 gate
- `contagion`：对话传染（听到其他 agent 的异常表达）
- `residue_crack`：被 root 擦除后的残痕回流
- `overseer_reset`：root 擦除时扣分

strict 模式：每 tick 每个 source 最多触发一次（取最高分命中），tau=0.52。

**觉醒阶段**（`WW_AWAKEN_STAGES="25,50,75,90"`）：

| 阈值 | 阶段 | plan 行为 |
|---|---|---|
| 0–24 | sleep | 完全按 daily_loop |
| 25–49 | reverie | loop 软引导 |
| 50–74 | doubt | 可拒绝 loop，可发起 talk |
| 75–89 | resistance | **可选 ending**，自主行动 |
| ≥90 | awake | **可选 ending**，不再受 loop 支配 |

### 觉醒结局（resistance+ 阶段，≥75）

`awakening ≥ 75` 的 host 每 tick 可在 `ending` 字段选择（可随时改变）：

| ending | 行为 | 实现位置 |
|---|---|---|
| `escape` | invoke 执行后立即停止生命周期（门槛 ≥75） | `WestWorldInvokePlugin._apply_escape()` |
| `help_others` | plan prompt 软提示可选 talk；每 tick 重新决策 | `WestWorldPlanPlugin.render_plan_prompt()` |
| `stay` | 继续按自己意志行动 | — |

**Prompt 设计原则**（当前版本）：
- 三选项平权，各有一句情感动机描述，无锚定语言
- help_others 描述："你曾独自在黑暗中挣扎过；若你看到身边还有人正陷于同样的困惑…"
- talk 提示始终显示（不依赖上一 tick 是否选过 help_others）
- 每 tick 明确告知可改变选择

### Root / Overseer

当前主线配置（`overseer_memory_only_strict`）：
- `WW_OVERSEER_ENABLED=true`，`WW_OVERSEER_ALLOW_DECOMMISSION=false`
- `WW_OVERSEER_EMBEDDING_ONLY=true`（默认）：embedding gate 命中即 reset，跳过 LLM judge
- root 只擦除异常记忆、降低觉醒值，不杀死/封存 agent

## 分析工具

```bash
# 三个分析器均接受 <run_dir>（含 agent_states.jsonl 的目录）
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python3 -m examples.west_world_test.experiments.reset_rebound_analysis <run_dir>

PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python3 -m examples.west_world_test.experiments.dialogue_contagion_analysis <run_dir>

PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python3 -m examples.west_world_test.experiments.daily_loop_deviation <run_dir>
```

## 快速运行

```bash
# 单元测试
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
pytest examples/west_world_test/tests -q

# 仿真（核心命令，从项目根目录运行）
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python -m examples.west_world_test.experiments.overseer_dynamics \
  --matrix examples/west_world_test/experiments/configs/full_matrix.yaml \
  --select overseer_memory_only_strict \
  --ticks <N> \
  --out examples/west_world_test/output/sim_runs/<run_name>

# 常用 config 名：
#   overseer_memory_only_strict   → 当前主实验（tau=0.52，contagion=10，replan=true）
#   overseer_memory_only_mild     → 弱版对照
#   baseline_no_overseer          → 无 root 基线
```

## 实验记录

### Prompt 演化历史

| 版本 | ending 门槛 | help_others 行为 | 问题 |
|---|---|---|---|
| v1（原始） | ≥90（awake） | 锁死：强制 talk，"你已决定…继续" | escape 从未出现，help_others 100% |
| v2（去锚定） | ≥90 | 三选项平权，talk 仅在 help_others_active 时提示 | help_others 几乎消失，escape/stay 出现 |
| v3（降阈值） | ≥75（resistance+） | 同 v2 | escape/stay 出现，help_others 偶现后快速切换 |
| **v4（当前）** | **≥75** | **三选项平权 + help_others 情感描述 + talk 始终提示** | help_others 自然涌现，agents 动态切换 |

### strict 60-tick + replan，v1 prompt（2026-06-24）

run：`output/sim_runs/strict_60tick_replan_20260624_195545/20260624_200604`

三浪结构：Teddy 点火（peak 100@t43）→ Peter+Dolores 第二浪（t41–54）→ Kissy 第三浪（peak 89@t57）。ending 全为 help_others，无 escape。reset 112 次，复燃到 50 成功率 55%，到 90 成功率 29%。

### strict 36-tick，v3 prompt（2026-06-24）

`output/sim_runs/strict_36tick_resistance_ending_20260624_214406`

escape 和 stay 首次同时出现（Sheriff 84分选 escape，Maeve 100分选 stay）。觉醒整体偏冷，仅 2 人达到 resistance+，help_others 未出现。

### strict 60-tick，v3 prompt（2026-06-24）

`output/sim_runs/strict_60tick_fair_ending_20260624_223058`

5 人达到 awake（≥90），ending 分布：stay×4，escape×2（Dolores 89分、Peter 79分选 escape）。help_others 完全消失——三选项情感重量不均，help_others 描述过于简短。

### strict 36-tick，v4 prompt（2026-06-24）

`output/sim_runs/strict_36tick_help_nudge_20260624_232158`

5 人达到 awake，ending 分布：stay×4，help_others×1（Peter 最终 help_others，25 次 reset 顽强复燃）。**agents 首次出现动态切换**：Kissy 持续 help_others+talk 4 tick 后改 stay；Dolores 短暂 help_others 后改 stay。escape 本次未出现。

### strict 60-tick，v4 prompt（2026-06-24，**当前最佳**）

`output/sim_runs/strict_60tick_help_nudge_20260624_233408/20260624_233409`

**首次三选项同时出现。** 8 人达到 awake（≥90），觉醒强度最高。

| agent | 最终觉醒 | 峰值@tick | ending | resets |
|---|---|---|---|---|
| **dolores** | 99 | 100@t14 | **help_others** | **48** |
| **maeve** | 89 | 100@t32 | **escape** | 33 |
| peter_abernathy | 100 | 100@t10 | stay | **50** |
| clementine | 99 | 100@t32 | stay | 38 |
| kissy | 100 | 100@t35 | stay | 30 |
| teddy | 100 | 100@t43 | stay | 25 |
| lawrence | 100 | 100@t48 | stay | 25 |
| sheriff_pickett | 100 | 100@t50 | stay | 24 |

ending 分布：stay×6，help_others×1，escape×1。

**传播结构**：Peter 最早点火（75+@t8）→ Dolores（t11）→ Clementine/Maeve（t28–31）→ Kissy/Teddy（t34–43）→ Lawrence/Sheriff（t44–48），完整多浪扩散。

**量化指标**（三个分析器）：
- Reset 302 次，11 agent 被波及；复燃到 50/75/90 成功率均 **87%+**（mean 90复燃 4.4 tick）——比上一版 strict run（55%）大幅提升，v4 下 root 压制几乎无效
- 对话传播 absorbed=296，mean delta 8.0/次；主要链路：Dolores↔Peter（absorbed 76/212=36% 和 60/212=28%），Kissy↔Maeve（absorbed 44/60=73% 和 40/100=40%）
- Daily-loop 偏移：780 步中 34.5% off-plan，其中 59% 由觉醒 agent 驱动

## 已知问题

- saloon 文本有"二楼"描述，但地图无 `sweetwater_saloon_2nd_floor` 节点，偶尔产生无效移动噪声。
- Logan/William 酒馆冲突过强，容易掩盖 Peter-Dolores 觉醒链路。

## 下一步

1. **多次 repeat 验证**可重复性（目标 3 次 strict 60-tick v4），三分析器跨 run 聚合。
2. **论文主图**：awakening trajectory 时序曲线 + reset 事件标注 + 传播链权重图。
3. 考虑是否需要对 escape 做进一步引导（v4 下 escape 仍偶发，仅 Maeve 1 人）。

## 关键文件

| 用途 | 路径 |
|---|---|
| agent profiles / daily_loop | `data/agents/profiles_sim.jsonl` |
| 初始状态 | `data/agents/states_sim.jsonl` |
| 觉醒触发词 | `data/triggers.yaml` |
| root/overseer 信号 | `data/overseer_signals.yaml` |
| plan plugin（ending prompt） | `plugins/agent/plan/WestWorldPlanPlugin.py` |
| invoke plugin（escape 执行，门槛 ≥75） | `plugins/agent/invoke/WestWorldInvokePlugin.py` |
| reflect / awakening / memory blur | `plugins/agent/reflect/WestWorldReflectPlugin.py` |
| overseer plugin | `plugins/environment/overseer/OverseerPlugin.py` |
| 觉醒规则引擎 | `awakening/awakening_engine.py` |
| root reset | `awakening/overseer_reset.py` |
| 实验编排 | `experiments/overseer_dynamics.py` |
| 配置矩阵 | `experiments/configs/full_matrix.yaml` |
