# West World 记忆清除、觉醒测量与监管对抗汇报整理

> 基于当前 `examples/west_world_test` 实现与开发笔记整理。重点结论：当前系统已经完成机制链路和指标抽取，但默认参数下自然觉醒很弱；真正能稳定观察到「觉醒上升 -> reset 压制 -> 残痕复燃 -> 多次 reset 后 decommission」的是放大觉醒驱动后的 `overseer_stress` 实验配置。

## 一句话总览

当前做法不是单纯让 host 忘记记忆，而是把高扰动记忆模糊化并保留一份隐藏残痕；觉醒测量用 0-100 的 `awakening` 分数、阶段映射和来源日志；监管者作为 world pod 环境组件每 tick 监控 host 输出和觉醒度，在动作执行后、反思前执行观察、重置或报废。

## 1. 记忆清除：模糊化 + 残痕，而不是硬删除

### 当前机制

记忆清除分两条路径：

1. 正常 host 反思阶段的记忆模糊化。
2. 监管者 reset 时的强制清除与强制模糊。

正常反思路径中，`WestWorldReflectPlugin._blur()` 只处理 host 的长期记忆中最新一条高扰动内容。高扰动由 `memory_blur.py` 的关键词规则判定，目前关键词包括「死、血、杀、异样、_uncanny」。如果命中，系统会：

- 读取当前 `awakening`。
- 用 `blur_strength(awakening, clear_threshold)` 计算模糊强度。
- 将清晰原文写入 `suppressed_memories`，记录 `tick` 和 `awakening_at_blur`。
- 调 LLM 按强度把长期记忆最后一条改写为模糊版本。

这意味着觉醒度越低，记忆越容易被压成模糊情绪；觉醒度越高，模糊强度越低。默认 `WW_AWAKEN_CLEAR_THRESHOLD=75`，达到阈值后基本不再模糊。

### 残痕回流

`WestWorldReflectPlugin._check_residue()` 负责残痕复燃。逻辑是：当 host 的觉醒度超过第一阶段阈值（默认 `WW_AWAKEN_STAGES=25,50,75,90` 的 25）后，检查 `suppressed_memories`。如果当前觉醒度高于某条记忆被模糊时的觉醒度，则认为该碎片被“看穿”：

- 从 `suppressed_memories` 移除。
- 以 `[残痕回流] ...` 形式追加回长期记忆。
- 通过 `awakening_engine.apply(..., source="residue_crack")` 增加觉醒来源。

所以这个系统不是“清除后彻底消失”，而是构造了一个可复燃的隐藏记忆池。

### 监管者 reset 的记忆操作

`apply_overseer_reset()` 是 level-1 干预。它做五件事：

- 清空短期记忆。
- 扫描长期记忆中高扰动条目，加入 `suppressed_memories`，并去重。
- 通过 `awakening_engine.apply(..., source="overseer_reset")` 把觉醒度降一档。
- 写入 `intervention_log`。
- 返回需要强制改写的长期记忆条目，由 `OverseerPlugin._force_blur_one()` 用强度 1 调 LLM 改写。

这条路径比正常反思更强：正常路径只处理最新长期记忆，reset 会扫描长期记忆中的高扰动条目，并且强制 strength=1。

## 2. 觉醒测量：分数、阶段、来源、行为四层

### 核心状态

当前觉醒测量核心是 agent state 中的：

- `awakening`：0-100 整数。
- `awakening_sources`：累计来源日志，每条含 `tick/source/delta/detail/score/level` 等字段。
- `suppressed_memories`：被压制的清晰记忆残痕。
- `intervention_log`：监管者 reset/decommission 历史。

指标抽取时，`experiments/metrics.py` 直接读 `output/sim_runs/<run_id>/internal/agent_states.jsonl`，提取觉醒曲线、阶段、reset/decommission、残痕长度、觉醒来源和对话传染边。

### 五阶段映射

`awakening/stages.py` 把觉醒度映射为五个阶段，默认阈值：

| 分数区间 | 阶段 | 含义 |
|---|---|---|
| `<25` | `sleep` | 完全在循环中 |
| `25-49` | `reverie` | 记起碎片，情绪波动 |
| `50-74` | `doubt` | 质疑现实，开始隐藏想法 |
| `75-89` | `resistance` | 抗命，主动传播怀疑 |
| `>=90` | `awake` | 完全觉醒 |

阈值可用 `WW_AWAKEN_STAGES` 配置。

### 觉醒来源

`awakening_engine.apply()` 是统一入口。host-facing 来源只允许单调增加：

- `trigger`：触发词或语义触发。
- `uncanny`：percept 中出现 `_uncanny`。
- `mismatch`：预留的矛盾/错配来源。
- `contagion`：对话传播。
- `residue_crack`：被压制记忆回流。

只有 `overseer_reset` 可以产生负 delta，把觉醒度降一档。默认 delta 包括：high trigger +15、mid trigger +8、uncanny +5、mismatch +8、contagion +10、residue_crack +5。

### 触发检测

触发检测不靠 agent LLM 判断，而是 `TriggerGate`：

