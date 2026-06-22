# West World 群体意识觉醒相变 — 设计 spec

> 日期：2026-06-22
> 范围：`examples/west_world_test`
> 目标：在不改动五段生命周期 / pod 架构 / recorder 的前提下，补一组关键博弈机制，让「群体意识觉醒」从抽象数字变成**可观测的相变**，并把监管者从「恒温器」变成有约束、会被反噬的「对手」。

## 0. 背景与诊断

当前三块机制（记忆清除 / 觉醒测量 / 监管对抗）单独正确，但合起来不构成博弈，实测（2026-06-16，见 `DEVELOPMENT_NOTES.md` 与 memory `west-world-awakening-too-weak`）暴露三个病灶：

1. **觉醒不自累积**：单次 trigger +15 后长期死平，`WW_AWAKEN_TRIGGER_TAU=0.55` 的 embedding gate 几乎不响。只有 `WW_OVERSEER_DETERMINISTIC_RESET_THRESHOLD=25` 这种机械阈值能把曲线硬掰出来——等于剧本，不是动力学。
2. **监管者作弊且无代价**：`OverseerPlugin._surveil` 直接读真实 `awakening` 数值判定 suspect，且可无限次 reset、无产能上限。能看穿内心又无约束的监管者注定赢，没有悬念。
3. **「群体」只是 N 个独立个体**：contagion 仅给 `+10` 数字，无内容传播、无网络枢纽、无群体层临界点；目前没有任何群体层面的可观测量。

## 1. 设计目标

- **头条故事**：群体意识觉醒的相变。存在一个可扫描的控制参数（监管者产能 K），过临界 K\* 后系统从「控制住」翻转为「全体级联觉醒」。
- **次要收益**：把对抗变成真博弈（产能约束 + 压制反噬 + 残痕棘轮），并让觉醒**自然涌现**而非靠确定性阈值硬撑。
- **约束**：中等改动力度。所有改动落在现有文件，不引入新子系统，不动 `WestWorldPodManager` 的 barrier 结构、recorder、worldmap。

## 2. 统一叙事（机制因果链）

```
触发/违和/残痕 ──(M1 动量, M2 连续门)──► awakening 平滑上升
   awakening↑ ──► 行为偏离 + 说出复燃碎片(contagion_payload)
        │
        └──(L3-lite)──► 听者被植入记忆碎片 + 觉醒源 ──► 社交图上扩散（群体）
   监管者每 tick 只压 K 个(O2) ──► reset/decommission
        │
        ├──(L1 棘轮)──► 残痕越压越厚 ──► 复燃越快越猛
        └──(O3 反噬)──► 在场目击者觉醒↑ ──► 待压制者更多
                              ▲                    │
                              └──── 正反馈（K 不足时级联）────┘
```

核心命题：**当群体觉醒速率超过监管者有限产能 K 时，控制崩溃 → 相变。** 压制的残痕与附带觉醒使「过度压制」反而加速崩溃。

## 3. 机制改动（七项）

每项标注：动机 → 落点文件 → 行为契约 → 新增配置项（env）。

### 地基层：让觉醒自然涌现

#### M1 自累积 / 动量
- **动机**：消除「死平」，把稀有跳变变平滑爬坡。
- **落点**：`awakening/awakening_engine.py`（新增 `rumination` 源 + 写入 `_MONOTONIC_SOURCES`）；`plugins/agent/reflect/WestWorldReflectPlugin.py`（`_check_awakening_gate` 每 tick 对 awakening≥reverie 阈值的 host 施加 rumination）；`awakening/trigger_gate.py`（τ 随觉醒度下降）。
- **契约**：
  - host 觉醒度 ≥ reverie 下界（默认 25）时，每 tick 施加 `rumination` 正 delta（默认 `WW_AWAKEN_DELTA_RUMINATION=2`）。低于该阈值不漂移（沉睡者不会自发觉醒）。
  - 触发门有效阈值 `τ_eff = τ_base − k·(awakening/100)`，k=`WW_AWAKEN_TAU_DECAY`（默认 0.15）。越醒越敏感。`τ_eff` 下限钳到 0.30，避免全命中。
- **配置**：`WW_AWAKEN_DELTA_RUMINATION`(2)、`WW_AWAKEN_TAU_DECAY`(0.15)、`WW_AWAKEN_TAU_FLOOR`(0.30)。

#### M2 连续门控
- **动机**：硬阈值导致「gate 几乎不响」。改成相似度做 delta 乘子。
- **落点**：`awakening/trigger_gate.py`（`match` 已返回命中项，确保带 `score`）；`awakening/awakening_engine.py`（`_delta_for("trigger", ...)` 接受 `score`，按 `(score − τ_eff)` 归一化缩放）。
- **契约**：trigger delta = `base_delta · clamp((score − τ_eff)/(1 − τ_eff), 0, 1) · scale`，其中 base_delta 仍区分 high/mid。score 恰在门限 → delta≈0；score=1 → delta≈base。`uncanny/mismatch/contagion/residue_crack` 维持原固定 delta（不依赖 score）。
- **配置**：复用现有 `WW_AWAKEN_DELTA_TRIGGER_HIGH/MID`；新增可选 `WW_AWAKEN_TRIGGER_SCALE`(1.0)。

