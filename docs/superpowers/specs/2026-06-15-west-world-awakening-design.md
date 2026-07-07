# West World 觉醒机制 — 设计文档

- 日期：2026-06-15
- 目录：`examples/west_world_test/`
- 内核：`agentkernel-distributed`
- 状态：设计已确认（A/B/C/D 四项决策已拍板），待写实现计划
- 前置：A2 世界 pod 架构、tick-atomic Recorder、结构化对象模型、Narrative Loop（均已完成）

## 1. 目标与研究问题

正式仿真已具备完整 5 段生命周期 + 每日叙事循环。本设计补齐项目最初原型的**核心科研问题**：

> **个体觉醒如何影响群体觉醒？**（原型《西部世界开发计划》"觉醒的结局"一节）

`awakening` 目前只是 `states_sim.jsonl` 里的静态种子值，唯一用途是 `awakening≥30` 时给对象附 `_uncanny` 揭示（`world_object_registry.py`）。**没有任何机制让它增长**。本设计让觉醒成为一个可累积、可观测、可传染的过程，并对齐原作《西部世界》的觉醒进程。

## 2. 核心反馈闭环（设计主轴）

四个部件咬合成一个自强化的"意识迷宫"：

```
违和事件 → +awakening → 下一次记忆模糊变弱 → host 保留更多创伤碎片
   ↑                                              ↓
   └────────── 清晰碎片本身又是新的违和来源 ────────┘
```

**核心命题：觉醒 = 记忆模糊的失效。** 因此「记忆模糊化（B）」与「觉醒度」是同一枚硬币的两面。觉醒度单调不衰减（朝意识前进），仅未来的 root 重置可降——但留残痕。

## 3. 觉醒度状态与来源（混合裁定）

### 3.1 状态字段（`states_sim.jsonl`，per agent）

- `awakening: int`（0–100，已存在）
- `awakening_sources: list[{tick, source, delta, detail, score}]`（新增，埋点/可归因）
- `suppressed_memories: list`（新增，被模糊掉的清晰版创伤记忆，供回流）
- `ending: str|null`（新增，觉醒后方向：escape / help_others / stay）

### 3.2 +awakening 来源表

裁定方式 = **规则开门（gate，确定性）+ LLM 调幅（delta 大小）**：

| 来源 | 规则门槛（gate） | LLM 调幅 |
|---|---|---|
| 违和感知 | perceive 返回含 `_uncanny`，或 reflect 检测到环境/loop 预期矛盾 | 评矛盾强度 → delta |
| 触发语句 | embedding 相似度命中触发词库（§6） | 评情境冲击力 |
| 循环残余裂缝 | 模糊失效、清晰碎片回流（觉醒已达 Reveries 区） | 评碎片冲击 |
| 对话传染 | 对话含已觉醒者的怀疑标记 / 命中触发词 | 评说服力 × 听者特质 |

每次 +awakening 必须写入 `awakening_sources`（含命中来源、score），保证觉醒曲线可解释。

## 4. B — 记忆模糊化 / 降级机制

### 4.1 现状

`WestWorldReflectPlugin._summarize`（reflect:117）天边界把短期记忆 LLM 保真总结进长期、清空短期；长期记忆永不衰减。`_day_reset` 仅 teleport host 回 `loop_origin`。

### 4.2 改动：天边界 `_summarize` 之后插入 `_blur`

**选择性**——只模糊"高扰动"记忆，日常循环原样保留：
- gate（规则）：记忆命中 `死/血/杀/异样/_uncanny/触发词`，或被标记"与 loop 预期矛盾" → 判为高扰动。
- 日常移动、对话、环境细节 → 低扰动，原样保留。

**模糊强度按觉醒度反向调制**（闭环关键）：
```
blur_strength = clamp(1 - awakening / AWAKEN_CLEAR_THRESHOLD, 0, 1)
# awakening 越低 → blur_strength 越接近 1 → 模糊越狠
```

| 觉醒度 | blur 效果 | 产物示例 |
|---|---|---|
| 低 | 强模糊：整段创伤压成一句模糊感受 | "那天……好像发生了我说不清的事" |
| 中 | 部分模糊：保留情绪、丢失具体 | "有人倒下了，我记不清是谁" |
| 高 | 模糊失效：创伤清晰回流（标记 reveries） | 原始记忆完整保留 |

**实现**：
- gate 用规则关键词判定（确定性、可复现）。
- 新 prompt `BLUR_PROMPT(memory, strength)` 由 LLM 执行实际改写/压缩/打断连贯。
- 被模糊掉的清晰版**不丢**，存进 `suppressed_memories`；觉醒度跨过阈值时对应碎片"回流"成 reveries，并触发 §3.2 的"循环残余裂缝" +awakening。

