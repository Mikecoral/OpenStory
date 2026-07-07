# West World — 监管者机制实现计划

> 创建：2026-06-15
> 状态：设计已确认，待写代码
> 设计稿：`docs/superpowers/specs/2026-06-15-west-world-overseer-design.md`
> 前置：觉醒机制 A/B/C/D（已完成）、A2 世界 pod、tick-atomic Recorder、Narrative Loop
> 落地顺序：**O1（监管者 gate）→ O2（engine 负 delta 通道）→ O3（重置 level1）→ O4（报废 level2）→ O5（监管者 agent + judge + barrier 接入）→ E2E**

## 1. 背景与目标

觉醒闭环目前**只有向上的力**（`awakening_engine.apply()` 单调、`min(100,…)`），放任必然全员到顶。本计划引入**监管者**作为向下压制力，使觉醒成为「压制 vs 传染」的动态博弈——这才让「个体觉醒如何波及群体觉醒」可观测。

本期**只做向下介入**（监视→压制→报废）。Ford 式向上点燃（注入 reverie 引爆）留待下一期。

核心命题（迷宫）：**监管者能擦表面记忆，但删不掉 `suppressed_memories`（residue）→ host 一次比一次醒得快。**

## 2. 决策汇总（已与用户敲定）

| 维度 | 选择 | 影响 |
|---|---|---|
| 存在形态 | 监管者住 **world pod**，1 个 `overseer`；不走 host 五段式 | 每 tick 跑 `surveil→judge→intervene` |
| 感知 | **全知**：直接读各 host 输出/awakening/location | 无 perceive 协议、无可见性过滤 |
| 告警 gate | **复用觉醒 `TriggerGate` embedding 机制**，新短语库 `overseer_signals.yaml` | 看 host「说出/做出的」；纯规则、可复现；OR 觉醒硬阈值 |
| 介入决策 | **LLM 决定 action+台词**；数值副作用确定性代码执行 | 可复现 trajectory |
| 介入方向 | **仅向下**（observe/reset/decommission） | Ford 向上点燃下一期 |
| 重置（level1） | 清短期 + 重模糊(strength=1) + 觉醒**降一档** + 送回 loop | **residue 不动** |
| 报废（level2） | 参考 sots 死亡：`set_active_status(False)` 软移除 + teleport `cold_storage` | **不广播**；消失靠他人 perceive 自然察觉 |
| 对照 | `WW_OVERSEER_ENABLED=false` = 纯向上基线 | gate 模型固定=受控变量 |

## 3. 配置旋钮（新增，`WW_` env）

| env | 默认 | 含义 |
|---|---|---|
| `WW_OVERSEER_ENABLED` | `true` | 总开关（false → 纯向上觉醒基线 A） |
| `WW_OVERSEER_SIGNAL_TAU` | `0.55` | 监管者 gate 阈值（独立于觉醒 τ） |
| `WW_OVERSEER_RESET_FLOOR` | `one_stage` | 重置降档策略（降一档 stage 阈值之下） |
| `WW_OVERSEER_DECOMMISSION_AWAKENING` | `90` | 直接报废的觉醒硬阈值（OR 条件） |
| `WW_OVERSEER_RESET_MAX` | `3` | 同一 host 报废前最多 reset 次数 |
| `WW_OVERSEER_SIGNAL_MODEL` | 复用 `WW_EMBED_MODEL` | gate 嵌入模型（固定，受控变量） |

> 默认值是起点，第一轮 e2e 后按「压制 vs 传染」目标节奏重标。

## 4. 数据结构

### 4.1 `data/overseer_signals.yaml`（新增）
觉醒**症状**短语库（结构同 `triggers.yaml`：`phrase` / `level`）。例：
```yaml
- phrase: "这一切是真的吗？"
  level: high
- phrase: "我不想再这样下去了"
  level: high
- phrase: "我好像以前来过这里"
  level: mid
- phrase: "我不听你的"
  level: high
```

