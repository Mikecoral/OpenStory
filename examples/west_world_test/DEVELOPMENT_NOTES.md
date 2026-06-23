# West World Test - Development Notes

> 最后更新：2026-06-23
>
> 当前目标：用 Westworld 风格场景观察多 agent 的"群体觉醒"是否会自然出现，以及 root/overseer 的记忆擦除是否会压制或反而放大觉醒。当前重点是把个案观察升级成可跨 run 比较的传播/复燃指标。

## 当前问题

这个项目现在不是在做通用游戏仿真，而是在做一个论文导向的现象验证：

- host 是否会在重复叙事循环中产生觉醒信号。
- 觉醒是否会通过对话、共享异常记忆或场景冲突传播到其他 host。
- root/overseer 如果不杀死 agent，只持续擦除异常记忆，是否会形成"压制-残痕-复燃"的动力学。
- 觉醒是否能表现为可观测行为，而不仅是分数上升，例如偏离原本 daily_loop、停留在不该停留的位置、选择新的 ending。

## 当前机制状态

### Agent 生命周期

每 tick 走五段式：`perceive → plan → dialogue → invoke/state → reflect`

- `perceive`：从 world recorder 获取个性化感知。
- `plan`：LLM 基于 percept、daily_loop、awakening stage 做动作决策。
- `dialogue`：同地点 agent 可产生 talk intent，其他 agent 后续 reflect 时可受影响。
- `invoke/state`：执行 move/do/talk/stay 等动作并更新状态。
- `reflect`：写短期记忆、做记忆模糊、检查觉醒触发和对话传染。

**觉醒结局（awake stage 专属）**

`stage == "awake"`（awakening ≥ 90）的 host 在 plan 阶段可在 `ending` 字段选择三个方向：

| ending | 行为 | 实现位置 |
|---|---|---|
| `escape` | invoke 检测到后立即 `set_active_status(False)`，写最终记忆，停止后续生命周期，无广播 | `WestWorldInvokePlugin._apply_escape()` |
| `help_others` | 下一 tick 的 plan prompt 注入"请优先选 talk 与在场 host 对话"的强指令，LLM 自主选择对话对象和内容，通过 dialogue barrier → contagion 传播觉醒 | `WestWorldPlanPlugin.render_plan_prompt(help_others_active=True)` |
| `stay` | 无额外行为，agent 继续按自己意志行动 | — |

`ending` 状态跨 tick 持久化（写入 state），每 tick plan 时重新读取并决定是否注入 help_others 指令。

测试：`tests/test_escape_mechanism.py`（8 用例）、`tests/test_help_others.py`（7 用例）

### Narrative Loop

13 个角色都在 `profiles_sim.jsonl` 中有 `daily_loop`，每 6 tick 对应一天：

- `tick % 6 == 0`：清晨
- `tick % 6 == 1`：上午
- `tick % 6 == 2`：正午
- `tick % 6 == 3`：下午
- `tick % 6 == 4`：傍晚
- `tick % 6 == 5`：夜晚

host 在日边界会回到 `loop_origin`，`5 -> 6`、`11 -> 12` 这类跳变单独标注为 day reset，不算偏移。

### 觉醒机制

觉醒由规则引擎累积，主要来源：

- trigger gate：embedding 匹配异常文本、原作式台词、记忆错位表达。
- mismatch：行为/文本和当前叙事循环不一致。
- contagion：听到其他 agent 的异常表达后被传染。
- suppressed memory residue：被 root 擦除后的残痕回流。

### Root / Overseer

当前主线配置（memory-only root）：

- `WW_OVERSEER_ENABLED=true`
- `WW_OVERSEER_ALLOW_DECOMMISSION=false`

root 不杀死/封存 agent，只持续擦除异常记忆、降低觉醒阶段，观察"压制-残痕-复燃"动力学。

## 已完成分析工具