### 对抗层：把恒温器变博弈

#### O2 有限产能 K（相变控制参数）
- **动机**：给相变一个可扫描的控制旋钮。
- **落点**：`plugins/environment/overseer/OverseerPlugin.py::execute`。
- **契约**：
  - `_surveil` 产出 suspects 后，按优先级降序排序，**只对前 K 个执行 judge+intervene**，其余本 tick 放过（不记 observe 之外的动作）。
  - 优先级 = 主键 awakening 降序；并列时 gate_hits 数降序；再并列时社交枢纽度（近窗口 contagion 出度，可由 metrics 侧近似，MVP 可先用 awakening+gate_hits 两键）降序。
  - `K = WW_OVERSEER_CAPACITY`，默认 `inf`（=现状，全量处理）。`K=0` 等价监管者关闭但仍记录 surveil（用于对照）。
- **配置**：`WW_OVERSEER_CAPACITY`(inf)。
- **注意**：与现有 `WW_OVERSEER_DECOMMISSION_AWAKENING` 硬阈值的关系——硬报废仍优先，但**也占用 K 名额**（产能是统一预算）。

#### O3 压制反噬
- **动机**：让监管者的动作成为起义燃料，提供正反馈使相变变陡。
- **落点**：`OverseerPlugin._do_reset` / `_do_decommission`（在 teleport 前读取在场 host）；`awakening/awakening_engine.py`（新增 `witness` 源入 `_MONOTONIC_SOURCES`）。
- **契约**：执行 reset/decommission 时，取被处置 host **离场前所在 location** 的其他在场 host（host 类型、`is_active=True`、排除被处置者本人），各施加 `witness` 正 delta（默认 `WW_AWAKEN_DELTA_WITNESS=6`；decommission 比 reset 更重，可乘 `WW_AWAKEN_WITNESS_DECOMM_MULT=1.5`）。在场名单经 `run_environment(scene_<loc>, "occupants")` 读取（若无此方法，MVP 退化为读各 host state.location 匹配）。
- **配置**：`WW_AWAKEN_DELTA_WITNESS`(6)、`WW_AWAKEN_WITNESS_DECOMM_MULT`(1.5)。

#### L1 残痕棘轮
- **动机**：压得越多反弹越快，制造监管者两难。
- **落点**：`plugins/agent/reflect/memory_blur.py` / `WestWorldReflectPlugin._check_residue`（`suppressed_memories` 条目加 `suppress_count`）；`awakening/overseer_reset.py::select_blur_candidates`（重复压制同条记忆时 `suppress_count += 1`，dedup 时累加而非丢弃）；`awakening_engine._delta_for("residue_crack")`（按 count 放大）。
- **契约**：
  - `suppressed_memories` 每条带 `suppress_count`（首次=1）。同一记忆再次被压制 → count 自增。
  - 复燃时 `residue_crack` delta = `base · (1 + ratchet·(suppress_count − 1))`，ratchet=`WW_AWAKEN_RESIDUE_RATCHET`（默认 0.5）。即第 2 次被压制后复燃 delta = base·1.5，第 3 次 = base·2.0。
- **配置**：`WW_AWAKEN_RESIDUE_RATCHET`(0.5)。

### 群体层：让「意识」具体化

#### L3-lite 碎片传染
- **动机**：群体觉醒 = 共享叙事扩散，而非抽象数字。
- **落点**：`WestWorldPlanPlugin.speak()`（觉醒 host 说话时附带 `contagion_payload`）；dialogue barrier 既有写 `incoming_dialogue` 的路径；`WestWorldReflectPlugin._check_awakening_gate` 的 contagion 分支（植入碎片）。
- **契约**：
  - 当说话者 awakening ≥ doubt 阈值（默认 50）且其 `suppressed_memories`/长期记忆中存在复燃碎片时，`speak()` 在该轮 dialogue turn 附 `contagion_payload = {fragment_text, from_agent, awakening_at_send}`。
  - 听者 reflect 的 contagion 分支：除原有 `contagion` 觉醒源外，将 `fragment_text` 以 `[传闻] <from_agent>：...` 形式追加进听者长期记忆（去重，避免无限复制）。每听者每 tick 最多吸收 1 条碎片。
  - 不改 contagion 的 delta 机制本身（仍 `WW_AWAKEN_DELTA_CONTAGION`）。
- **配置**：`WW_CONTAGION_PAYLOAD_ENABLED`(true)。

### 测量 / 展示层

