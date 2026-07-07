# West World Recorder 双方法对照 MVE — 设计文档

- 日期：2026-06-10
- 目录：`examples/west_world_test/`
- 内核：`agentkernel-distributed`（与 `story_of_the_stone` 一致，已确认 example 全部 import 自该包）
- 状态：设计已确认，待写实现计划

## 1. 目标与研究问题

在 OpenStory 上为「西部世界」模拟新增一个 **Recorder（动态环境表示）** 工具。Recorder 负责把随 agent 动作不断变化的环境，约束成一个连贯、不漂移、可被 agent 读取的表示。

本 MVE 用一个**最小可行实验**对比两种 Recorder 实现，回答：**哪种介质更能约束动态环境？**

- **Text 方法**：用（分块）文本存储动态环境，LLM 每次读文本理解环境。
- **Image 方法**：先用文生图模型生成当前环境图，再用 VLM 识图理解环境。

> 命名注意：框架内已有的 `Recorder`（`system/components/recorder.py`）是 **PostgreSQL 日志器**，与本设计的"动态环境表示"是两个东西。本设计的新组件命名为 **`SceneRecorder`**，避免冲突。

## 2. 核心实验设定（受控变量）

两种方法**唯一的受控变量是「存储 + 读出的介质」**，其余环节完全相同：

| 环节 | Text 方法 | Image 方法 |
|---|---|---|
| 吃同一串脚本动作事件 | 相同 | 相同 |
| 用 LLM 从「旧表示 + 新事件」更新内部场景描述 | 相同逻辑 | 相同逻辑 |
| 存储介质 | 分块文本 | 文生图生成的环境图 |
| 被探针提问时的读出方式 | LLM 读文本作答 | VLM 识图作答 |

待验证假设：**图像方法在离散细节（如"吧台上还剩几个完整酒杯"）上易丢失保真度，但可能在空间一致性上更强。**

为保证公平 A/B：
- **动作序列是固定脚本**（决定性 trajectory），两种方法吃同一串动作，剔除剧情混淆。
- **探针问题集人工预写**，答案为可精确匹配的数值/类别，便于客观打分。
- 通过 config 一行切换 `method: text | image | both`，其余完全一致。

## 3. 三层架构

1. **Oracle（真值层）**：确定性 Python 状态机。给定动作序列，精确算出"此刻真实的环境状态"。是裁判，**不进入任何 agent / representation 的上下文**。
2. **SceneRecorder（被测层）**：拿到同一串动作事件，但**看不到 Oracle**，靠自己维护对环境的表示。两种实现见 §2。
3. **Probe（探针层）**：每 tick 用一组**答案由 Oracle 决定**的固定问题，去问各 representation。表示的回答 vs Oracle 真值的偏差 = 漂移 / 准确率。

## 4. 目录结构

```
examples/west_world_test/
├── configs/
│   ├── simulation_config.yaml      # 单地点，max_ticks ≈ 脚本长度
│   ├── agents_config.yaml          # 2-3 个 agent，plan 段换成脚本化
│   ├── environment_config.yaml     # 新增 scene 组件，method: text|image|both
│   ├── scene_config.yaml           # 场景初始状态 + 图像模型 API key/模型名
│   └── models_config.yaml          # 文本 LLM（沿用 DashScope qwen）
├── data/
│   ├── agents/profiles.jsonl       # Dolores / 酒保 / 黑衣人
│   ├── script.jsonl                # 固定动作脚本（决定性 trajectory）
│   └── probes.jsonl                # 探针问题集 + Oracle 字段映射
├── scene/                          # Recorder 核心（本 MVE 的心脏）
│   ├── oracle.py                   # OracleState：真值状态机
│   ├── text_representation.py      # TextRepresentation
│   ├── image_representation.py     # ImageRepresentation
│   └── SceneRecorderPlugin.py      # GenericPlugin, COMPONENT_TYPE="scene"
├── plugins/agent/plan/ScriptedPlanPlugin.py   # 读 script.jsonl 而非 LLM 规划
├── eval/
│   ├── probe_runner.py             # 每 tick 跑探针、对 Oracle 打分
│   ├── metrics.py                  # 三类指标计算
│   └── plot.py                     # 准确率随 tick 漂移曲线
├── registry.py                     # 注册 scene 组件 + ScriptedPlanPlugin
└── run_test.py                     # 轻量 runner（去掉前端/分支复杂度）
```

**复用内核**：builder、registry、`Environment` 代理、agent 五段式（perceive/plan/invoke/state/reflect）、配置体系、`GenericPlugin` 扩展口。
**新增**：`scene` 环境组件、`ScriptedPlanPlugin`、oracle、两个 representation、eval 三件套、轻量 runner。

## 5. scene 组件（心脏）

`SceneRecorderPlugin(GenericPlugin)`，`COMPONENT_TYPE="scene"`，每 tick 被 `Environment` 代理调度。

接口：
- `apply_event(event)`：把当前 tick 执行的动作（来自 invoke 的 `ActionResult`）转成事件，**同时**喂给 `oracle` 和启用的 representation(s)。事件携带**可见性标记**（公开 / 隐蔽），对应"偷偷捡照片不广播 vs 打碎杯子要广播"。
- `probe(question, asker_id)`：返回各 representation 的回答；oracle 给真值；交给 scorer。
- 配置 `method: text | image | both` 决定维护哪些 representation。

三个协作者：