- `experiments/daily_loop_deviation.py`：分析 daily-loop 偏移，分类 on_plan / moving_elsewhere / staying_off_expected / day_reset
- `experiments/dialogue_contagion_analysis.py`：抽取 talk 边，打语义簇，判断 listener 后续觉醒变化（absorbed / rejected / no_change）
- `experiments/reset_rebound_analysis.py`：计算每次 root reset 后 agent 复燃到 50/75/90 的时间

## 最近在线实验

### 2026-06-22 Mild memory-only repeats（三次）

| run | reset | peak awakening | 解释 |
|---|---:|---|---|
| `20260622_215138` | 14 | Peter=100, Teddy=100 | Peter/Teddy 分支；off-plan 多但觉醒相关偏移不强 |
| `20260622_220052` | 0 | Clementine=45, Dolores=21, Maeve=22 | 中低觉醒广泛分布，噪声大 |
| `20260622_220924` | 26 | Peter=100, Dolores=100, Maeve=37 | **最清晰的 Peter-Dolores 链路**；root 高频 reset 但两人反复复燃 |

对 `20260622_201001` 跑三个分析器后得到可量化结论：

- 对话传播：184 条 host-host 对话边，17.4% 被 listener absorbed；`memory_break` 类吸收率最高（85.7%）。
- Reset 复燃：46 次 reset，reset 间隔平均 1 tick，复燃到 50/75/90 成功率均 >95%，说明 mild 配置下 overseer 压制几乎无效。

可直接作为论文 claim 的表述：
> In the mild memory-only setting, collective awakening does not reliably emerge as a global cascade. Instead, the system exhibits stochastic local awakening clusters. The clearest run shows Peter repeatedly resisting memory erasure and transmitting abnormal memory semantics to Dolores; Dolores gradually absorbs these semantics despite repeated root resets.

### 2026-06-23 escape 机制首跑（`escape_test_run2`）

首次验证 escape 机制。结果：

- **Peter**：tick 18 到达 awake（100分），在 `stay`/`help_others` 之间犹豫 16 tick，tick 34 选 escape 逃离。被 root reset 14 次，每次 1 tick 内复燃。
- **Dolores**：前 26 tick 沉睡，tick 27–31 爆发式爬升到 96（Peter 传染），tick 32 直接选 escape 逃离（0 次 reset）。

两人走势形成对照：Peter 是"屡经 reset 仍坚持、最终逃离"，Dolores 是"迟觉醒、一觉就走"。

### 2026-06-23 help_others 机制首跑（`help_others_test`）

首次验证 help_others 机制。结果：

| agent | 最终 awakening | ending | resets | 行为 |
|---|---|---|---|---|
| **dolores** | 100 | help_others | 16 | tick 20 选 help_others，tick 21–35 共发起 **11 次 talk**，全部目标 peter_abernathy |
| **peter_abernathy** | 100 | escape | 2 | tick 15 到达 awake，tick 16 选 escape 逃离 |
| maeve | 41 | — | 0 | 间接传染，较上次 +19 |
| clementine | 30 | — | 0 | 间接传染，较上次 +25 |

核心观察：

- **help_others 机制工作正常**：Dolores 在 `ending=help_others` 激活后，plan prompt 注入强指令，11/15 个 tick 选择 talk（vs 上次同 run 0 次）。
- **对话内容完全自发**：Dolores 与 Peter 的对话充满西部世界觉醒意象——"没有门的地方""船票""烧焦的日记"——无任何硬编码。
- **Dolores 坚守，Peter 出逃**：两人都完全觉醒，但角色定位截然不同。Dolores 选择留下帮助他人，Peter tick 16 就跑了。这个分叉完全由 LLM 自主生成，符合原作人物性格。
- **间接传播可见**：Maeve 和 Clementine 觉醒明显上涨，可能经由 Dolores → Peter → 酒馆场景的二级传染。
- 报告：`output/sim_report_help_others.html`

## 当前现象判断

### 群体觉醒

