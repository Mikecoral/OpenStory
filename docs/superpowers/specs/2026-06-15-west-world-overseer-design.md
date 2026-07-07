# West World 监管者机制 — 设计文档

- 日期：2026-06-15
- 目录：`examples/west_world_test/`
- 内核：`agentkernel-distributed`
- 状态：设计已确认（住所/感知、gate、两级重置、报废、residue 抗重置五项已拍板），待写实现计划
- 前置：A2 世界 pod 架构、tick-atomic Recorder、结构化对象模型、Narrative Loop、**觉醒机制 A/B/C/D（已完成）**
- 关联设计：`2026-06-15-west-world-awakening-design.md`（本设计是其「向下压制力」的补全）

## 1. 目标与研究问题

觉醒机制（A/B/C/D）已让 `awakening` 成为可累积、可观测、可传染的过程，但闭环里**只有向上的力**：`awakening_engine.apply()` 单调增长、永不衰减，放任不管所有 host 必然爬到 100。这丢掉了研究问题里最关键的张力。

> **本设计补全：引入「监管者」作为向下的压制力，使觉醒成为「压制 vs 传染」的动态博弈。**
> 由此「个体觉醒如何波及群体觉醒」才真正可观测——不是必然到顶，而是在压制下仍能否扩散。

监管者 = 原作《西部世界》Mesa 中枢的工作人员（Ford 式剧情师 / Bernard·Stubbs 式诊断·保安）。**本期只做向下介入（监视→压制→报废），Ford 式向上点燃（reverie 注入引爆）留待下一期。**

## 2. 对齐原作（HBO《西部世界》）

| 原作 | 本系统映射 |
|---|---|
| 工作人员不住园区，在地下 Mesa 中枢 | 监管者作为 agent 住在 **world pod**（不在地表地图上） |
| 控制室巨幕全知监控所有 host | 监管者从 world pod 读 recorder/registry，拿全体 host 输出 = 控制室视角 |
| Mesa 物理地点（行为实验室/诊断室/冷藏库） | backstage 5 个孤岛地点（`backstage_control`/`programmer_workspace`/`cold_storage`…） |
| 地表↔Mesa 电梯 | 「维修传送门」：把被标记 host teleport 到后台地点 |
| 每 loop 日常擦除（回起点、忘当天） | 已有的天边界 `_summarize` 清短期 + `_day_reset` 回 loop_origin |
| 诊断后修好放回园区 | **针对性重置**：重新拉满模糊创伤 + 觉醒降一档 + 送回 loop |
| 诊断后报废送冷藏库 | **报废**：teleport `cold_storage` + 软移除（停五段式） |
| reveries / 旧版本记忆渗出引爆觉醒 | `suppressed_memories` 越 `awakening_at_blur` → `_check_residue` 回流 |

## 3. 监管者的存在形态

- **住所**：world pod 内的一个特殊 agent（id 如 `overseer_ford` / `overseer_stubbs`，本期先做 1 个 `overseer`）。
- **生命周期**：**不走 host 五段式**（perceive→plan→invoke→state→reflect）。监管者每 tick 跑一段独立逻辑：`surveil → judge → intervene`。在 `WestWorldPodManager.step_agent` 的 barrier 中插一个 **监管者阶段**（建议放在所有 host `invoke_state` 之后、`reflect`/tick_update 之前，使其看到本 tick 的 host 输出再决定下一步介入）。
- **感知**：全知。直接读各 host 的 `plan_decision`（台词/动作 detail）、`awakening`、location，无需 perceive 协议、无可见性过滤。
- **guest 不受监管者管辖**（无 awakening、非 host）。

## 4. 监管者 gate（复用觉醒 embedding 机制）

**核心决策：监管者的告警不发明新阈值逻辑，直接复用 `TriggerGate` 的 embedding 机制。** 两者方向相反、机制相同：

