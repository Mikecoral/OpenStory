from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from worldkernel.stage3 import build_agentkernel_project


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class _StubModel:
    """Minimal LLM stub: returns 12 hourly plans alternating allowed locations."""

    async def chat(self, prompt: str) -> str:
        names = ["Open Hall", "Study"]
        plans = [
            {
                "action": "observe",
                "time": hour,
                "target": "自己",
                "location": names[hour % len(names)],
                "importance": 1,
            }
            for hour in range(12)
        ]
        return json.dumps(plans, ensure_ascii=False)


def _case_root(name: str) -> Path:
    root = Path(__file__).resolve().parents[3] / ".tmp" / "worldkernel-stage3-tests" / f"{name}-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def _preserve_runtime_data():
    project_root = Path(__file__).resolve().parents[1]
    data_files = [
        project_root / "data" / "agents" / "profiles.jsonl",
        project_root / "data" / "agents" / "states.jsonl",
        project_root / "data" / "relations" / "relations.jsonl",
        project_root / "data" / "map" / "agents.jsonl",
        project_root / "data" / "map" / "locations.json",
        project_root / "data" / "map" / "paths.json",
        project_root / "data" / "world" / "background.json",
        project_root / "data" / "stage3_manifest.json",
    ]
    snapshots = {path: path.read_bytes() if path.exists() else None for path in data_files}
    try:
        yield
    finally:
        for path, content in snapshots.items():
            if content is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def _make_stage2_session(root: Path) -> Path:
    session = root / "session-001"
    semantic = session / "generated" / "artifacts" / "semantic"
    spatial = session / "generated" / "artifacts" / "spatial"

    _write_json(
        session / "generated" / "plan" / "world_background.json",
        {
            "world_name": "Test World",
            "theme": "truth and access",
            "world_constraints": ["Stay grounded in generated locations."],
        },
    )
    _write_json(
        semantic / "metadata" / "semantic_manifest.json",
        {
            "world_id": "world-001",
            "artifact_files": {
                "location_profile": "locations/locations.json",
                "character_profile": "characters/characters.json",
                "path_edge": "path_graph/path_graph.json",
                "relation_edge": "relation_graph/relation_graph.json",
            },
        },
    )
    _write_json(
        semantic / "locations" / "locations.json",
        {
            "artifact_type": "location_profile",
            "items": [
                {
                    "identity": {
                        "id": "loc-open",
                        "name": "Open Hall",
                        "type": "hall",
                        "description": "A public hall.",
                        "symbolic_meaning": "public order",
                        "key_plot_events": "gatherings",
                    },
                    "access": {"access_level": "open", "permissions": "all"},
                    "state": {"current_state": "busy", "capacity": 20},
                },
                {
                    "identity": {
                        "id": "loc-closed",
                        "name": "Closed Vault",
                        "type": "vault",
                        "description": "A sealed vault.",
                    },
                    "access": {"access_level": "closed", "permissions": "forbidden"},
                    "state": {"current_state": "blocked", "capacity": 2},
                },
            ],
        },
    )
    _write_json(
        semantic / "characters" / "characters.json",
        {
            "artifact_type": "character_profile",
            "items": [
                {
                    "identity": {"id": "char-a", "name": "Ada", "role": "witness"},
                    "goals": {"long_term_goal": "Understand the hall."},
                    "memories": {"key_events": ["arrived"]},
                    "state": {
                        "location": {"location_id": "loc-open"},
                        "position": {"x": 1, "y": 2},
                    },
                },
                {
                    "identity": {"id": "char-b", "name": "Ben", "role": "keeper"},
                    "goals": {"motivation": "Guard secrets."},
                    "memories": {},
                    "state": {"location": {"location_id": "missing-location"}},
                },
            ],
        },
    )
    _write_json(
        semantic / "path_graph" / "path_graph.json",
        {
            "artifact_type": "path_edge",
            "items": [
                {
                    "identity": {"id": "path-1", "name": "Hall to Vault", "type": "door"},
                    "endpoints": {"from_id": "loc-open", "to_id": "loc-closed", "bidirectional": True},
                    "conditions": {"access_level": "restricted", "danger_level": "low"},
                },
                {
                    "identity": {"id": "path-bad", "name": "Bad Path"},
                    "endpoints": {"from_id": "loc-open", "to_id": "missing", "bidirectional": True},
                    "conditions": {},
                },
            ],
        },
    )
    _write_json(
        semantic / "relation_graph" / "relation_graph.json",
        {
            "artifact_type": "relation_edge",
            "items": [
                {
                    "edge": {
                        "id": "rel-1",
                        "from_id": "char-a",
                        "to_id": "char-b",
                        "type": "trust",
                        "direction": "one-way",
                    },
                    "properties": {"strength": "medium", "description": "Ada trusts Ben."},
                }
            ],
        },
    )
    _write_json(
        spatial / "spatial_blueprint.json",
        {
            "world_id": "world-001",
            "grid": {"width": 20, "height": 20, "tile_size": 16},
            "regions": [
                {
                    "location_id": "loc-open",
                    "name": "Open Hall",
                    "bounds": {"x": 1, "y": 1, "w": 5, "h": 5},
                    "entrance": {"x": 2, "y": 2},
                    "tags": [],
                },
                {
                    "location_id": "loc-closed",
                    "name": "Closed Vault",
                    "bounds": {"x": 8, "y": 1, "w": 3, "h": 3},
                    "entrance": {"x": 8, "y": 2},
                    "tags": [],
                },
            ],
            "routes": [
                {
                    "path_edge_id": "path-1",
                    "from_location_id": "loc-open",
                    "to_location_id": "loc-closed",
                    "centerline": [{"x": 2, "y": 2}, {"x": 8, "y": 2}],
                    "movement_cost": 1.0,
                    "access_tags": ["restricted"],
                }
            ],
            "spawn_points": [
                {"character_id": "char-a", "character_name": "Ada", "location_id": "loc-open", "position": [2, 2]}
            ],
        },
    )
    return session