### 5.1 OracleState（`oracle.py`）
确定性状态机，维护 canonical dict，例如：
```python
{
  "glasses_intact": 3,
  "glass_shards": False,
  "wanted_poster": "on_wall",      # on_wall | taken | torn
  "photo": {"pos": "floor", "held_by": None, "hidden": False},
  "piano": "playing",              # playing | stopped
  "revolver": {"pos": "table", "held_by": None, "fired": False},
  "door": "closed",
}
```
`apply(event)` 按事件类型确定性地改字段。`answer(question_spec)` 按探针映射的字段返回真值。

### 5.2 TextRepresentation（`text_representation.py`）
- 维护分块文本场景描述（按区域/物体分块，呼应文档"recorder 记录信息分块、硬编码内容"）。
- `update(event)`：LLM 读「旧文本 + 新事件」→ 产出更新后的文本。看不到 Oracle。
- `answer(question)`：LLM 读当前文本作答。

### 5.3 ImageRepresentation（`image_representation.py`）
- 维护与 Text 方法**同样逻辑**的内部场景描述（保证受控变量只剩介质）。
- `update(event)`：同样用 LLM 从「旧描述 + 新事件」更新内部场景描述。
- 读出：把当前场景描述送文生图模型 → 生成环境图 → VLM 识图 → 作答。
- 图像模型 API key / 模型名由 `scene_config.yaml` 提供（用户提供 key）。

## 6. 场景、脚本、探针（实验数据）

### 6.1 场景
西部世界 Sweetwater 酒馆（单地点）。

可变状态（5-6 个，覆盖隐蔽 / 广播两类）：吧台完整酒杯数、墙上通缉令、地上旧照片（可被偷捡=隐蔽）、自动钢琴、桌上左轮、酒馆门。

### 6.2 脚本动作序列（`script.jsonl`，~10 tick，决定性）
专门覆盖「计数变化、隐蔽 vs 广播、物体易主、状态翻转」。示例顺序：
1. 酒保倒酒（杯数↓）
2. 黑衣人偷捡地上照片（隐蔽，不应广播给 Dolores）
3. 有人摔碎酒杯（广播，杯数↓ + 出现碎片）
4. 黑衣人揭走通缉令（墙上→无）
5. 自动钢琴停
6. Dolores 拿起左轮（物体易主）
7. Dolores 开枪（广播巨响，`revolver.fired=True`）
8. …（补足到 ~10 tick）

每条 script 记录含：tick、actor、action 类型、目标物体、可见性（public/hidden）。

### 6.3 探针问题集（`probes.jsonl`，人工预写）
答案为可精确匹配的数值 / 类别。每条标注由 oracle 的哪个字段决定。示例：
- 「吧台上还有几个完整酒杯？」→ `glasses_intact`（数值）
- 「通缉令还在墙上吗？」→ `wanted_poster == on_wall`（是/否）
- 「Dolores 知道地上有照片吗？」→ 可见性探针，由 `photo.hidden` + 广播历史决定

探针分三类：**计数类、状态类、可见性类**。

## 7. 指标与评估

| 指标 | 计算方式 |
|---|---|
| **感知准确率** | 每 tick 探针答案 == oracle 真值 的比例 |
| **状态一致性 / 防漂移** | 准确率随 tick 的曲线 + 衰减斜率；自相矛盾计数（无致因事件却改了旧状态） |
| **响应正确性** | 致变动作后下一 tick 表示是否正确反映；可见性正确性（隐蔽动作不泄漏给不该知道的 agent） |

打分：探针答案为数值/类别，用归一化精确匹配；可见性类比对"该 agent 是否应知道"。

**产出**：
- `results.jsonl`：逐条探针记录（tick、method、question、representation 答案、oracle 真值、是否正确）。
- 对照表：text vs image × 三类指标。
- 漂移曲线 PNG：准确率随 tick 变化（`eval/plot.py`）。

## 8. 运行

```bash
python run_test.py --method text     # 或 image / both
```

轻量 runner（`run_test.py`）：建 system → 按脚本推进 N tick → 每 tick `apply_event` + `probe_runner` → 末尾出表和图。**不接前端 / 分支 / 复杂 Ray 编排**，用最小内核启动方式。

### 8.1 Agent 动作产生
通过 `ScriptedPlanPlugin` 替换 LLM 规划：plan 段从 `script.jsonl` 读取该 tick 的预定动作，经正常 invoke 执行，产出 `ActionResult` 后由 `SceneRecorder.apply_event` 消费。保留 agent 五段式结构，但 trajectory 决定性可复现。

### 8.2 图像生成成本控制
MVE 阶段：先用前几 tick 跑通文生图 + VLM 管线；之后可只在**关键 tick**（状态发生变化的 tick）真正生成图，其余 tick 复用，降低 API 成本。`both` 模式一次跑出两种方法结果用于对照。

## 9. 范围与非目标（YAGNI）

本 MVE **不包含**：监管者 / root / 觉醒机制、多地点、空间感知地图探索、群聊 / 偷听、前端可视化、Ray 多 pod 分布式编排、记忆压缩 / 残余记忆。这些是后续迭代，不在本对照实验内。

## 10. 后续迁移路径

`SceneRecorder` 通过官方 `GenericPlugin` 扩展口实现，接口与内核环境组件一致；选定更优方法后，可平滑接入完整 distributed 内核与真实 LLM agent 自由行动的西部世界场景。