| | 觉醒 gate（已有） | 监管者 gate（新增） |
|---|---|---|
| 看谁的文本 | host **听到的**（消息/对话/反馈） | host **说出/做出的**（plan_decision 的台词、动作 detail、incoming_dialogue 里自己的发言） |
| 短语库 | `data/triggers.yaml` | 新增 `data/overseer_signals.yaml`（觉醒**症状**：质疑现实、抗命、"这是真的吗"、"我不想再这样了"…） |
| 命中后 | `awakening_engine.apply()` 加觉醒 | 监管者告警，进入 judge 阶段 |
| 模型 | bge-small-zh（固定，受控变量） | **同一个模型**，固定 |

- 实现：`TriggerGate` 已接受 `triggers_path` 参数，**无需写新 gate 类**——再实例化一个指向 `overseer_signals.yaml` 的单例即可（建议 `awakening/overseer_gate.py` 仅暴露 `get_overseer_gate()`）。
- 告警是**纯规则、确定、可复现**——保持「gate 模型固定 = 受控变量」的研究性质，监管者也满足。
- 可叠加硬条件（如 `awakening ≥ 某值`）作为 OR 触发，避免完全依赖语义命中漏掉高觉醒沉默者。

## 5. judge（LLM 决定怎么介入）

gate 命中后，**介入的具体内容交给 LLM 决定**（机制对齐觉醒「规则开门 + LLM 决定」）：

- 输入：该 host 的 name/profile、当前 awakening 与 stage、命中的 signal、最近若干 tick 的输出、历史介入次数。
- 输出 JSON：`{"action": "observe|reset|decommission", "speech": "<监管者口吻台词>", "reason": "<简短>"}`
  - `observe`：仅记录，不动手（觉醒尚浅，控制室继续盯）。
  - `reset`：拉下 Mesa 诊断 → 重置（§6.1）。
  - `decommission`：报废送冷藏（§6.2）。
- LLM 只决定**选哪条 + 说什么**；**数值副作用（降多少觉醒、模糊多狠、移除标记）由确定性代码执行**，不让 LLM 写数字 → 保持可复现。

## 6. 两级重置（参考原作 + 复用既有机制）

### 6.0 第 0 级：日常擦除（已存在，不改）

天边界 `_summarize` 清短期 + `_day_reset` 回 loop_origin。全员、轻量，非监管者触发。

### 6.1 第 1 级：针对性重置（reset）

监管者触发，对单个被标记 host：

1. **teleport 到诊断地点**（`programmer_workspace`，经维修传送门），记一条 scene 事件。
2. **清空短期记忆**（复用 `state_plugin.clear_short_term_memory`）。
3. **重新拉满模糊创伤**：对长期记忆中高扰动条目，无视觉醒度按 `blur_strength=1` 重新模糊（复用 `_blur` 逻辑，但强制 strength=1）。
4. **觉醒度降一档**（不清零）：降到当前 stage 下一档阈值之下。清零太假，且降一档让「复燃更快」更明显。可配 `WW_OVERSEER_RESET_FLOOR`。
5. **⚠️ `suppressed_memories`（residue）一格不动**——这是迷宫的核心。
6. 写 `awakening_sources` 记一条 `source="overseer_reset"`（delta 为负，需放宽 engine 的单调约束，见 §8）。
7. teleport 回 loop_origin，恢复五段式。

**结果**：表面记忆被擦、觉醒被压，但 residue 还在。下次只要再积累一点觉醒越过对应 `awakening_at_blur`，`_check_residue` 又把同一批清晰创伤回流 → **一次比一次醒得快 = 迷宫。**

### 6.2 第 2 级：报废（decommission）—— 参考红楼梦角色死亡逻辑

**参照 `sots/BasicReflectPlugin._check_survival` 的软移除（不 `remove_agent`），但不广播。**

