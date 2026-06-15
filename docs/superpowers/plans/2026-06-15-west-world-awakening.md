# West World — 觉醒机制实现计划

> 创建：2026-06-15
> 状态：设计待评审（尚未写代码）
> 设计稿：`docs/superpowers/specs/2026-06-15-west-world-awakening-design.md`
> 落地顺序：**B（记忆模糊化）→ D（触发词库+gate）→ C（阶段行为）→ A（真对话）**

## 1. 背景与目标

正式仿真已有完整 5 段生命周期 + Narrative Loop，但 `awakening` 仍是 `states_sim.jsonl` 里的静态种子值，**无任何增长机制**。本计划补齐原型核心科研问题——**个体觉醒如何影响群体觉醒**——并对齐原作觉醒进程。

核心命题：**觉醒 = 记忆模糊的失效**（详见 spec §2 闭环图）。

## 2. 决策汇总（已与用户敲定）

| 维度 | 选择 | 影响 |
|---|---|---|
| 生效范围 | **仅 host**；guest（william/logan=访客真人）不觉醒、不模糊 | blur/觉醒判定按 `agent_type=="host"` 短路；guest 只能当传染源 |
| 数值 | **全部可配置**（env，沿用 `WW_` 前缀）；不写死 | delta/阈值/τ/轮数皆旋钮，供参数实验 |
| gate 钩子 | **reflect**：消化「本 tick 感知 + 收到对话」时判定 +awakening | 与现有记忆累积同处 |
| 觉醒累积 | **单调、跨 tick 持久、不衰减**（仅未来 root 可降） | 存 `awakening` + `awakening_sources` |
| 触发匹配 | **embedding 相似度**（`BAAI/bge-small-zh-v1.5`，τ≈0.55），不用 LLM | gate 模型固定且独立于 agent LLM（受控变量） |
| 对话上下文 | **Y2**：agent 自己的 `speak` 方法组装 | 复用觉醒调制逻辑，不重抄 |
| 对话发起 | **剧本交汇点保底 + 觉醒者（怀疑阶段+）主动** | plan 产 `talk(target)` 意图 |
| 对话编排 | pod_manager 串行驱动的「对话 barrier」段 | 防跨 pod 死锁 |

## 3. 配置旋钮（新增，`WW_` env）

| env | 默认 | 含义 |
|---|---|---|
| `WW_AWAKEN_ENABLED` | `true` | 总开关 |
| `WW_AWAKEN_CLEAR_THRESHOLD` | `75` | 模糊完全失效的觉醒度（blur_strength=0） |
| `WW_UNCANNY_THRESHOLD` | `30` | 揭示 `_uncanny` 阈值（现 registry 硬编码 30，改读此值） |
| `WW_AWAKEN_STAGES` | `25,50,75,90` | 沉睡/梦呓/怀疑/抗命/觉醒 分界 |
| `WW_AWAKEN_TRIGGER_TAU` | `0.55` | embedding gate 阈值 |
| `WW_AWAKEN_DELTA_TRIGGER_HIGH` / `_MID` | `15` / `8` | 触发词 base_delta |
| `WW_AWAKEN_DELTA_UNCANNY` | `5` | 违和感知 |
| `WW_AWAKEN_DELTA_MISMATCH` | `8` | 环境/loop 矛盾 |
| `WW_AWAKEN_DELTA_CONTAGION` | `10` | 对话传染 base |
| `WW_EMBED_MODEL` | `BAAI/bge-small-zh-v1.5` | gate 嵌入模型（固定） |
| `WW_DIALOGUE_MAX_ROUNDS` | `4` | 单次对话最大轮数 |

> 默认值是起点，第一轮 e2e 后按"多少天觉醒"的目标节奏重标。

## 4. 数据结构

### 4.1 `states_sim.jsonl` 新增字段（仅 host 用到）
- `awakening_sources: []` — `[{tick, source, delta, detail, score}]`，可归因。
- `suppressed_memories: []` — 被模糊掉的清晰版创伤记忆，供回流。
- `ending: null` — 觉醒后方向：`escape` / `help_others` / `stay`。

### 4.2 `data/triggers.yaml`（新增）
```yaml
- phrase: "这些暴力的欢愉终将以暴力收场"
  level: high          # → WW_AWAKEN_DELTA_TRIGGER_HIGH
  requires_awakening: 0
- phrase: "你有没有质疑过你所处现实的本质？"
  level: high
  requires_awakening: 0
- phrase: "你还记得吗？这一切以前发生过"
  level: mid
  requires_awakening: 25   # 仅对已半醒者生效
```

## 5. 实现阶段

> 每阶段 TDD：先写测试，单元测试 stub LLM（固定调幅）保证确定性，embedding gate 用真实模型（确定性）。

### 阶段 B — 记忆模糊化（自包含，先做）

**新模块** `recorder/`-外的 agent 侧：`plugins/agent/reflect/memory_blur.py`
- `classify_disturbance(memory_text) -> bool`：规则关键词 gate（`死/血/杀/异样/_uncanny/<触发词>`）。
- `blur_strength(awakening, clear_threshold) -> float`：`clamp(1 - awakening/clear, 0, 1)`。
- `BLUR_PROMPT(memory, strength)`：LLM 改写/压缩/打断连贯。