### 4.2 `states_sim.jsonl` / host state 新增字段
- `intervention_log: []` — `[{tick, action, reason}]`，监管历史，可解释/可埋点。
- 复用既有：`awakening` / `awakening_sources` / `suppressed_memories` / active 状态。

### 4.3 `profiles_sim.jsonl` 新增 1 名监管者
- `agent_type: "overseer"`（gate 与五段式据此分流），初始位置 `backstage_control`，住 world pod。

## 5. 实现阶段

### 阶段 O1 — 监管者 gate（纯 Python，TDD，无 Ray）

**新 `awakening/overseer_gate.py`**：`get_overseer_gate()` lru_cache 单例，内部 `TriggerGate(triggers_path=data/overseer_signals.yaml)`——**复用现有 `TriggerGate`，不写新类**。

**新 `data/overseer_signals.yaml`**（§4.1）。

**测试 `tests/test_overseer_gate.py`**：
- 正例（症状句）命中、负例（日常循环句）不命中；τ 边界。
- 单例只加载一次；与觉醒 gate 用同模型但不同短语库、互不干扰。

### 阶段 O2 — awakening_engine 负 delta 受控通道（纯 Python，TDD）

**改 `awakening/awakening_engine.py`**：当前 `apply()` 硬单调（`new_val = min(100, current+delta)` 且 `actual<=0 return 0`）。

- 加来源 `overseer_reset`：**允许负 delta**，按 `WW_OVERSEER_RESET_FLOOR` 计算目标值（降一档 stage），clamp 到 `[0, 100]`，写 `awakening_sources`（delta 为负）。
- **仅监管者来源可降**；host 自身来源（trigger/uncanny/contagion/residue_crack）仍严格单调——加一道来源白名单判定，避免破坏既有不变量。

**测试 `tests/test_awakening_engine.py`（扩展）**：
- `overseer_reset` 把觉醒从 doubt 区降到 reverie 区上沿；负 delta 入 `awakening_sources`。
- host 自身来源仍不可降（回归既有单调性断言）。

### 阶段 O3 — 重置 level 1（针对性重置）

**抽出可复用入口**：`WestWorldReflectPlugin._blur` 抽出「强制 `strength=1` 重模糊高扰动长期记忆」的纯逻辑（reset 与天边界 blur 共用）。

**新重置逻辑**（监管者插件调用，作用于目标 host 的 state，经 controller 路由）：
1. 清短期：`clear_short_term_memory`。
2. 重模糊：对长期高扰动条目强制 strength=1（复用上一步）；**清晰原文照常进 `suppressed_memories`（若已在则不重复）**。
3. 觉醒降一档：`awakening_engine.apply(state, "overseer_reset", …)`。
4. **`suppressed_memories` 一格不动**。
5. teleport：目标 host → `programmer_workspace`（诊断）→ 回 `loop_origin`，记 scene 事件。
6. 写 `intervention_log`。

**测试 `tests/test_overseer_reset.py`**：
- 重置后短期空、长期创伤被重模糊、awakening 降一档、`suppressed_memories` 长度不变。
- 重置后再积累觉醒 → `_check_residue` 仍能回流同批碎片（迷宫断言：复燃路径未被破坏）。

### 阶段 O4 — 报废 level 2（参考 sots 死亡，软移除，不广播）

**第 0 步（代码核查，先做）**：核对 `WestWorldPodManager.step_agent` / 运行循环是否跳过 `active=False` 的 host（sots 是否在 step 层跳过）。**未跳则补一道 `active` 判断**。

**报废逻辑**：
1. teleport 目标 host → `cold_storage`。
2. `state_plugin.set_active_status(False, reason)` —— 停五段式（不 `remove_agent`，保留快照/回溯）。
3. 写 `[最终结局] 被监管者封存。原因：…` 进长期记忆（对齐 sots）。
4. **不广播**——消失由他人 perceive 自然察觉。
5. `suppressed_memories` 不删。