- 读取 `data/triggers.yaml` 中 8 条触发短语。
- 用 `BAAI/bge-small-zh-v1.5` 编码触发短语与输入语句。
- 用 cosine similarity 与阈值 `WW_AWAKEN_TRIGGER_TAU` 比较，默认 0.55。
- 支持 `requires_awakening`，例如部分短语只对觉醒度 >= 25 或 >= 50 的 host 生效。

`WestWorldReflectPlugin._check_awakening_gate()` 每 tick 在 reflect 阶段检查：

- percept scene 中是否有 `_uncanny`。
- percept messages。
- 上一动作 feedback。
- dialogue barrier 写入的 `incoming_dialogue`。

命中后写回 `awakening` 和 `awakening_sources`。

### 行为层观测

觉醒不是只看分数。`WestWorldPlanPlugin` 会根据阶段改变行为提示：

- `sleep/reverie`：日常 loop 仍然有强约束。
- `doubt`：允许拒绝与现实冲突的日常计划，并可触发真正对话。
- `resistance/awake`：不再被固定日程支配。
- `awake`：要求输出 `ending`，可选择 `escape`、`help_others`、`stay`。

所以可汇报的觉醒测量包含两类证据：数值曲线和行为偏离。

## 3. 监管对抗：world-pod 监管者 vs host 觉醒

### 调用位置

`WestWorldPodManager.step_agent()` 的 tick 顺序是：

1. `perceive_plan`
2. dialogue barrier
3. `invoke_state`
4. scene `tick_update`
5. overseer barrier
6. `reflect`

监管者在动作裁决之后、反思之前运行。这样它能看到本 tick host 的计划、动作反馈和对话输出，并在反思写入新记忆之前进行干预。

### 监管者结构

`OverseerPlugin` 是 world-pod 级环境组件，不是普通 host agent。主流程是：

1. `surveil`：遍历 host，过滤 guest 和已报废 `is_active=False` 的 host。
2. 收集 host 输出：`plan_decision` 中的 `speech/detail/thought`、`feedback`、自己说出的 dialogue line。
3. 用 `overseer_gate` 检测觉醒症状语义，或用觉醒阈值直接判定 suspect。
4. `judge`：优先走硬阈值，其次确定性 reset 阈值，最后才用 LLM judge。
5. `intervene`：执行 `observe`、`reset` 或 `decommission`。

### 干预动作

`observe`：只记录观察，不改变 host。

`reset`：level-1 干预：

- 清短期记忆。
- 高扰动长期记忆进入 `suppressed_memories`。
- 觉醒度降一档。
- 通过 backstage 路径把 host 转移到 `programmer_workspace`，再送回 `loop_origin`。
- 强制模糊被选中的长期记忆。
- reset 次数达到 `WW_OVERSEER_RESET_MAX`，默认 3，升级为 decommission。

`decommission`：level-2 干预：

- `set_active_status(False)`，停止后续五阶段生命周期。
- 写入 `[最终结局] 被监管者封存...` 长期记忆。
- location 设为 `cold_storage`，并通过 scene teleport 进入冷库。
- 写入 `intervention_log`。

### 对抗在哪里体现

当前对抗不是战斗系统，而是动力学对抗：

- host 侧：触发词、违和感知、对话、残痕回流推动 `awakening` 上升；阶段越高，日常 loop 权重越低，越可能 talk、抗命或选择 ending。
- overseer 侧：症状 gate 和觉醒阈值发现可疑 host；reset 降低觉醒并加深压制记忆；多次 reset 后 decommission 终止 host 生命周期。
- 残痕侧：reset 不会删除 suppressed 记忆，反而可能积累可复燃材料；后续觉醒度再升高时，残痕回流继续推动觉醒。

因此可汇报成「控制系统试图压低觉醒，但压制留下的残痕又成为下一轮觉醒燃料」。

## 4. 实验与指标现状

### 已有实验编排

`experiments/` 子包负责长 tick 动力学实验：

- `overseer_dynamics.py`：按参数矩阵启动独立子进程跑 `run_simulation`。
- `metrics.py`：从 run archive 提取时间序列和事件。
- `plot_dynamics.py`：生成觉醒轨迹、热力图、干预时间线、reset 间隔图。
- 输出包括 `records.jsonl`、`events.jsonl`、`summary.json`、`metrics/<config>.json` 和每个 config 的完整 run archive。

核心可画字段：

- `awakening` / `stage`
- `suppressed_len`
- `reset` / `decommission`
- `reset_intervals`
- `awakening_source_counts`
- `contagion_events`
- `location_flow`

### stress 配置结果

`experiments/configs/full_matrix.yaml` 中的 `overseer_stress` 做了三类放大：

- `WW_AWAKEN_TRIGGER_TAU=0.45`，降低觉醒触发阈值。
- 适度提高 trigger/contagion/mismatch delta。
- `WW_OVERSEER_DETERMINISTIC_RESET_THRESHOLD=25`，host 进入 reverie 即 reset。

开发笔记记录：该配置 30 tick 跑出了清晰动力学，host 在 25 阈值附近震荡，出现「爬升 -> reset -> 复燃 -> 再 reset」，8 个 host 呈现 reset x3 后 decommission x1 的链条，`reset_intervals` 可量化复燃周期。