# OpenStory - Codex Working Notes

> This file is the project-level guide for Codex-style agents working in this repository.
> It mirrors the useful parts of `CLAUDE.md`, but keeps the instructions current and focused on how to work in this codebase.

## Project Overview

OpenStory is a multi-agent story simulation framework built on LLMs and Agent-Kernel.

- Main language: Python, preferably 3.11.
- Runtime dependencies: Ray + Redis. PostgreSQL is optional and only needed for the system recorder path.
- Active kernel package: `packages/agentkernel-distributed` (`agentkernel_distributed`).
- `packages/agentkernel-standalone` is not used by current examples unless explicitly requested.

The main examples are:

- `examples/story_of_the_stone`: main reference implementation.
- `examples/west_world_test`: Westworld-style simulation and current research playground.

## Repository Map

```text
OpenStory/
├── packages/agentkernel-distributed/agentkernel_distributed/
│   ├── mas/
│   │   ├── builder.py
│   │   ├── agent/
│   │   ├── environment/
│   │   ├── system/
│   │   ├── action/
│   │   ├── controller/
│   │   └── pod/
│   ├── toolkit/
│   └── types/
├── examples/
│   ├── story_of_the_stone/
│   └── west_world_test/
├── docs/superpowers/specs/
├── docs/superpowers/plans/
├── CLAUDE.md
└── CODEX.md
```

## Kernel Facts

The runtime architecture is component/plugin based:

- Agent components: `profile`, `perceive`, `plan`, `invoke`, `state`, `reflect`.
- Environment components: relation, space, and custom generic components.
- System components: messager, recorder, timer.
- Action components exist, but current examples often execute movement inside invoke plugins.

Each example usually has:

- `registry.py` or `registry_sim.py`: maps config names to Python classes.
- `configs/` or `configs_sim/`: YAML entrypoints and component wiring.
- plugin folders under `plugins/`.

Important runtime facts:

- Use `packages/agentkernel-distributed` in `PYTHONPATH`.
- `Builder.init()` returns `(pod_manager, system)`.
- Environment instances live inside pods, not directly on the builder.
- Environment calls should go through pod/controller/environment routing rather than importing environment singletons directly from agent-side code.
- Redis must be running for full simulations.

## General Development Rules

- Prefer existing local patterns over new abstractions.
- Read the relevant plugin/config/registry files before modifying behavior.
- Keep changes scoped. Avoid unrelated refactors.
- Do not revert user changes or unrelated dirty worktree changes.
- Use tests proportional to the risk of the change.
- For manual file edits, use patch-based edits rather than shell write tricks.
- Use `rg` / `rg --files` for search.

Useful baseline test command:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
pytest examples/west_world_test/tests -q
```

## west_world_test Workflow

When working under `examples/west_world_test/`, first read:

```text
examples/west_world_test/DEVELOPMENT_NOTES.md
```

That file is the current source of truth for:

- what the Westworld experiment is trying to observe;
- which mechanisms are active;
- latest run results;
- current interpretation of awakening/root dynamics;
- next concrete tasks.

After completing a meaningful west_world_test task, update `DEVELOPMENT_NOTES.md`.

Keep that file concise:

- preserve current state and next actions;
- remove stale implementation history;
- avoid turning it into a chronological dump.

## Current west_world_test Direction

The active research question is not general game simulation. It is:

- whether group awakening emerges in a Westworld-like multi-agent setting;
- whether awakening spreads through dialogue, memory residue, or scene conflict;
- whether root/overseer memory erasure suppresses or amplifies awakening;
- whether awakening is observable behaviorally, such as deviation from `daily_loop`.

Current preferred root design:

- memory-only root;
- no decommission by default;
- repeated anomaly memory erasure instead of killing/deactivating agents.

Current best empirical signal:

- mild memory-only online runs show a local Peter-Dolores awakening cluster;
- Dolores shows meaningful `daily_loop` deviation after awakening;
- Maeve/Clementine show weaker reverie-level signals;
- current evidence does not yet support a claim of broad group awakening.

Be careful when interpreting movement:

- movement toward the expected `daily_loop` location is not a true deviation;
- host day-boundary reset every 6 ticks can look like teleportation;
- scene conflict and guest behavior can pull agents off plan without awakening;
- `lawrence`, `teddy`, `william`, and `logan` are currently noisy for plan-deviation analysis.

## Key west_world_test Files

| Purpose | Path |
|---|---|
| Current project notes | `examples/west_world_test/DEVELOPMENT_NOTES.md` |
| Simulation entry | `examples/west_world_test/run_simulation.py` |
| Comparison runner | `examples/west_world_test/run_test.py` |
| Pod manager | `examples/west_world_test/WestWorldPodManager.py` |
| Sim registry | `examples/west_world_test/registry_sim.py` |
| Sim configs | `examples/west_world_test/configs_sim/` |
| Agent profiles / daily loops | `examples/west_world_test/data/agents/profiles_sim.jsonl` |
| Initial agent states | `examples/west_world_test/data/agents/states_sim.jsonl` |
| Map truth | `examples/west_world_test/data/map/locations.yaml` |
| Awakening triggers | `examples/west_world_test/data/triggers.yaml` |
| Overseer signals | `examples/west_world_test/data/overseer_signals.yaml` |
| Plan plugin | `examples/west_world_test/plugins/agent/plan/WestWorldPlanPlugin.py` |
| Reflect / memory / awakening | `examples/west_world_test/plugins/agent/reflect/WestWorldReflectPlugin.py` |
| Invoke plugin | `examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py` |
| Scene recorder plugin | `examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py` |
| Overseer plugin | `examples/west_world_test/plugins/environment/overseer/OverseerPlugin.py` |
| Awakening engine | `examples/west_world_test/awakening/awakening_engine.py` |
| Overseer reset | `examples/west_world_test/awakening/overseer_reset.py` |
| Overseer decommission | `examples/west_world_test/awakening/overseer_decommission.py` |
| Experiment runner | `examples/west_world_test/experiments/overseer_dynamics.py` |
| Experiment metrics | `examples/west_world_test/experiments/metrics.py` |
| Experiment matrix | `examples/west_world_test/experiments/configs/full_matrix.yaml` |

## Useful Commands

Run full west_world_test unit tests:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
pytest examples/west_world_test/tests -q
```

Run a mild memory-only long experiment:

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
python -m examples.west_world_test.experiments.overseer_dynamics \
  --matrix examples/west_world_test/experiments/configs/full_matrix.yaml \
  --select overseer_memory_only_mild \
  --ticks 36 \
  --out examples/west_world_test/output/sim_runs/online_memory_only_mild_long
```

Run the base simulation:

```bash
PYTHONPATH=$PWD:$PWD/packages/agentkernel-distributed \
WW_MAX_TICKS=20 \
python -m examples.west_world_test.run_simulation
```

## Notes On "Recorder"

The word "Recorder" has two meanings in this repository:

- Kernel `Recorder`: system-level PostgreSQL logging component.
- Westworld recorder: dynamic environment representation / scene state mechanism.

In west_world_test, the second concept is implemented through the scene/location recorder path and should not be confused with the kernel system recorder.