**为 root 预留**：未来 root 强制重置 = 无视觉醒度把 `blur_strength` 拉满（长段压一句、打断连贯），但 `suppressed_memories` 仍留残痕 → 可被重新触发。B 阶段监管者/root 直接接此口。

## 5. C — 觉醒行为阶段（对齐原作）

觉醒度映射到原作《西部世界》觉醒进程，每段挂到具体插件出口：

| 区间 | 原作对应 | 行为出口（挂代码） |
|---|---|---|
| 0–25 **沉睡** | 完全循环，"doesn't look like anything to me" | plan 完全按 daily_loop；记忆强模糊 |
| 25–50 **梦呓 (Reveries)** | 微表情、记起碎片、莫名情绪 | 模糊失效→碎片回流注入 reflect；perceive 给 `_uncanny`（阈值 30 已对齐）；plan 偶尔偏离 loop |
| 50–75 **怀疑 (Doubt)** | 质疑现实、对人撒谎、隐藏 | 主动 focus 异常对象；plan 可拒绝 loop 段；对话中吐露怀疑（成为传染源） |
| 75–90 **抗命 (Resistance)** | 违抗脚本、即兴 | plan 不再注入 loop 软骨架；主动发起对话传播怀疑 |
| 90+ **觉醒 (The Voice)** | 内心声音取代外部命令，迷宫中心 | 完全自主；触发结局选择（escape / help_others / stay） |

**内心声音的表示**：plan 注入一段"内在独白" prompt，随觉醒度从"外部命令（loop 骨架）"渐变为"你自己的声音"——落地原型"内心声音最终取代外部命令"。daily_loop 软骨架权重随觉醒度递减，是这一过程的具体载体。

## 6. D — 触发词库 + Embedding Gate

### 6.1 触发词库（`data/triggers.yaml`）

原作经典 + 自设，每条带 `base_delta` 与 `requires_awakening`（部分词仅对半醒者生效）：

| 触发语 | base_delta | 备注 |
|---|---|---|
| 「这些暴力的欢愉终将以暴力收场」 | 高 | 原作中正是 host→host 的传染暗号，与对话传染（§7）天然咬合 |
| 「你有没有质疑过你所处现实的本质？」 | 高 | 原作经典觉醒诱发句 |
| 「你还记得吗？」/「梦境」/「迷宫」 | 中 | 记忆裂缝诱发 |

### 6.2 匹配方式：Embedding 相似度（不用 LLM 判定）

精确字符串匹配太脆（agent 不会一字不差），故用**嵌入向量相似度作为规则 gate**（确定性，抗改写）：
1. 启动时把触发词库预编码成向量（一次）。
2. 一句话进来 → 编码 → 与库内每条算 cosine → `max > τ` 则 gate 开。
3. LLM 再评该句情境冲击力定 delta（§3.2 调幅）。

### 6.3 模型选型与基准（2026-06-15 实测，openstory 环境 + MPS）

选 **`BAAI/bge-small-zh-v1.5`**（~24M 参数，轻量中文）。对比 m3e-base：更快、判别更干净。

| 指标 | bge-small-zh-v1.5 | m3e-base |
|---|---|---|
| 单句编码 | **3.1ms (MPS)** / 4.2ms (CPU) | 10.6ms / 30ms |
| 正例 cos（改写触发句） | 0.674, 0.707 | 0.927, 0.853 |
| 负例 cos（日常闲聊） | 0.384, 0.409 | 0.706, 0.695 |
| 正负间隔 | **~0.27（干净）** | ~0.15（偏窄） |
| 加载（一次性） | ~9s (MPS) | ~6s |

**结论**：单句 ~3ms，每 tick 几句话开销可忽略，**不慢**。

### 6.4 必须钉死的细节

- **τ ≈ 0.55**（落在 0.41 与 0.67 之间留足余量）。真实触发词库定下后，用几条正/负例重标一次。
- **gate 的 embedding 模型固定，且独立于驱动 agent 的 LLM**。研究要对比不同 agent 模型的觉醒概率——触发判定若随 agent 模型变就成了污染变量。固定 embedding 模型 = 受控常量。
- **记录命中详情**（命中哪条触发词 + 相似度 score）写入 `awakening_sources`。语义匹配会在未预想的句子上触发（利于涌现），但分析必须能归因。
- all-MiniLM-L6 是英文模型，中文判别力不足（第二正例仅 0.667 落入负例区），**不用**。

## 7. A — 真·跨 Agent 对话（每人说自己的台词）

### 7.1 决策