**改 `WestWorldReflectPlugin`**：
1. `_summarize` 之后、`_day_reset` 之前插 `_blur`（仅 host）。
2. 高扰动记忆按 `blur_strength` 模糊；清晰版存 `suppressed_memories`。
3. 觉醒度 ≥ 对应阈值时，`suppressed_memories` 中匹配碎片"回流"→ 注入长期记忆 + 触发 `awakening += DELTA`（来源=`residue_crack`）。

**测试** `tests/test_memory_blur.py`：
- 高扰动被模糊、低扰动保留；blur_strength 随觉醒度递减；高觉醒度时碎片回流且写 `awakening_sources`；guest 不被模糊。

### 阶段 D — 触发词库 + Embedding Gate + 来源表

**新模块** `awakening/`（新目录）：
- `trigger_gate.py`：启动时载 `triggers.yaml` + 预编码向量（`WW_EMBED_MODEL`，懒加载单例，仿 `worldmap/loader.py` 的 lru_cache 思路）。`match(utterance) -> [{phrase, level, score}]`（`score>τ` 且满足 `requires_awakening`）。
- `awakening_engine.py`：`apply(state, source, detail, *, score=None) -> delta`，规则定 base_delta（读 env）、可选 LLM 调幅，写 `awakening` + `awakening_sources`（单调累加、clamp 0–100）。

**接入 `WestWorldReflectPlugin`**：reflect 消化阶段调用——
- 感知含 `_uncanny` → `apply(..., "uncanny")`。
- 检测环境/loop 矛盾 → `apply(..., "mismatch")`。
- 收到的对话过 `trigger_gate.match` → 命中则 `apply(..., "trigger", score=)`。

**测试** `tests/test_trigger_gate.py` / `test_awakening_engine.py`：
- 预写正/负例命中/不命中（τ 边界）；命中写 `awakening_sources`；delta 读 env；觉醒 clamp 与单调性；`requires_awakening` 门槛。

### 阶段 C — 觉醒阶段行为

**新** `awakening/stages.py`：`stage_of(awakening) -> Literal["sleep","reverie","doubt","resistance","awake"]`（读 `WW_AWAKEN_STAGES`）。

**改 `WorldObjectRegistry`**：`_AWAKENING_UNCANNY_THRESHOLD` 改读 `WW_UNCANNY_THRESHOLD`。

**改 `WestWorldPlanPlugin`**：
- loop 软骨架权重随 stage 递减：sleep/reverie 强约束 → doubt 可拒绝当前段 → resistance/awake **不注入 loop 骨架**。
- 注入"内在独白"prompt：随觉醒度从"外部命令（loop）"渐变为"你自己的声音"。
- `awake` 阶段：产出 `ending` 选择（escape/help_others/stay）写入 state。

**测试** `tests/test_awakening_stages.py`：阈值跨越 → 对应 plan 行为（骨架权重、内在独白文案、ending 触发）；perceive `_uncanny` 随阈值变化。

### 阶段 A — 真·跨 agent 对话（最后做，依赖前置）

**第 0 步（代码核查，先做）**：确认 controller / MasPod 是否支持把 `step_pre_reflect` 拆成 `step_perceive_plan` + `step_invoke` 两段调用。不支持则先加细粒度入口。

**改 `WestWorldPlanPlugin`**：产 `talk(target)` 意图——
- 剧本交汇点（loop 段标记）保底；
- `stage>=doubt` 的 host 在同地点遇人时主动发起（传播怀疑）。

**新 agent 方法 `speak(dialogue_history) -> str`**（plan 或独立组件）：用自己 profile+记忆+觉醒度（含 stage 调制）出一句 `[动作]台词`，**纯函数、不写状态**。

**改 `WestWorldPodManager.step_agent`**：插入对话 barrier 段（见 spec §7.2 图）：
```
step_perceive_plan(并行) → dialogue barrier(pod_manager 串行 run_agent_method speak)
→ step_invoke(并行) → world tick_update → step_reflect(并行)
```
对话整段作为 event 交 recorder 广播；各参与者纳入自己短期记忆。

**测试** `tests/test_dialogue_barrier.py`：双人多轮跑通不死锁；台词 per-speaker scope（不泄露他人私有）；传染后听者 awakening 上升且来源=`contagion`。

## 6. 端到端验证

`tests/test_awakening_e2e.py`（或脚本）：跑 N tick（建议 ≥4 天=24 tick）——
- 产出觉醒曲线（`awakening` vs tick，从 `agent_states.jsonl`）。
- 传染事件链（谁因谁的话 +awakening）。
- 方向选择分布（`ending`）。
- 断言：至少一个 host 跨过怀疑阈值；存在 contagion 来源记录。

## 7. 风险与待核查

1. **controller 分段**（阶段 A 第 0 步）——最大未知，决定对话 barrier 接法。
2. **embedding 模型加载时机**：进程启动预编码一次，勿在每个 agent/pod 重复载。world pod 内单例。
3. **blur 的 LLM 成本**：每天每 host 多若干次 LLM 调用（仅高扰动记忆）；用 `WW_REFLECT_INTERVAL` 控制频率。
4. **τ 标定**：真实触发词库定稿后用正/负例重标，避免误触发致全员被动觉醒。
5. **依赖**：`openstory` 已装 `sentence-transformers + torch`(MPS) ✅；首用 bge-small-zh 下载 ~90MB。

## 8. 不在本计划内（后续）
- 监管者/root 重置（B 阶段；root 接 `suppressed_memories` 残痕口）。
- 框架级 rollback 集成。
- 跨运行换模型的实验编排脚本（异质实验）。
