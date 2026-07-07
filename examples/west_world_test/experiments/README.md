# 论文级长 tick 仿真实验（overseer 动力学）

观测「**自然觉醒 → overseer 压制 → 残痕复燃**」的完整动力学曲线，产出可统计、可画图的数据。

> 这是**数据收集 / 现象观察**工具，不是 pytest 硬断言。机制本体（觉醒/监管者/叙事）已完成，
> 本模块只做批量编排 + 指标提取，不改任何机制代码。

## 模块

| 文件 | 职责 |
|---|---|
| `metrics.py` | 纯函数指标提取层（解析 run 输出，无 Ray/Redis/LLM 依赖，有单测） |
| `overseer_dynamics.py` | 编排层：参数矩阵 × subprocess 跑 `run_simulation` + 聚合落盘 |
| `configs/default_matrix.yaml` | 小默认矩阵（overseer on/off），脚本正确性验证用 |
| `configs/full_matrix.yaml` | 论文级完整矩阵示例（扫监管者干预强度），用 `--matrix` 指定 |

## 运行

需 Redis 在线 + 真实 LLM（`configs/models_config.yaml` 可用）。

```bash
# 默认小矩阵，30 tick（先验证脚本能跑通）
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
  python -m examples.west_world_test.experiments.overseer_dynamics --ticks 30

# 干跑：只打印将执行的 config，不真跑（不需 Redis/LLM）
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
  python -m examples.west_world_test.experiments.overseer_dynamics --dry-run

# 论文级完整矩阵，长 tick
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
  python -m examples.west_world_test.experiments.overseer_dynamics \
    --matrix examples/west_world_test/experiments/configs/full_matrix.yaml \
    --ticks 80 --out /tmp/ww-exp

# 只跑矩阵里某几个 config
... overseer_dynamics --select baseline_no_overseer,overseer_default
```

### CLI 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--matrix` | `configs/default_matrix.yaml` | 参数矩阵 yaml |
| `--ticks` | `30` | 每个 config 的 tick 数（论文级建议 50–100+） |
| `--out` | `output/sim_runs` | 实验输出根目录 |
| `--recorder-mode` | `structured` | `WW_RECORDER_MODE` |
| `--select` | 全跑 | 逗号分隔的 config 名子集 |
| `--dry-run` | off | 只打印计划，不真跑 |

每个 config 独立子进程跑（Ray 干净启停），单 run 的完整日志在 `runs/<config>/`
（即 `SimulationLogArchive` 的标准输出）。

## 输出结构

```
output/sim_runs/<exp_id>/
├── manifest.json          # 实验元数据 + 每个 run 的执行情况（退出码/耗时）
├── summary.json           # 各 config 的聚合 totals（reset/decommission/移动数…）
├── records.jsonl          # tidy 长格式：每 (config, agent, tick) 一行 → notebook 直接读
├── events.jsonl           # 监管者干预事件：每条 reset/decommission
├── metrics/<config>.json  # 单 config 完整指标（觉醒峰值/终值、reset 间隔、来源计数…）
└── runs/<config>/         # 该 config 的原始仿真日志（含 internal/agent_states.jsonl）
```

### `records.jsonl` 字段（画图主数据）

`config_name, agent_id, tick, awakening, stage, location, is_active, suppressed_len`

### `events.jsonl` 字段

`config_name, agent_id, tick, action(reset|decommission), reason, awakening_after?`

## 可视化（`plot_dynamics.py`）

读实验目录的 `records.jsonl` / `events.jsonl`，生成图到 `<exp_dir>/figures/`：

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
  python -m examples.west_world_test.experiments.plot_dynamics <exp_dir>
# 不传 exp_dir 则取 output/sim_runs 下最新一次
```

产出（每个 config 一套）：

| 图 | 内容 |
|---|---|
| `awakening_trajectories_<config>.png` | 逐 host 觉醒度时间序列 + reset(▽)/decommission(✕) 标记 + 阶段阈值线（**主图**） |
| `awakening_heatmap_<config>.png` | agent × tick 觉醒度热力图 |
| `intervention_timeline.png` | 监管者干预事件时间线 |
| `reset_intervals.png` | 复燃周期（相邻两次 reset 间隔）分布 |

> 中文标签自动选系统已注册的 CJK 字体（PingFang/Songti/STHeiti…）。

**对照解读**（2026-06-16 实测）：默认矩阵 100 tick 的 `overseer_off` 主图——只有 2 host 动过、maeve 跳到 45 后平躺 60 tick、零干预；`overseer_stress` 30 tick 主图——多 host 在 25 阈值附近震荡、规范链 reset×3→decommission×1。一眼看出「默认参数死平 vs 放大驱动后动力学点燃」。

## 指标提取（`metrics.py`）

所有函数接受「已解析的 state 行列表」或 run 目录，核心信号来自
`internal/agent_states.jsonl`（逐 agent 逐 tick 的完整 state）：

- `awakening_timeseries` — 觉醒度 + stage 时间序列
- `suppressed_timeseries` — suppressed_memories 长度（随 reset 单调增）
- `intervention_events` / `reset_intervals` — 监管者干预事件与复燃间隔
- `awakening_source_counts` / `contagion_events` — 觉醒来源分布与传染边
- `location_flow` — 地点轨迹与移动次数
- `summarize_run` / `tidy_records` — 单 run 汇总 / tidy 长格式
