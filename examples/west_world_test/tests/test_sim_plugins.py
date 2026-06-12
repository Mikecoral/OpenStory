"""M2 插件逻辑测试：占位感知、随机游走、移动落实（无 Ray/Redis）。"""
from pathlib import Path

from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import build_percept
from examples.west_world_test.plugins.agent.plan.RandomWalkPlanPlugin import decide
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import apply_move
from examples.west_world_test.worldmap.loader import load_world_map

WORLD = load_world_map(str(Path(__file__).parents[1] / "data" / "map" / "locations.yaml"))


def test_percept_contains_description_and_known_neighbors():
    state = {"location": "sweetwater_saloon", "known_map": ["sweetwater_saloon", "sweetwater"]}
    percept = build_percept(WORLD, "dolores", state)
    assert "酒馆" in percept["here_description"]
    # neighbors 是 sweetwater_saloon 的激活邻接地点（active=True 的直接邻居）
    assert isinstance(percept["neighbors"], list)
    assert len(percept["neighbors"]) > 0
    # sweetwater_saloon 的邻接地点应至少包含 sweetwater_plaza 或 sweetwater
    assert any(n in percept["neighbors"] for n in ["sweetwater", "sweetwater_plaza"])
    # known_map 反映当前 state 中的 known_map
    assert "sweetwater_saloon" in percept["known_map"]


def test_random_walk_only_picks_active_neighbors_or_stay():
    state = {"location": "sweetwater", "known_map": ["sweetwater"]}
    percept = build_percept(WORLD, "teddy", state)
    for seed in range(20):
        decision = decide(percept, seed=seed)
        assert decision["action"] in ("stay", "move")
        if decision["action"] == "move":
            assert decision["target"] in percept["neighbors"]


def test_apply_move_updates_state_and_known_map():
    # 找一个有邻接地点的激活 location
    saloon = WORLD.get("sweetwater_saloon")
    valid_neighbor = WORLD.neighbors("sweetwater_saloon", active_only=True)[0]

    state = {"location": "sweetwater_saloon", "known_map": ["sweetwater_saloon"]}
    new_state, ok, reason = apply_move(WORLD, state, valid_neighbor)
    assert ok and new_state["location"] == valid_neighbor
    assert valid_neighbor in new_state["known_map"]

    # 测试不邻接的地点被拒绝
    # 找一个不与 sweetwater_saloon 邻接的激活 location
    non_neighbor = next(
        lid for lid in WORLD.active_ids()
        if lid not in WORLD.get("sweetwater_saloon").adjacency and lid != "sweetwater_saloon"
    )
    new_state2, ok2, reason2 = apply_move(WORLD, state, non_neighbor)
    assert not ok2 and new_state2["location"] == "sweetwater_saloon" and reason2