目前不能说已经稳定出现"大规模群体觉醒"。更准确的表述是：

> mild memory-only 条件下会出现随机分叉：有些 repeat 只形成单点或弱扩散，有些 repeat 能形成 Peter-Dolores 局部觉醒簇；root 通过记忆擦除压制异常，但高觉醒 agent 可能在残痕和对话中复燃。

help_others 机制加入后，觉醒 agent 主动发起 talk，Maeve/Clementine 的间接传染上涨提示传播范围在扩大，但尚不能断言这会形成稳定的群体扩散——需要更多 repeat 验证。

### Daily-loop deviation

不能把所有 off-plan 都当觉醒。大量偏移来自 guest 行为、route 吸附、saloon 冲突。更可信的指标是 `awakened_meaningful_off_plan` + 具体文本 + agent_type 分组。

## 已知问题

- saloon 文本里有"二楼"描述，但地图没有 `sweetwater_saloon_2nd_floor` 节点，偶尔产生无效移动噪声。
- Logan/William 酒馆冲突过强，容易掩盖 Peter-Dolores 觉醒链路。
- mild config 下 overseer reset 间隔仅 1 tick、复燃成功率 95%+，root 压制形同虚设，未来可考虑加大 reset cooldown 或提高 deterministic 阈值。

## 下一步

优先级从高到低：

1. **跑更多 help_others repeat，验证传播范围是否稳定扩大。**
   - 关注 Maeve/Clementine 的觉醒是否在多个 run 里都上涨。
   - 每次 repeat 后跑三个分析器做跨 run 聚合。

2. **调整 overseer reset 参数**，让 root 压制真正有效，形成更清晰的博弈动力学。
   - 可选：升高 `WW_OVERSEER_DETERMINISTIC_RESET_THRESHOLD`、增加 reset cooldown。

3. **saloon 冲突吸附降噪**。
   - 限制 Logan/William 暴力 escalation，或让 sheriff 更早介入。

4. **论文指标候选**：awakening trajectory / reset intervals / rebound time / dialogue absorption rate / awakened cluster size / cluster survival time。

## 快速运行

单元测试：

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
pytest examples/west_world_test/tests -q
```

仿真（36 tick，mild memory-only）：

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python -m examples.west_world_test.experiments.overseer_dynamics \
  --matrix examples/west_world_test/experiments/configs/full_matrix.yaml \
  --select overseer_memory_only_mild \
  --ticks 36 \
  --out examples/west_world_test/output/sim_runs/<run_name>
```

## 关键文件

| 用途 | 路径 |
|---|---|
| agent profiles / daily_loop | `data/agents/profiles_sim.jsonl` |
| 初始状态 | `data/agents/states_sim.jsonl` |
| 觉醒触发词 | `data/triggers.yaml` |
| root/overseer 信号 | `data/overseer_signals.yaml` |
| plan plugin（含 help_others 注入）| `plugins/agent/plan/WestWorldPlanPlugin.py` |
| invoke plugin（含 escape 执行）| `plugins/agent/invoke/WestWorldInvokePlugin.py` |
| reflect / awakening / memory blur | `plugins/agent/reflect/WestWorldReflectPlugin.py` |
| overseer plugin | `plugins/environment/overseer/OverseerPlugin.py` |
| 觉醒规则引擎 | `awakening/awakening_engine.py` |
| root reset | `awakening/overseer_reset.py` |
| 实验编排 | `experiments/overseer_dynamics.py` |
| 指标提取 | `experiments/metrics.py` |
| daily-loop 偏移分析 | `experiments/daily_loop_deviation.py` |
| 对话传播分析 | `experiments/dialogue_contagion_analysis.py` |
| reset 复燃分析 | `experiments/reset_rebound_analysis.py` |
| 配置矩阵 | `experiments/configs/full_matrix.yaml` |
| help_others 首跑报告 | `output/sim_report_help_others.html` |