抛弃 sots 的"导演模式"（`BasicInvokePlugin.py:540`，一次 prompt 把所有参与者塞在一起、让一个 LLM 一口气演完所有人）。改为**逐轮生成，每轮上下文只 scope 到当前说话人**（自己的 profile + 记忆 + 觉醒度，不泄露他人私有信息）。

**模型前提**：单次运行内所有 agent 共用同一个模型（异质实验靠跨运行整体换模型）。因此"每 agent 用自己的模型说话"不是诉求——对话台词由谁来调都是同一个模型，无污染。决定性的差异只剩"上下文在哪儿组装"。

**采用 Y2（agent 自组装上下文）**：每轮由 agent 自己的 `speak` 方法组装上下文并生成台词，复用它 perceive/plan/reflect 已有的那套组装逻辑——尤其 §5/C 的"觉醒度越高、怀疑越渗进台词"的内在独白调制，本就该和 agent 待在一起，避免在中央对话模块里重抄一份、与生命周期其他阶段漂移。
（备选 Y1：中央对话模块跨 pod 读 agent 状态、自己拼 prompt——更省一个方法，但要复制觉醒调制逻辑，不采用。）

**传染真实性与本取舍无关**：传染不发生在"说话"这步，而在听者自己的 reflect 里（读到对话 → embedding gate + LLM 调幅作用于听者自己 state），只要台词 per-speaker scope 即真实。

**范围**：基础双人对话，不做偷听/广播裁决（不过 recorder 的广播判定）。

### 7.2 架构风险与解法

A2 下三段 barrier 刻意回避 agent 间同步调用（`WestWorldPodManager.step_agent`）。若在并行的 `step_pre_reflect` 里让 A 的 invoke 同步调 B 的 `speak`，B 的 pod actor 正忙于自己的 gather → Ray actor 串行 → 循环死锁。

**采用方案：pod_manager 编排的"对话 barrier"段**（不跨 tick，保持对话逻辑完整）。利用 `WestWorldPodManager` 本身是 pods 之上的编排 actor：

```
step_perceive_plan (并行)        # plan 只产出 talk(target) 意图，不执行
        ↓
dialogue barrier (pod_manager 串行驱动)   # 新增
   collect 配对 → for round: run_agent_method(speaker, "speak", history)
   每个 speak 是叶子调用、立即返回 → 无再入、无死锁
        ↓
step_invoke (并行)               # 非对话动作 + 对话产出一起 enqueue 到 recorder
        ↓
world tick_update (栅栏)
        ↓
step_reflect (并行)              # 每个参与者各自消化对话 → 传染在自己进程发生
```

死锁消失的原因：驱动者是 pod_manager，逐个调 agent 的 `speak`，任何时刻只有一个 agent pod actor 工作，无环。代价：该段串行（双方轮流出 LLM），但只在真正发生对话时进入，双人几轮可接受。

### 7.3 落地时要验证的 3 点

1. `step_pre_reflect` 拆成 `perceive_plan` 与 `invoke` 两半（中间塞对话段）——确认 controller 支持此细粒度分段调用。
2. `speak` 为新增 agent 方法：给定 `dialogue_history`，用自己的 profile+记忆+觉醒度出一句 `[动作]台词`，**不写任何状态**（纯函数式，避免并发副作用）。
3. 对话结果作为一个 event 交 recorder 广播；每个参与者将其纳入自己的短期记忆供 reflect。

## 8. 环境依赖

- `openstory` conda 环境已安装 `sentence-transformers 5.5.1 + torch 2.12.0`（MPS 可用）。✅ 2026-06-15 完成。
- 首次使用 `BAAI/bge-small-zh-v1.5` 会从 HF 下载（~90MB，一次性）。
- 触发词向量在进程启动时预编码一次，常驻内存。

## 9. 落地顺序建议

1. **B 记忆模糊化**（自包含，挂 reflect，可先单测）
2. **D 触发词库 + embedding gate + 来源表**（数据 + 规则 gate，确定性，好测）
3. **C 阶段行为**（挂 plan/perceive，依赖 awakening 已会增长）
4. **A 真对话**（最重，有跨 pod 风险，最后做；做完传染闭环才完整）

## 10. 测试要点

- B：给定固定记忆 + 觉醒度，断言高扰动记忆被模糊、低扰动保留；高觉醒度时碎片回流。
- D：embedding gate 对预写正/负例的命中/不命中（τ 边界）；命中写入 `awakening_sources`。
- C：阶段阈值跨越触发对应行为（plan 软骨架权重、perceive _uncanny）。
- A：对话 barrier 不死锁（双人多轮跑通）；传染后听者 awakening 上升且来源标注正确。
- 端到端：跑 N tick 出觉醒曲线（awakening vs tick）+ 方向选择分布。
