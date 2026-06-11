import asyncio

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.scene.SceneRecorderPlugin import SceneRecorderPlugin


def test_plugin_component_type_is_scene():
    assert SceneRecorderPlugin.COMPONENT_TYPE == "scene"


def test_plugin_apply_and_probe_with_fakes():
    plugin = SceneRecorderPlugin(method="text", llm_factory=lambda: FakeLLM(["updated", "1"], default="1"))
    asyncio.run(plugin.apply_event({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]}))
    result = asyncio.run(plugin.probe({"id": "q9", "kind": "state", "text": "几个?", "field": "glasses_filled", "answer_type": "int"}))
    assert result["truth"] == 1
    assert result["answers"]["text"]["correct"] is True
