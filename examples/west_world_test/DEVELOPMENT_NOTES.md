# West World Test - Development Notes

> 最后更新：2026-06-25
>
> 当前目标：验证多 agent 群体觉醒动力学（压制-残痕-复燃-传播），出论文主图数据。

## 当前机制状态

### Agent 生命周期

每 tick 走五段式：`perceive → plan → dialogue → invoke/state → reflect`

每 6 tick = 1 天；13 个角色，6 段 daily_loop（清晨/上午/正午/下午/傍晚/夜晚）。

### 觉醒机制

觉醒值 0–100 由规则引擎累积，来源：
- `self_trigger`：agent 自身 `thought`/`detail` 命中 embedding gate（单 tick 最多触发一次）
- `trigger`：外部消息/场景文本命中 gate（单 tick 最多触发一次）
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

**Prompt 设计原则**（v4，当前）：
- 三选项平权，各有一句情感动机描述，无锚定语言
- help_others："你曾独自在黑暗中挣扎过；若你看到身边还有人正陷于同样的困惑…"
- talk 提示始终显示（不依赖上一 tick 是否选过 help_others）
- 每 tick 明确告知可改变选择

### `thought` 内心独白字段

plan 阶段新增 `thought` 字段（host 专属，不说出口），直接作为 `self_trigger` 来源进入 embedding gate 检测，驱动觉醒自然涌现。

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
| **实验结果记录** | `RESULTS.md` |