def _load_runtime_module(module_name: str, relative_path: str):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    spec = importlib.util.spec_from_file_location(module_name, project_root / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage3_adapter_preserves_location_profile() -> None:
    root = _case_root("preserves-location-profile")
    session = _make_stage2_session(root)
    with _preserve_runtime_data():
        result = build_agentkernel_project(session, max_ticks=3)

        assert result.counts["locations"] == 2
        assert result.counts["paths"] == 1
        assert result.dry_validation_passed
        assert Path(result.project_root).name == "WorldKernel"
        assert Path(result.manifest_path).name == "stage3_manifest.json"
        assert result.data_paths["world_background"] == "data/world/background.json"

        simulation_config = (Path(result.project_root) / "configs" / "simulation_config.yaml").read_text(encoding="utf-8")
        assert 'models: "models.yaml"' in simulation_config

        world_background = json.loads(
            (Path(result.project_root) / "data" / "world" / "background.json").read_text(encoding="utf-8")
        )
        assert world_background["world_name"] == "Test World"

        locations = json.loads((Path(result.project_root) / "data" / "map" / "locations.json").read_text(encoding="utf-8"))
        open_hall = next(loc for loc in locations if loc["id"] == "loc-open")

        assert open_hall["name"] == "Open Hall"
        assert open_hall["access"]["access_level"] == "open"
        assert open_hall["state"]["current_state"] == "busy"
        assert open_hall["capacity"] == 20
        assert open_hall["symbolic_meaning"] == "public order"
        assert open_hall["key_plot_events"] == "gatherings"
        assert open_hall["raw"]["identity"]["description"] == "A public hall."

        profiles = [
            json.loads(line)
            for line in (Path(result.project_root) / "data" / "agents" / "profiles.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        states = [
            json.loads(line)
            for line in (Path(result.project_root) / "data" / "agents" / "states.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        ada_profile = next(row for row in profiles if row["id"] == "Ada")
        ada_state = next(row for row in states if row["id"] == "Ada")
        assert "memories" not in ada_profile
        assert "location_id" not in ada_profile
        assert ada_state["location_id"] == "loc-open"
        assert ada_state["memory"]["key_events"] == ["arrived"]
        assert ada_profile["raw"]["memories"]["key_events"] == ["arrived"]


def test_stage3_ready_session_summary_requires_complete_stage2_artifacts() -> None:
    from worldkernel.stage3.sessions import build_stage3_session_summary

    root = _case_root("stage3-session-summary")
    session = _make_stage2_session(root)
    incomplete_session = root / "incomplete-session"
    _write_json(
        incomplete_session / "generated" / "artifacts" / "semantic" / "metadata" / "semantic_manifest.json",
        {"world_id": "incomplete", "artifact_files": {}},
    )

    summary = build_stage3_session_summary(session)
    incomplete_summary = build_stage3_session_summary(incomplete_session)

    assert summary is not None
    assert summary["session_id"] == "session-001"
    assert summary["world_name"] == "Test World"
    assert summary["counts"]["characters"] == 2
    assert summary["counts"]["locations"] == 2
    assert summary["counts"]["regions"] == 2
    assert summary["counts"]["spawn_points"] == 1
    assert incomplete_summary is None


def test_generated_space_plugin_filters_accessible_locations() -> None:
    root = _case_root("space-plugin-access")
    session = _make_stage2_session(root)
    with _preserve_runtime_data():
        result = build_agentkernel_project(session)
        project_root = Path(result.project_root)

        plugin_path = project_root / "plugins" / "environment" / "space" / "BasicSpacePlugin.py"
        spec = importlib.util.spec_from_file_location("basic_space_plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        locations = json.loads((project_root / "data" / "map" / "locations.json").read_text(encoding="utf-8"))
        paths = json.loads((project_root / "data" / "map" / "paths.json").read_text(encoding="utf-8"))
        agents = [
            json.loads(line)
            for line in (project_root / "data" / "map" / "agents.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        plugin = module.BasicSpacePlugin(locations=locations, paths=paths, agents=agents)

        import asyncio

        accessible = asyncio.run(plugin.list_accessible_locations({"id": "Ada"}, 0))
        names = {loc["name"] for loc in accessible}

        assert "Open Hall" in names
        assert "Closed Vault" not in names


def test_generated_move_plugin_rejects_missing_location() -> None:
    root = _case_root("move-plugin-rejects")
    session = _make_stage2_session(root)
    with _preserve_runtime_data():
        result = build_agentkernel_project(session)
        project_root = Path(result.project_root)
        sys.path.insert(0, str(project_root))
        try:
            spec = importlib.util.spec_from_file_location(
                "basic_move_plugin",
                project_root / "plugins" / "action" / "move" / "BasicMovePlugin.py",
            )
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(module)
            move = module.BasicMovePlugin()

            class Controller:
                async def run_agent_method(self, *args):
                    if args[2] == "get_agent_profile":
                        return {"id": "Ada"}
                    if args[2] == "get_state":
                        return "loc-open"
                    return None

                async def run_environment(self, component, method, *args):
                    if method == "can_agent_enter":
                        return {"allowed": False, "reason": "location not found"}
                    return None

            import asyncio

            asyncio.run(move.init(controller=Controller()))
            result_obj = asyncio.run(move.move_to(agent_id="Ada", location="Missing"))
            assert result_obj.is_error()
            assert "location not found" in result_obj.message
        finally:
            sys.path.remove(str(project_root))


def test_plan_plugin_uses_accessible_location_names() -> None:
    module = _load_runtime_module(
        "basic_plan_plugin", "plugins/agent/plan/BasicPlanPlugin.py"
    )
    plugin = module.BasicPlanPlugin()
    # Avoid cross-test contamination from the class-level injected location list.
    module.BasicPlanPlugin.set_locations([])

    class Controller:
        async def run_environment(self, component, method, *args):
            assert component == "space"
            assert method == "list_accessible_locations"
            return [
                {"id": "loc-open", "name": "Open Hall", "activities": ["observe"]},
                {"id": "loc-study", "name": "Study", "activities": ["study"]},
            ]

        async def get_all_agent_ids(self):
            return ["Ada"]

    import asyncio

    plugin.controller = Controller()
    plugin.model = _StubModel()
    plans = asyncio.run(
        plugin.generate_hourly_plans("Ada", 0, {"id": "Ada", "name": "Ada"}, None)
    )
    allowed = {"Open Hall", "Study"}

    assert len(plans) == 12
    assert {plan[3] for plan in plans}.issubset(allowed)


def test_invoke_plugin_records_action_for_low_importance_plan() -> None:
    module = _load_runtime_module(
        "basic_invoke_plugin", "plugins/agent/invoke/BasicInvokePlugin.py"
    )
    plugin = module.BasicInvokePlugin()

    class StatePlugin:
        def __init__(self):
            self.values = {
                "hourly_plans": {1: [["observe", 0, "自己", "Open Hall", 2]]},
                "current_plan": None,
                "current_action": None,
                "current_plan_note": None,
                "occupied_by": None,
            }
            self.memories = []

        async def is_active(self):
            return True

        async def get_hourly_plans(self, day=None):
            return self.values["hourly_plans"]

        async def set_state(self, key, value):
            self.values[key] = value

        async def add_short_term_memory(self, memory, tick=None):
            self.memories.append({"tick": tick, "content": memory})

        async def add_dialogue(self, tick, history):
            pass

    class ProfilePlugin:
        def get_agent_profile(self):
            return {"id": "Ada", "name": "Ada"}

        async def get_agent_profile_by_id(self, target):
            return {"id": target, "name": target}

    class StateComponent:
        def __init__(self, plugin):
            self._plugin = plugin

        def get_plugin(self):
            return self._plugin

    class ProfileComponent:
        def __init__(self, plugin):
            self._plugin = plugin

        def get_plugin(self):
            return self._plugin

    class Agent:
        def __init__(self, state_comp, profile_comp):
            self._components = {"state": state_comp, "profile": profile_comp}
            self.controller = None

        def get_component(self, name):
            return self._components[name]

    class Component:
        def __init__(self, agent):
            self.agent = agent

    class MoveResult:
        message = "ok"

        def is_successful(self):
            return True

    class Controller:
        async def run_action(self, component, method, **kwargs):
            return MoveResult()

    import asyncio

    state_plugin = StatePlugin()
    profile_plugin = ProfilePlugin()
    agent = Agent(StateComponent(state_plugin), ProfileComponent(profile_plugin))
    plugin.agent_id = "Ada"
    plugin.controller = Controller()
    plugin.redis = None  # no occupancy backend in this unit test
    plugin._component = Component(agent)

    asyncio.run(plugin.execute(0))

    assert state_plugin.values["current_action"] is not None
    assert "Open Hall" in state_plugin.values["current_action"]
    assert state_plugin.memories
