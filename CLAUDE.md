# OpenStory（万象谱）— 项目导览

> 本文件是给 AI 助手快速了解本项目的入口。在 OpenStory 目录下工作时会被自动加载，无需用户手动指认。
> 维护约定：架构/机制有变动时更新本文件；细节实现以源码为准，本文件只给"地图"和"指针"。

## 1. 这是什么

OpenStory 是基于 LLM 和 **Agent-Kernel** 的**多智能体推演/模拟框架**。用多智能体在仿真地图上模拟人物的日常行为、社交、剧情推演。第一个官方故事是 `examples/story_of_the_stone`（红楼梦大观园，1:1 地图 + Web 前端）。

- 语言：Python（推荐 3.11；README 写 3.10+）。
- 运行时依赖：**Ray**（分布式 actor）+ **Redis**（默认数据总线/缓存，`localhost:6379`）+ 可选 **PostgreSQL**（持久化 Recorder）。
- 前端：纯静态 JS（`examples/*/frontend/`），由内置 API Server（默认 `:8000`）挂载。

## 2. 内核：用哪个包

- **实际使用的内核 = `packages/agentkernel-distributed`**（`agentkernel_distributed`）。所有 example 100% import 自它。
- `packages/agentkernel-standalone` 是几乎同构的镜像包（疑似去 Ray 单机版），**当前没有任何 example 使用**。除非明确要做单机轻量版，否则忽略它。

## 3. 目录地图

```
OpenStory/
├── packages/agentkernel-distributed/agentkernel_distributed/   # 内核
│   ├── mas/
│   │   ├── builder.py            # Builder.init() → (pod_manager, system)；装配一切
│   │   ├── system/              # System 级组件：messager / recorder / timer
│   │   ├── environment/         # Environment 代理 + 组件（relation/space/generic）
│   │   ├── agent/              # Agent 容器 + 五段式组件 + 插件基类
│   │   ├── action/             # 动作组件（communication/move/otheractions）
│   │   ├── controller/         # Controller（推进/编排）
│   │   └── pod/               # MasPod + PodManager（Ray actor，承载 agents+environment）
│   ├── toolkit/                # models(LLM provider/router)、storages(Redis等)、logger、generation(PCG)
│   └── types/                  # schemas(message/action/agent) + configs(pydantic 配置模型)
├── examples/
│   ├── story_of_the_stone/     # 红楼梦（主参考实现）
│   └── west_world_test/        # 西部世界 Recorder 对照实验（见 §7）
├── docs/superpowers/specs/     # 设计 spec
├── docs/superpowers/plans/     # 实现计划
└── README.md / tutorial/       # 上手教程
```

## 4. 核心抽象（组件 + 插件 + 注册表 + YAML）

四类"组件域"，每类是「**Component（壳/接口）+ Plugin（具体实现）**」的两层结构：

| 域 | 组件 | 典型插件（sots） | 职责 |
|---|---|---|---|
| **Agent** | profile/perceive/plan/invoke/state/reflect | Basic*Plugin | 单 agent 的感知→规划→执行→状态→反思生命周期 |
| **Action** | communication/move/otheractions | Basic*Plugin | agent 可执行的动作族 |
| **Environment** | relation/space/**generic** | Basic*Plugin | 世界态：关系、空间、**自定义类型** |
| **System** | messager/recorder/timer | 内核自带 | 全局：消息总线、持久化、时钟 |

机制三件套：
1. **Plugin 基类**：`mas/agent/base/plugin_base.py`、`mas/environment/base/plugin_base.py`。每个 plugin 实现 `init()` / `execute(current_tick)` 等钩子。
2. **registry.py**（每个 example 一个）：把"名字 → 类"汇总成 `RESOURCES_MAPS`（agent_components/agent_plugins/environment_*/system_*/models/adapters/controller/pod_manager）。
3. **YAML 配置**（`examples/*/configs/`）：`simulation_config.yaml` 是入口，引用 environment/actions/agents/system/db/models 各 yaml。`agents_config.yaml` 用 `component_order` 定义每 tick 组件执行顺序，并按名字挂插件。

> **扩展自定义环境类型不需要改内核**：用 `mas/environment/components/generic.py` 的 `get_or_create_component_class("xxx")` 动态造组件类，插件继承 `GenericPlugin` 并设 `COMPONENT_TYPE="xxx"`。

## 5. 运行时与启动流程

1. `python -m examples.<name>.run_simulation`（sots）/ `run_test.py`（west_world_test）。
2. `ray.init(...)` → `Builder(project_path, RESOURCES_MAPS)` → `await builder.init()`：
   - 读 YAML（`load_config`）、把数据文件注入各组件配置（`_load_data_into_config`）。
   - `_init_pod_manager`：用模板 + 数据为每个 agent 生成完整配置，创建 **MasPod**（Ray actor，每 pod 装若干 agent + 一份 environment）。
   - `_init_system`：建 messager/timer/(recorder)。
   - 返回 `(pod_manager, system)`。
