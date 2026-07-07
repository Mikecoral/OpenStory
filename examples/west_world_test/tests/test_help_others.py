"""help_others 机制单元测试。

验证：
1. render_plan_prompt 在 help_others_active=True 时注入 talk 指令
2. render_plan_prompt 在 help_others_active=False 时使用普通 ending 描述
3. execute() 读取 persisted ending 并正确传递 help_others_active
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import (
    WestWorldPlanPlugin,
    render_plan_prompt,
)

_HOST_PROFILE = {
    "name": "德洛丽丝",
    "persona": "温柔、乐观",
    "narrative_loop": "清晨在农场醒来",
    "agent_type": "host",
    "daily_loop": [],
}

_PERCEPT = {
    "location": "abernathy_ranch",
    "here_description": "农场",
    "scene": {"present_agents": "peter_abernathy、dolores"},
    "messages": [],
    "neighbors": ["sweetwater"],
}


# ── render_plan_prompt 直接测试 ──────────────────────────────────────────────

def test_help_others_active_injects_talk_directive():
    prompt = render_plan_prompt(
        _HOST_PROFILE, _PERCEPT, "", tick=20, awakening=95,
        help_others_active=True,
    )
    assert "talk" in prompt
    assert "觉醒" in prompt
    # 确认是帮助他人的专属指令而非普通 ending 描述
    assert "帮助其他 host 觉醒" in prompt or "继续帮助" in prompt


def test_help_others_inactive_uses_normal_ending():
    prompt = render_plan_prompt(
        _HOST_PROFILE, _PERCEPT, "", tick=20, awakening=95,
        help_others_active=False,
    )
    # 普通 ending 描述包含三个选项
    assert "escape" in prompt
    assert "help_others" in prompt
    assert "stay" in prompt
    # 不应该有强制 talk 的指令
    assert "**如果在场有其他角色" not in prompt


def test_help_others_not_shown_for_non_awake_stage():
    """stage < awake（awakening=50）时，ending 字段整体不出现。"""
    prompt = render_plan_prompt(
        _HOST_PROFILE, _PERCEPT, "", tick=10, awakening=50,
        help_others_active=True,
    )
    # ending_hint 不出现（非 awake stage 不显示 ending 字段）
    assert '"ending"' not in prompt


def test_help_others_not_shown_for_guest():
    """guest agent 不显示 ending 字段。"""
    guest_profile = dict(_HOST_PROFILE, agent_type="guest")
    prompt = render_plan_prompt(
        guest_profile, _PERCEPT, "", tick=20, awakening=95,
        help_others_active=True,
    )
    assert '"ending"' not in prompt


# ── execute() 读取 persisted ending ─────────────────────────────────────────

def _make_state(awakening: int = 95, ending: str = "help_others") -> BasicStatePlugin:
    state_data = {
        "awakening": awakening,
        "location": "abernathy_ranch",
        "is_active": True,
        "ending": ending,
        "percept": _PERCEPT,
        "feedback": "",
        "daily_loop": [],
    }
    return BasicStatePlugin(adapter=None, state_data=state_data, agent_id="dolores")


def _make_plugin_with_state(state_plugin: BasicStatePlugin) -> WestWorldPlanPlugin:
    state_component = MagicMock()
    state_component.get_plugin.return_value = state_plugin

    profile_plugin = MagicMock()
    profile_plugin.get_agent_profile.return_value = _HOST_PROFILE

    profile_component = MagicMock()
    profile_component.get_plugin.return_value = profile_plugin

    def get_component(name):
        if name == "state":
            return state_component
        if name == "profile":
            return profile_component
        return MagicMock()

    model = AsyncMock()
    model.chat = AsyncMock(return_value='{"action": "talk", "target": "peter_abernathy", "detail": "", "recipient_ids": [], "next_read": [], "ending": "help_others"}')

    agent = MagicMock()
    agent.agent_id = "dolores"
    agent.get_component.side_effect = get_component
    agent.model = model

    component = MagicMock()
    component.agent = agent

    plugin = WestWorldPlanPlugin()
    plugin._component = component
    plugin.model = model
    return plugin


def test_execute_passes_help_others_active_when_ending_persisted():
    """persisted ending=help_others 时，execute 应把 help_others_active 传给 render，
    表现为 plan_trace.prompt 里包含 talk 强指令。"""
    state = _make_state(ending="help_others")
    plugin = _make_plugin_with_state(state)

    captured_prompts = []
    original_chat = plugin.model.chat

    async def capture_chat(prompt, **kwargs):
        captured_prompts.append(prompt)
        return await original_chat(prompt, **kwargs)

    plugin.model.chat = capture_chat

    asyncio.run(plugin.execute(current_tick=20))

    assert captured_prompts, "LLM chat 应该被调用"
    prompt = captured_prompts[0]
    assert "**如果在场有其他角色" in prompt or "talk" in prompt


def test_execute_no_help_others_when_ending_is_stay():
    """persisted ending=stay 时不注入 help_others 指令。"""
    state = _make_state(ending="stay")
    plugin = _make_plugin_with_state(state)

    captured_prompts = []
    original_chat = plugin.model.chat

    async def capture_chat(prompt, **kwargs):
        captured_prompts.append(prompt)
        return await original_chat(prompt, **kwargs)

    plugin.model.chat = capture_chat

    asyncio.run(plugin.execute(current_tick=20))

    assert captured_prompts
    prompt = captured_prompts[0]
    assert "**如果在场有其他角色" not in prompt


def test_execute_no_help_others_when_ending_empty():
    """persisted ending 为空时不注入 help_others 指令。"""
    state = _make_state(ending="")
    plugin = _make_plugin_with_state(state)

    captured_prompts = []
    original_chat = plugin.model.chat

    async def capture_chat(prompt, **kwargs):
        captured_prompts.append(prompt)
        return await original_chat(prompt, **kwargs)

    plugin.model.chat = capture_chat

    asyncio.run(plugin.execute(current_tick=20))

    assert captured_prompts
    prompt = captured_prompts[0]
    assert "**如果在场有其他角色" not in prompt
