"""M2 插件逻辑测试：占位感知、随机游走、移动落实（无 Ray/Redis）。"""
import json
import asyncio
from pathlib import Path

from agentkernel_distributed.types.schemas.message import Message, MessageKind
from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import build_percept
from examples.west_world_test.plugins.agent.plan.RandomWalkPlanPlugin import decide
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import (
    WestWorldInvokePlugin,
    apply_move,
    eligible_recipients,
)
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


def test_plan_prompt_contains_loop_percept_feedback_and_neighbors():
    from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import render_plan_prompt, parse_decision
    profile = {"姓名": "德洛丽丝", "性格": "温柔好奇", "narrative_loop": "清晨在农场醒来，上午去镇上采购。"}
    percept = {"location": "abernathy_ranch", "here_description": "农场。",
               "neighbors": ["sweetwater"], "known_map": ["abernathy_ranch"],
               "scene": {"present_agents": "peter_abernathy", "recent_events": []},
               "messages": [{"from_id": "teddy", "content": "我在镇上等你"}]}
    prompt = render_plan_prompt(profile, percept, feedback="你捡起了一支画笔。", tick=5)
    for needle in ("德洛丽丝", "清晨在农场醒来", "农场。", "sweetwater", "画笔", "我在镇上等你"):
        assert needle in prompt
    assert "严禁描述离开" in prompt
    assert "recipient_ids" in prompt
    decision = parse_decision('{"action": "move", "target": "sweetwater", "detail": "", "next_read": ["recent_events"]}')
    assert decision["action"] == "move" and decision["target"] == "sweetwater"
    assert decision["recipient_ids"] == []
    assert parse_decision("乱七八糟")["action"] == "stay"     # 解析失败降级为 stay


def test_invoke_move_relocates_holdings():
    """apply_move + registry relocate_holdings moves held objects with the agent."""
    from examples.west_world_test.recorder.world_object_registry import get_object_registry, reset_object_registry
    reset_object_registry()
    reg = get_object_registry()
    reg.create(name="左轮", location_id="sweetwater_saloon", by="t", tick=1, action="a", fields={}, held_by="hector")
    new_state, ok, _ = apply_move(WORLD, {"location": "sweetwater_saloon", "known_map": []}, "sweetwater")
    assert ok
    reg.relocate_holdings("hector", new_state["location"], tick=2)
    assert reg.get("obj_0")["location_id"] == "sweetwater"
    assert reg.get("obj_0")["held_by"] == "hector"


def test_perceive_consumes_messages_once():
    from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import WestWorldPerceivePlugin

    plugin = WestWorldPerceivePlugin(world=WORLD)
    message = Message("teddy", "dolores", MessageKind.FROM_AGENT_TO_AGENT, "我在镇上等你")
    asyncio.run(plugin.add_message(message))

    assert plugin._consume_messages() == [{
        "from_id": "teddy",
        "content": "我在镇上等你",
        "kind": "from_agent_to_agent",
    }]
    assert plugin._consume_messages() == []


def test_perceive_filters_sender_echo_from_kernel_messager():
    from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import WestWorldPerceivePlugin

    plugin = WestWorldPerceivePlugin(world=WORLD)
    plugin._component = type("Component", (), {
        "agent": type("Agent", (), {"agent_id": "maeve"})()
    })()
    asyncio.run(plugin.add_message(
        Message("maeve", "clementine", MessageKind.FROM_AGENT_TO_AGENT, "清理牌桌")
    ))
    asyncio.run(plugin.add_message(
        Message("clementine", "maeve", MessageKind.FROM_AGENT_TO_AGENT, "已经清理好了")
    ))

    assert plugin._consume_messages() == [{
        "from_id": "clementine",
        "content": "已经清理好了",
        "kind": "from_agent_to_agent",
    }]


def test_message_recipients_must_be_present_and_unique():
    assert eligible_recipients(
        "maeve", ["clementine", "ghost", "clementine", "maeve"],
        "maeve、clementine",
    ) == ["clementine"]


def test_invoke_delivers_explicit_dialogue_through_messager():
    class Controller:
        def __init__(self):
            self.messages = []

        async def run_environment(self, _component, method, *_args):
            assert method == "read"
            return {"present_agents": "maeve、clementine"}

        async def run_system(self, component, method, message):
            assert (component, method) == ("messager", "send_message")
            self.messages.append(message)

    plugin = WestWorldInvokePlugin(world=WORLD)
    plugin._component = type("Component", (), {
        "agent": type("Agent", (), {"agent_id": "maeve"})()
    })()
    controller = Controller()

    delivered = asyncio.run(plugin._deliver_messages(
        controller, "sweetwater_saloon", ["clementine", "ghost"], "把碎玻璃清理掉。", 2
    ))

    assert delivered == ["clementine"]
    assert controller.messages[0].to_id == "clementine"
    assert controller.messages[0].content == "把碎玻璃清理掉。"