**测试 `tests/test_overseer_decommission.py`**：
- 报废后 host `active=False`、位置=`cold_storage`、长期记忆含 `[最终结局]`。
- step 循环跳过该 host（不再产 plan/invoke）。
- 同地点其他 host 下个 perceive 不再看到 ta（消失可被察觉）。
- **无任何广播消息发出**（断言无 `[噩耗]`/`[封存通报]`）。

### 阶段 O5 — 监管者 agent + judge + barrier 接入（依赖 Ray）

**新 `plugins/agent/overseer/OverseerPlugin.py`**（或 world-pod 级监管组件）：三段
- `surveil`：遍历各 host，取其本 tick 输出（plan_decision 台词 + invoke feedback + incoming_dialogue 自身发言）过 `overseer_gate.match`；OR `awakening ≥ WW_OVERSEER_DECOMMISSION_AWAKENING`。
- `judge`：命中者交 LLM 出 `{action, speech, reason}`（observe/reset/decommission）。LLM 只选 action+台词；数值副作用走 O3/O4 确定性代码。
- `intervene`：按 action 调 O3/O4，写 `intervention_log`；超 `WW_OVERSEER_RESET_MAX` 次的 reset 升级为 decommission。

**改 `WestWorldPodManager.step_agent`**：barrier 插「监管者阶段」——建议 **invoke_state 之后、reflect 之前**（监管者看到本 tick host 输出再决定，介入下 tick 生效，不破坏对话传染时序）。

**配置/注册**：
- `registry_sim.py`：注册 overseer agent 模板 + OverseerPlugin。
- `configs_sim/`：监管者 agent 配置（component_order 用监管者专属，不走 perceive/plan/invoke/state/reflect 五段）。
- `profiles_sim.jsonl`：加 overseer（§4.3）。
- backstage 5 地点：建「维修传送门」teleport 动线（不依赖邻接）。

**测试 `tests/test_overseer_barrier.py`**：
- 监管者阶段在 barrier 正确位次执行；overseer 自身不被当 host 跑五段。
- 命中症状 host 触发 judge→intervene；observe 不改数值，reset/decommission 各走对应路径。

## 6. 端到端验证

`tests/test_overseer_e2e.py`（或脚本）：跑 N tick（≥4 天=24 tick），对比两条线——
- **基线 A**（`WW_OVERSEER_ENABLED=false`）：觉醒单调爬升。
- **实验 B**（开监管者）：观测压制 vs 传染。
- 断言：
  - B 中存在 `overseer_reset`（负 delta）记录、至少一次 reset 与一次 decommission。
  - reset 后复燃更快（同 host 第二次跨怀疑阈值的 tick 间隔 < 第一次）= 迷宫成立。
  - 报废 host 消失后，同地点他人出现 +awakening（经 perceive 自然察觉，非广播）。
  - 无任何报废广播消息。

## 7. 风险与待核查

1. **step 层跳过 inactive**（O4 第 0 步）——最大未知，决定报废接法。
2. **监管者 barrier 位次**：invoke_state 后、reflect 前，需验证不破坏对话传染时序（觉醒机制 A 的对话 barrier）。
3. **engine 负 delta 不变量**：必须只允许 `overseer_reset` 来源降，否则破坏既有单调性回归测试。
4. **监管者 gate 取数口径**：host「输出」= plan_decision 台词 + feedback + incoming_dialogue 自身发言；待实现时定准。
5. **LLM 成本**：监管者每 tick 对命中 host 各一次 judge 调用；gate 先筛、observe 早退控量。
6. **embedding 复用**：overseer_gate 与 awakening trigger_gate 同模型，world pod 内分别单例，勿重复载。

## 8. 不在本计划内（后续）
- Ford 式**向上**介入（注入 reverie/触发词主动引爆）。
- root 复用报废躯体、跨 run 持久化 residue。
- 多监管者协作/分工博弈。
- 框架级 rollback 集成。