3. 主循环按 tick 推进（sots 的 `run_simulation.py` 里还接了前端信号、分支/回溯 `make_snapshot`/`rollback_to_tick`）。
4. **Agent 每 tick**：`Agent.run(tick)` 按 `_component_order`（默认 `perceive→plan→invoke→state→reflect`）依次跑组件。

**易踩点 / 重要事实：**
- `Builder.init()` 返回 `(pod_manager, system)`；**`Environment` 在 pod 内部**，不是 builder 的直接属性。要调环境组件方法走 `Environment.run(component_name, method_name, *args)`（`mas/environment/environment.py` 已确认），但拿到 environment 句柄需经 pod/pod_manager。
- `PodManager` 关键方法：`step_agent` / `run_agent_method` / `add_agent` / `remove_agent` / `make_snapshot` / `rollback_to_tick`（支持动态增删 agent 与时间回溯/分支）。
- 跑起来需要 Redis 在线；Postgres 仅在启用 `recorder` 系统组件时需要。
- `PYTHONPATH` 要包含 `packages/agentkernel-distributed`。

## 6. ⚠️ "Recorder" 有两个不同含义（极易混淆）

- **内核 `Recorder`**（`mas/system/components/recorder.py`）：纯 **PostgreSQL 日志器**，把 tick/action/message 落库。System 级组件。
- **西部世界设计里的 "Recorder"**：一个**新的"动态环境表示"概念**（被动查询、分块、由 agent 决定读哪些 context），与上面的日志器无关。在 west_world_test 中实现为 **`SceneRecorder`**（`scene` 环境组件）以避免命名冲突。

## 7. 当前在做的工作：west_world_test（西部世界 Recorder 对照实验）

### MVE 与正式仿真两条线

项目包含两条独立的验证线路：

1. **MVE 对照实验**（Phase A & B）
   - 目标：对比两种动态环境表示——**文本存储+LLM 读** vs **文生图+VLM 识图**——哪种更能约束动态环境（防漂移/感知准确率/响应正确性）。
   - 设计 spec：`docs/superpowers/specs/2026-06-10-west-world-recorder-mve-design.md`
   - 实现计划：`docs/superpowers/plans/2026-06-10-west-world-recorder-mve.md`
   - 关键设计：唯一受控变量=「读出介质」（两法共用 LLM 更新逻辑）；固定动作脚本保证 trajectory 决定性；Oracle 真值状态机做裁判；人工预写探针集打分。
   - 结构：Phase A（`core/` 纯 Python 实验核心，TDD，无需 Ray/Redis 即可出对照结果）+ Phase B（`run_test.py` 接入完整内核）。
   - 入口：`python -m examples.west_world_test.run_test`、`python -m examples.west_world_test.core.compare`

2. **正式仿真**（M0–M3，完成）
   - 6 人团队在 12 个激活地点的多 tick 智能推演；Recorder 全程运行；持久化至 Redis/PostgreSQL。
   - 入口：`python -m examples.west_world_test.run_simulation`（需 Redis）；支持 `WW_MAX_TICKS` 覆盖 tick 数。
   - 配置集：`configs_sim/` + 注册表 `registry_sim.py`（与 MVE 的 `configs/` + `registry.py` 分离，互不干扰）。
   - **关键模块指针**：
     - 地图真值：`examples/west_world_test/data/map/locations.yaml` + `worldmap/loader.py`（31 地点，12 激活）
     - Recorder：`examples/west_world_test/recorder/` （`LocationRecorder`、`prompts`、`factory`）
     - 环境插件：`examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py`
     - Agent 插件：`plugins/agent/perceive/WestWorldPerceivePlugin.py`、`plugins/agent/plan/WestWorldPlanPlugin.py`、`plugins/agent/invoke/WestWorldInvokePlugin.py`、`plugins/agent/reflect/WestWorldReflectPlugin.py`
     - 生命周期为 5 段 `perceive→plan→invoke→state→reflect`。reflect 是 west_world 原生实现（**不复用 sots 的 BasicReflectPlugin**——后者绑死在每日 hourly-plan/LongTask 模型上）：每 tick 由 state 组装短期记忆，每 `WW_REFLECT_INTERVAL`（默认 6）tick 用 LLM 总结进长期记忆并清空。
     - 地图加载统一走 `worldmap/loader.py` 的 `get_world_map()`（lru_cache 单例）+ `default_map_path()`，全进程只 load 一次；勿在插件里各自 `load_world_map(...)`。
     - ⚠️ 动作组件 `move/communication/otheractions` 在 registry/actions_config 里注册了但**两个 example（含 sots）都不调用**——移动逻辑内联在 invoke 的 `apply_move`。这是框架既有模式，非缺陷。
   - 运行命令示例：`WW_MAX_TICKS=20 PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed python -m examples.west_world_test.run_simulation`

## 8. west_world_test 工作流约定

处理 `examples/west_world_test/` 时按以下节奏：

