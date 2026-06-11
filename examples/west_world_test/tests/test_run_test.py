import asyncio

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.run_test import run_kernel_loop
from examples.west_world_test.scene.SceneRecorderPlugin import SceneRecorderPlugin


def test_kernel_loop_flattens_scene_results():
    plugin = SceneRecorderPlugin(method="text", llm_factory=lambda: FakeLLM(["0", "record", "1"], default="1"))

    async def call(_component, method, payload):
        return await getattr(plugin, method)(payload)

    events = [Event.from_dict({"id": "e1", "tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass", "affected_probe_ids": ["q9"]})]
    probes = [Probe.from_dict({"id": "q9", "kind": "state", "text": "几个?", "field": "glasses_filled", "answer_type": "int"})]
    records = asyncio.run(run_kernel_loop(events, probes, call))
    assert records == [{
        "tick": 0, "method": "text", "probe_id": "q9", "truth": 0,
        "evaluation_role": "initial", "had_relevant_event": False,
        "score_group": "visual_snapshot", "answer": "0", "norm": "0", "correct": True,
    }, {
        "tick": 1, "method": "text", "probe_id": "q9", "truth": 1,
        "evaluation_role": "affected", "had_relevant_event": True,
        "score_group": "visual_snapshot", "answer": "1", "norm": "1", "correct": True,
    }]