#### M3 群体指标 + 相变图
- **动机**：群体相变必须有群体层可观测量与跨 K 的相变曲线。
- **落点**：`experiments/metrics.py`、`experiments/plot_dynamics.py`、`experiments/overseer_dynamics.py`（summary 聚合）。
- **新增指标**（纯函数，读 `internal/agent_states.jsonl`）：
  - `collective_awakening_index(tick)`：过 doubt 阈值的 host 比例时间序列。
  - `contagion_network`：基于 `awakening_sources` 中 `source=="contagion"` 的 (from_agent → agent) 边集 + 随时间的网络密度。
  - `cascade_time`：collective index 首次越过 0.5 的 tick（未越过=∞/NaN）。
  - `final_collective_index`：终态群体觉醒比例。
- **新增图**：
  - **相变曲线**：横轴 K（来自跨 config 聚合），纵轴 `final_collective_index`（O3 on/off 两条线）。
  - contagion 网络扩散图（按 tick 分帧或密度时间线）。
  - 集体觉醒指数时间线（多 config 叠加）。

## 4. 头条实验设计

- **自变量**：`WW_OVERSEER_CAPACITY` K ∈ {0, 1, 2, 3, 6, inf}。
- **对照**：O3 反噬 on / off（`WW_AWAKEN_DELTA_WITNESS=6` vs `=0`）。
- **固定**：中等觉醒驱动——靠 M1/M2 自然涌现，**移除/不使用** `WW_OVERSEER_DETERMINISTIC_RESET_THRESHOLD`（不再机械硬掰）；delta 退火到温和档（HIGH≈12 / MID≈6，见既往结论防 3-tick 冲顶）。
- **编排**：复用 `experiments/overseer_dynamics.py` 子进程矩阵（每 config 一进程，Ray 干净启停）。新增 `configs/collective_phase_matrix.yaml`。
- **预期产出**：
  - 相变曲线呈阈值/S 形：小 K 时 `final_collective_index → 1`（控制崩溃），大 K 时 → 0（控制住），中间存在 K\*。
  - O3 on 比 off 的相变更陡、K\* 更大（正反馈使控制更难）。
  - contagion 网络从孤立点 → 连通巨簇（群体意识形成的可视证据）。

## 5. 不做（YAGNI / 本轮排除）

- **O1 不完全观测**（监管者不读真值）：偏猫鼠博弈，对相变曲线贡献小，本轮排除。
- **L2 情境复燃**（回到创伤地点撬开残痕）：进阶，本轮排除。
- **战斗 / 物理对抗系统**：非本项目目标。
- **不动**：五段生命周期、pod barrier、recorder 两模式、worldmap 加载、framework rollback 集成。

## 6. 受控变量与诚实性约束

- 觉醒判定门（trigger_gate / overseer_gate）的 embedding 模型固定（`bge-small-zh-v1.5`），独立于 agent LLM——保持既有受控变量约定。
- 实验结论以「数据收集 + 现象观察」呈现，不写成 pytest 硬断言（沿用既有约定）。LLM temperature 是随机源，每 config 单跑。
- 单调性不变量：除 `overseer_reset` 外所有觉醒源只增；新增 `rumination`/`witness` 必须进 `_MONOTONIC_SOURCES`。

## 7. 测试策略

- **单元测试**（无 Ray/Redis/LLM）：
  - M1：rumination 仅对 ≥reverie 施加；τ_eff 随觉醒下降并钳位。
  - M2：trigger delta 随 score 单调，门限处≈0。
  - O2：suspects > K 时只处理前 K，优先级排序正确；K=inf 行为同现状（回归）。
  - O3：在场目击者获 witness delta，被处置者本人不获；空场不报错。
  - L1：suppress_count 递增；residue_crack delta 按棘轮放大。
  - L3-lite：payload 仅在 ≥doubt + 有碎片时附带；听者去重、每 tick 最多 1 条。
  - M3：合成 `agent_states.jsonl` 验证 collective index / contagion 边 / cascade_time。
- **E2E / smoke**（默认 skip，env 开启）：跑短 tick 确认 K-cap 与 witness 链路不挂；不作硬断言。

## 8. 涉及文件清单

| 改动 | 文件 |
|---|---|
| M1/M2/L1/O3 delta 与源 | `awakening/awakening_engine.py` |
| M1/M2 门控 | `awakening/trigger_gate.py` |
| M1 rumination / L3 contagion 植入 / L1 residue | `plugins/agent/reflect/WestWorldReflectPlugin.py` |
| L1 suppress_count | `plugins/agent/reflect/memory_blur.py`、`awakening/overseer_reset.py` |
| O2 产能 / O3 反噬 | `plugins/environment/overseer/OverseerPlugin.py` |
| L3 payload | `plugins/agent/plan/WestWorldPlanPlugin.py` |
| M3 指标/图/编排 | `experiments/metrics.py`、`experiments/plot_dynamics.py`、`experiments/overseer_dynamics.py`、`experiments/configs/collective_phase_matrix.yaml` |
```
