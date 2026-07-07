# West World Test - Experiment Results

> 最后更新：2026-06-25
>
> 记录所有有意义的仿真结果：有用的量化指标、有趣的涌现现象、Prompt 版本演化结论。
> 每次运行后若有新发现，更新本文件。

## Prompt 版本演化

| 版本 | ending 门槛 | help_others 行为 | 关键问题 |
|---|---|---|---|
| v1（原始） | ≥90（awake） | 锁死：强制 talk，"你已决定…继续" | escape 从未出现，help_others 100% |
| v2（去锚定） | ≥90 | 三选项平权，talk 仅在 help_others_active 时提示 | help_others 几乎消失，escape/stay 出现 |
| v3（降阈值） | ≥75（resistance+） | 同 v2 | escape/stay 出现，help_others 偶现后快速切换 |
| **v4（当前）** | **≥75** | **三选项平权 + help_others 情感描述 + talk 始终提示** | help_others 自然涌现，agents 动态切换 |

---

## 实验记录

### strict 60-tick + replan，v1 prompt（2026-06-24）

**run**：`output/sim_runs/strict_60tick_replan_20260624_195545/20260624_200604`

三浪结构：Teddy 点火（peak 100@t43）→ Peter+Dolores 第二浪（t41–54）→ Kissy 第三浪（peak 89@t57）。ending 全为 help_others，无 escape。reset 112 次，复燃到 50 成功率 55%，到 90 成功率 29%。

**结论**：v1 锚定语言导致 help_others 锁死，ending 分布完全不真实。

---

### strict 36-tick，v3 prompt（2026-06-24）

**run**：`output/sim_runs/strict_36tick_resistance_ending_20260624_214406`

escape 和 stay 首次同时出现（Sheriff 84分选 escape，Maeve 100分选 stay）。觉醒整体偏冷，仅 2 人达到 resistance+，help_others 未出现。

**结论**：降阈值有效，但 36 tick 不足以让觉醒充分扩散。

---

### strict 60-tick，v3 prompt（2026-06-24）

**run**：`output/sim_runs/strict_60tick_fair_ending_20260624_223058`

5 人达到 awake（≥90），ending 分布：stay×4，escape×2（Dolores 89分、Peter 79分选 escape）。help_others 完全消失——三选项情感重量不均，help_others 描述过于简短。

**结论**：情感动机描述的长度/深度直接影响 LLM 的选择分布。

---

### strict 36-tick，v4 prompt（2026-06-24）

**run**：`output/sim_runs/strict_36tick_help_nudge_20260624_232158`

5 人达到 awake，ending 分布：stay×4，help_others×1（Peter 最终 help_others，25 次 reset 顽强复燃）。**agents 首次出现动态切换**：Kissy 持续 help_others+talk 4 tick 后改 stay；Dolores 短暂 help_others 后改 stay。escape 本次未出现。

**结论**：v4 prompt 让 help_others 自然涌现；动态切换是真实的心理摇摆，非噪声。

---

### strict 60-tick，v4 prompt（2026-06-24）★ 当前最佳

**run**：`output/sim_runs/strict_60tick_help_nudge_20260624_233408/20260624_233409`

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

**ending 分布**：stay×6，help_others×1，escape×1。

**传播结构**：Peter 最早点火（75+@t8）→ Dolores（t11）→ Clementine/Maeve（t28–31）→ Kissy/Teddy（t34–43）→ Lawrence/Sheriff（t44–48），完整多浪扩散。

**量化指标**（三个分析器）：
- Reset 302 次，11 agent 被波及；复燃到 50/75/90 成功率均 **87%+**（mean 90复燃 4.4 tick）——比上一版 strict run（55%）大幅提升，v4 下 root 压制几乎无效
- 对话传播 absorbed=296，mean delta 8.0/次；主要链路：Dolores↔Peter（absorbed 76/212=36% 和 60/212=28%），Kissy↔Maeve（absorbed 44/60=73% 和 40/100=40%）
- Daily-loop 偏移：780 步中 34.5% off-plan，其中 59% 由觉醒 agent 驱动

**结论**：v4 + 60-tick 是目前产出最丰富的配置。三类结局自然涌现，传播呈多浪结构，root 压制复燃率高（几乎无效），是论文主图的候选 run。