1. **开工前必读** `examples/west_world_test/DEVELOPMENT_NOTES.md`。
2. 根据其中的「已知问题 / 下一步」确认当前任务。
3. **每完成一个任务，立即回写 `DEVELOPMENT_NOTES.md`**：更新机制状态、已知问题、下一步。
4. **DEVELOPMENT_NOTES.md 只写技术实现**：机制、配置、工具、文件指针。删除过时描述，不要写流水账。
5. **实验结果写 `RESULTS.md`**：每次运行有新发现时，追加一条记录（run 路径、关键指标、结论）。也在这里维护 Prompt 演化历史。两个文件职责不同，都需要保持更新。

## 9. 想深入某块时，直接读这些源码

- 启动/装配：`mas/builder.py`
- 环境组件机制与自定义扩展：`mas/environment/environment.py`、`mas/environment/components/generic.py`、`mas/environment/base/plugin_base.py`
- Agent 生命周期：`mas/agent/agent.py`、`mas/agent/base/plugin_base.py`
- 主参考实现（含 LLM prompt 怎么拼）：`examples/story_of_the_stone/`（`registry.py`、`configs/`、`plugins/agent/plan|invoke|reflect/*.py`）
- 配置数据模型：`types/configs/*.py`；消息/动作 schema：`types/schemas/*.py`
- 西部世界整体构想（含监管者/root/觉醒等后续设计）：`../西部世界开发计划 *.md`、`docs/westworld_design_brainstorm.md`
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenStory is a multi-agent deduction and simulation framework built on LLMs. The core engine is **Agent-Kernel**, which orchestrates LLM-powered agents through a tick-based simulation loop. The primary showcase simulates *Dream of the Red Chamber* with autonomous character agents interacting in a pixel-art "Grand View Garden" map.

## Setup and Running

Python >= 3.11 required. Redis must be running on localhost:6379.

```bash
# Install (pick one):
pip install -e "packages/agentkernel-distributed[all]"   # distributed (Ray)
pip install -e "packages/agentkernel-standalone[all]"     # standalone (no Ray)

# Run main simulation:
python -m examples.story_of_the_stone.run_simulation
# Frontend at http://localhost:8000/frontend/index.html
```

No test suite or linter is configured in this repo.

## Architecture

### Two package variants in `packages/`

- **agentkernel-distributed** — Uses Ray actors for pod execution across processes/nodes.
- **agentkernel-standalone** — Same architecture, no Ray dependency, runs entirely in-process.

Both share identical internal structure under `agentkernel_{distributed,standalone}/`:

| Subpackage | Role |
|---|---|
| `mas/builder.py` | Loads YAML configs + registry, wires up the full system |
| `mas/pod/` | PodManager + MasPod — agent lifecycle as Ray actors (distributed) or local wrappers (standalone) |
| `mas/agent/` | Agent perceive→plan→invoke→state→reflect lifecycle with plugin/component slots |
| `mas/action/` | Action plugins (communication, movement, etc.) |
| `mas/environment/` | Environment simulation (relations, space) |
| `mas/controller/` | Simulation flow control (tick loop) |
| `mas/system/` | Shared services: Messager (message bus), Timer (clock), Recorder |
| `mas/interface/` | FastAPI server, WebSocket broadcasting |
| `toolkit/models/` | LLM routing via OpenAI-compatible API |
| `toolkit/storages/` | Pluggable adapters: Redis KV, Redis graph, PostgreSQL, Milvus |
| `toolkit/generation/` | PCG for agents, relationships, spaces |
| `types/` | Pydantic config models and data schemas |

### Example implementations in `examples/`

Each example provides its own registry, plugins, configs, and frontend:

- **`story_of_the_stone/`** — Main Dream of the Red Chamber example (Chinese)
- **`story_of_the_stone_en/`** — English translation of the same
- **`WorldKernel/`** — Placeholder/stub (empty files)

Key files in an example:
- `run_simulation.py` — Entry point
- `registry.py` — Maps plugin/component class names to implementations (the central wiring table)
- `configs/` — YAML configs: simulation, models, system, agents, actions, environment, database
- `plugins/` — Example-specific plugin implementations
- `frontend/` — Vanilla JS visualization (no build step)
- `data/` — Character profiles (JSONL), relationships

### Simulation loop (tick cycle)

Each tick: agents **perceive** → **plan** → **invoke actions** → **update state** → **reflect**. The Messager dispatches inter-agent messages. The frontend receives WebSocket broadcasts each tick.

### Plugin system

Plugins are Python classes registered in `registry.py`. The `agents_config.yaml` defines which plugin classes back each lifecycle slot (perceive, plan, invoke, state, reflect) for each agent template. To add new behavior, implement a plugin class and register it.

## Configuration

Simulation configs live under `examples/<name>/configs/`. The master config is `simulation_config.yaml`, which references all other config files and defines data paths, pod size, tick limits, and API server settings. LLM endpoints are configured in `models_config.yaml` using OpenAI-compatible API format.

## Conventions

- No monorepo tooling — each package is independently installable via `pip install -e`.
- Config and data schemas are Pydantic models in the `types/` subpackage.
- Storage backends are pluggable via adapter pattern (configured in `db_config.yaml`).
- The frontend is plain HTML/JS/CSS with no build step — edit and refresh.
