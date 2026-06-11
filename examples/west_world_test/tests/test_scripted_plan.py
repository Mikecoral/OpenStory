from examples.west_world_test.core.schema import Event
from examples.west_world_test.plugins.agent.plan.ScriptedPlanPlugin import ScriptedPlanPlugin


def test_action_for_returns_matching_event():
    events = [
        Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}),
        Event.from_dict({"id": "e2", "tick": 2, "actor": "黑衣人", "action": "pick_up_photo", "target": "photo"}),
    ]
    plan = ScriptedPlanPlugin(events=events, agent_id="黑衣人")
    assert plan.action_for(2) == events[1]
    assert plan.action_for(1) is None
