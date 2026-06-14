"""WestWorldReflectPlugin：每 tick 累积短期记忆，每 N tick LLM 总结进长期记忆。

参考红楼梦 BasicReflectPlugin 的「短期记忆→总结→长期记忆」思路，但适配
west_world 的「每 tick 现场决策」模型（无 hourly_plans / LongTask）。
纯函数（compose/should_summarize/render）单独可测，execute 用真实 BasicStatePlugin 做内存态。
"""
import asyncio

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import (
    WestWorldReflectPlugin,
    compose_tick_memory,
    render_summary_prompt,
    should_summarize,
)


# ---- 纯函数 ----

def test_compose_tick_memory_covers_move_do_stay_and_feedback():
    move = compose_tick_memory({"action": "move", "target": "sweetwater"}, "你看见酒馆里有人。", "sweetwater", 3)
    assert "3" in move and "sweetwater" in move and "酒馆" in move

    do = compose_tick_memory({"action": "do", "detail": "我擦拭吧台"}, "", "saloon", 4)
    assert "擦拭吧台" in do and "4" in do

    stay = compose_tick_memory({"action": "stay"}, "", "ranch", 5)
    assert "5" in stay and "ranch" in stay
    # 空决策不应抛错
    assert compose_tick_memory(None, "", "", 0)


def test_should_summarize_only_on_interval_boundary():
    assert should_summarize(5, 6) is True   # (5+1) % 6 == 0
    assert should_summarize(11, 6) is True
    assert should_summarize(4, 6) is False
    assert should_summarize(2, 3) is True


def test_render_summary_prompt_contains_name_and_all_memories():
    prompt = render_summary_prompt("德洛丽丝", ["（第0刻）我醒来", "（第1刻）我去镇上"])
    assert "德洛丽丝" in prompt
    assert "我醒来" in prompt and "我去镇上" in prompt


# ---- execute（真实 BasicStatePlugin + 假 model/agent）----

class _FakeModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts = []

    async def chat(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self.reply


class _FakeProfilePlugin:
    def get_agent_profile(self):
        return {"name": "德洛丽丝", "persona": "温柔好奇"}


class _FakeComponent:
    def __init__(self, plugin):
        self._plugin = plugin

    def get_plugin(self):
        return self._plugin


class _FakeAgent:
    def __init__(self, components, model, agent_id):
        self._components = components
        self.model = model
        self.agent_id = agent_id

    def get_component(self, name):
        return self._components[name]


class _FakeReflectComponent:
    def __init__(self, agent):
        self.agent = agent


def _wire(model_reply: str, interval: int):
    state = BasicStatePlugin(adapter=None, state_data={}, agent_id="dolores")
    components = {
        "state": _FakeComponent(state),
        "profile": _FakeComponent(_FakeProfilePlugin()),
    }
    agent = _FakeAgent(components, _FakeModel(model_reply), "dolores")
    plugin = WestWorldReflectPlugin(interval=interval)
    plugin._component = _FakeReflectComponent(agent)
    return plugin, state, agent


def test_execute_accumulates_short_term_memory_each_tick():
    plugin, state, _ = _wire("总结：今天在镇上转了一圈。", interval=6)

    async def run():
        for tick in range(3):  # 0,1,2 —— 未到 interval 边界
            await state.set_state("plan_decision", {"action": "do", "detail": f"我做了事{tick}"})
            await state.set_state("feedback", f"反馈{tick}")
            await state.set_state("location", "saloon")
            await plugin.execute(tick)
        return await state.get_short_term_memory()

    memories = asyncio.run(run())
    assert len(memories) == 3
    assert any("我做了事2" in m["content"] for m in memories)
    # 未触发总结
    assert state.state_data["long_term_memory"] == []


def test_execute_summarizes_and_clears_on_boundary():
    plugin, state, agent = _wire("德洛丽丝今天在甜水镇度过了平静的一天。", interval=3)

    async def run():
        for tick in range(3):  # 0,1,2 —— tick=2 触发 (2+1)%3==0
            await state.set_state("plan_decision", {"action": "move", "target": "sweetwater"})
            await state.set_state("feedback", "")
            await state.set_state("location", "saloon")
            await plugin.execute(tick)

    asyncio.run(run())
    long_mem = state.state_data["long_term_memory"]
    assert len(long_mem) == 1
    assert "甜水镇" in long_mem[0]["content"]
    # 总结后短期记忆被清空
    assert asyncio.run(state.get_short_term_memory()) == []
    # 确实调用了 LLM 且 prompt 含角色名
    assert agent.model.prompts and "德洛丽丝" in agent.model.prompts[0]


def test_execute_is_safe_without_model():
    plugin, state, agent = _wire("unused", interval=3)
    agent.model = None  # LLM 不可用时降级：仍累积短期记忆，但不总结、不清空

    async def run():
        for tick in range(3):
            await state.set_state("plan_decision", {"action": "stay"})
            await state.set_state("location", "ranch")
            await plugin.execute(tick)

    asyncio.run(run())
    # 无模型时不总结，短期记忆保留
    assert len(asyncio.run(state.get_short_term_memory())) == 3
    assert state.state_data["long_term_memory"] == []
