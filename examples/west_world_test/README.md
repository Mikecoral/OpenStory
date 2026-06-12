# West World Recorder MVE

This experiment compares two independent dynamic-environment recorders against
the same fixed event sequence and Oracle truth.

## Evaluation Protocol

- Every event has a structured action plus an explicit natural-language
  `description`. Both recorders receive the same event semantics.
- Every event explicitly declares `affected_probe_ids`; relevance is not guessed
  from the target name.
- `pour_whiskey` increases `glasses_filled` and does not consume or destroy an
  intact glass.
- The initial state is evaluated at tick 0 before the first image edit.
- Every answer is classified as:
  - `initial`: initial representation fidelity.
  - `affected`: whether the current event was written correctly.
  - `persistence`: whether a previously changed fact survived unrelated edits.
  - `unaffected_baseline`: a fact that has not yet been changed by the script.
- Probes are split into:
  - `visual_snapshot`: directly answerable from one clear current image.
  - `temporal_nonvisual`: sound or historical facts not reliably encoded by a
    static image.
  - `hidden_knowledge`: actor knowledge and witness/access-control facts.
- The primary comparison is the `visual_snapshot` initial, affected, and
  persistence matrix. Other groups are diagnostic limitations, not pure visual
  capability scores.

## Recorder Methods

### Text Recorder

```text
previous text state + event
  -> qwen3.5-flash
  -> next text state
  -> qwen3.5-flash answers probes from text
```

### Image Recorder

```text
initial scene description
  -> Image 2 images.generate
  -> initial world-state image

previous world-state image + event
  -> Image 2 images.edit
  -> next world-state image
  -> qwen3.5-flash answers probes from the current image
```

The Image Recorder does not keep `scene_text` or use a text LLM to update its
state. Its only persistent dynamic state is the current image handle.

This comparison intentionally changes both the storage medium and the update
mechanism. Errors can therefore come from image generation/editing, accumulated
visual drift, or visual question answering.

## Interpretation

The experiment changes both storage medium and update mechanism. It can measure
whether image state is created, updated, and preserved, but it cannot attribute
every error to one component without further ablations.

An image can represent visible current physical state. It cannot naturally
encode facts such as "the piano is audible", "the gun fired earlier", or
"Dolores did not witness a hidden event." These are reported separately. A
production Recorder still needs structured temporal and access-control state.

## Model Configuration

The local credential file is ignored by Git:

```bash
cp examples/west_world_test/configs/models_config.example.yaml \
   examples/west_world_test/configs/models_config.yaml
```

The configured Image 2 endpoint must provide OpenAI-compatible `images.generate`
and `images.edit` methods. If its API differs, adapt
`adapters/model_clients.py` without changing the experiment core.

## Run

Phase A, without Ray or Redis:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.core.compare --method both
```

Phase B, through the distributed kernel:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.run_test
```

Plot results:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.plot
```

Run a fully archived comparison:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.run_archived_comparison
```

Each archived run contains every model request and response in
`model_traces/all_calls.jsonl`, every image state, raw scored results,
event-by-event statistics, a global report, provenance, and checksums.

Run a two-event pilot before the full comparison:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.run_archived_comparison --validate-only

PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.run_archived_comparison --max-ticks 2
```

`--validate-only` checks the protocol and local model config and prints the
expected call budget without creating a run or calling an API. The archived
runner writes `results.jsonl` incrementally, rejects malformed protocol data
before the first API call, and refuses to append into a non-empty run directory.

## Report Metrics

- `initial_accuracy`: all tick-0 probes.
- `affected_accuracy`: probes explicitly changed by the current event.
- `persistence_accuracy`: changed probes queried after later unrelated events.
- `final_state_accuracy`: all probes at the final executed tick.
- `group_metrics.json`: aggregate score by semantic group.
- `role_metrics.json`: aggregate score by evaluation role.
- `group_role_matrix.json`: cross-matrix used for the primary visual comparison.

## 正式仿真（M0–M3）

### 前置条件

- Redis（`redis-server`，默认 `localhost:6379`）
- Python 3.11，依赖与 OpenStory 主项目相同
- `examples/west_world_test/configs_sim/models_config.yaml`（LLM API key 配置）

### 运行

```bash
# 仓库根目录
export PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed

# 运行正式仿真（默认 40 tick，约 1-2 小时）
python -m examples.west_world_test.run_simulation

# 快速调试（只跑 5 tick）
WW_MAX_TICKS=5 python -m examples.west_world_test.run_simulation
```

### MVE 对照实验（独立）

```bash
# Phase A：纯 Python 核心（无需 Ray/Redis）
PYTHONPATH=packages/agentkernel-distributed:. \
  python -m examples.west_world_test.core.compare --method both

# Phase B：完整内核（需 Redis）
PYTHONPATH=packages/agentkernel-distributed:. \
  python -m examples.west_world_test.run_test
```

### 项目结构

| 目录/文件 | 用途 |
|---|---|
| `data/map/locations.yaml` | 地图真值：31 个地点，12 个激活 |
| `worldmap/` | 地图加载、校验、邻接查询 |
| `recorder/` | LocationRecorder：每地点状态分块 + LLM 裁决 |
| `plugins/environment/scene/` | LocationRecorderPlugin：内核接入壳 |
| `plugins/agent/` | perceive/plan/invoke 插件 |
| `configs_sim/` | 正式仿真配置（6 人阵容，12 激活地点）|
| `registry_sim.py` | 正式仿真注册表 |
| `run_simulation.py` | 正式仿真入口 |
| `configs/` | MVE 对照实验配置 |
| `registry.py` | MVE 对照实验注册表 |
| `run_test.py` | MVE Phase B 入口 |
| `core/` | MVE Phase A 纯 Python 核心，TDD，不依赖 Ray/Redis |