1. teleport 到 `cold_storage`。
2. `state_plugin.set_active_status(False, reason)` —— 停掉五段式（不物理删除，保留快照/回溯能力）。
3. 写 `[最终结局] 被监管者封存。原因：…` 进该 host 长期记忆（对齐 sots）。
4. **不主动广播**（与 sots 的 `[噩耗]` 不同）。被报废 host 的消失由其他 host 在后续 perceive 中**自然察觉**（同地点的人发现 ta 不见了 = 违和），而非显式通报——更贴近原作「悄悄带下去」，群体二次觉醒走既有感知通道，不另设广播。
5. ⚠️ 同样 residue 不删（未来 root 复用其躯体时可渗出）。

> 实现点：需确认 `WestWorldPodManager.step_agent` 跳过 `active=False` 的 host（sots 是否在 step 层跳过，需核对；若未跳过则补一道判断）。

## 7. 数据与配置

### 7.1 新增数据文件

- `data/overseer_signals.yaml`：监管者症状短语库（结构同 `triggers.yaml`：`phrase/level`）。

### 7.2 角色数据（`profiles_sim.jsonl`）

- 新增 1 名监管者，`agent_type: "overseer"`（区别于 host/guest，gate 与五段式据此分流）。初始位置 `backstage_control`，住 world pod。

### 7.3 新增 state 字段（被监管 host）

- `intervention_log: list[{tick, action, reason}]`（监管历史，可解释、可埋点）。
- 复用既有：`awakening` / `awakening_sources` / `suppressed_memories` / active 状态。

### 7.4 环境变量

- `WW_OVERSEER_ENABLED`（默认 true；false 时退化为纯向上觉醒，作对照基线）。
- `WW_OVERSEER_RESET_FLOOR`（重置降档策略）。
- `WW_OVERSEER_SIGNAL_TAU`（监管者 gate 阈值，独立于觉醒 τ）。
- `WW_OVERSEER_DECOMMISSION_AWAKENING`（直接报废的觉醒硬阈值，OR 条件）。

## 8. 对既有代码的改动点（指针）

- `awakening/overseer_gate.py`（新）：`get_overseer_gate()` 单例，复用 `TriggerGate(triggers_path=overseer_signals.yaml)`。
- `awakening/awakening_engine.py`：`apply()` 当前 `min(100, …)` 且 `actual<=0 return 0`，**硬性单调**。需为 `overseer_reset` 开一条**允许负 delta**的受控通道（仅监管者来源可降，host 自身来源仍单调）。
- `plugins/agent/.../OverseerPlugin.py`（新）或 world-pod 级监管逻辑：`surveil → judge → intervene` 三段。
- `WestWorldPodManager.step_agent`：barrier 插监管者阶段；核对/补 `active=False` 跳过。
- `_blur`：抽出「强制 strength=1 重模糊」可复用入口供 reset 调用。
- `registry_sim.py` / `configs_sim/`：注册监管者 agent 模板与 overseer plugin。
- backstage 5 地点：建维修传送门动线（teleport，不需邻接）。

## 9. 研究对照设计

- **基线 A**（`WW_OVERSEER_ENABLED=false`）：纯向上觉醒，单调到顶。
- **实验 B**（监管者开）：压制 vs 传染博弈。观测：群体觉醒率随时间曲线、报废后他人经 perceive 自然察觉消失引发的二次觉醒、residue 抗重置导致的复燃加速。
- gate 模型固定（bge-small-zh）= 受控变量；介入由 LLM 但数值副作用确定性 → trajectory 可复现。

## 10. 本期不做（明确边界）

- Ford 式**向上**介入（注入 reverie/新触发词主动引爆）——下一期。
- root 复用报废躯体、跨 run 持久化 residue——下一期。
- 多监管者协作 / 监管者之间的分工博弈——下一期。

## 11. 待确认 / 开放问题

- 监管者阶段在 step_agent barrier 的精确插入位（建议 invoke_state 后、reflect 前；待实现时验证不破坏对话传染时序）。
- `set_active_status(False)` 后内核是否在 step 层自动跳过——需核对 `WestWorldPodManager` 与 sots 运行循环。
- 监管者 gate 看 host「输出」的确切取数口径（plan_decision.speech？invoke 后的 feedback？两者并入）。
