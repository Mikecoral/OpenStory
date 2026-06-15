"""单元测试：Narrative Loop 机制（纯函数，不依赖 Ray/Redis）。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import (
    SEGMENT_NAMES,
    parse_decision,
    render_plan_prompt,
)
from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import (
    compose_tick_memory,
    should_summarize,
)

# ─── 数据路径 ───────────────────────────────────────────────────────────────
_DATA = Path(__file__).parent.parent / "data"
_PROFILES_FILE = _DATA / "agents" / "profiles_sim.jsonl"
_LOCATIONS_FILE = _DATA / "map" / "locations.yaml"


def _load_profiles():
    return [json.loads(line) for line in _PROFILES_FILE.read_text().splitlines() if line.strip()]


def _load_location_ids():
    locs = yaml.safe_load(_LOCATIONS_FILE.read_text())
    return {loc["id"] for loc in locs}


# ─── profiles 数据校验 ──────────────────────────────────────────────────────

class TestProfilesData:
    def test_all_agents_have_agent_type(self):
        profiles = _load_profiles()
        assert len(profiles) == 13
        for p in profiles:
            assert "agent_type" in p, f"{p['id']} 缺少 agent_type"
            assert p["agent_type"] in ("host", "guest"), f"{p['id']} agent_type 值非法"

    def test_guest_agents(self):
        profiles = _load_profiles()
        guests = [p["id"] for p in profiles if p["agent_type"] == "guest"]
        assert sorted(guests) == ["logan", "william"]

    def test_all_agents_have_daily_loop_with_6_segments(self):
        profiles = _load_profiles()
        for p in profiles:
            loop = p.get("daily_loop", [])
            assert len(loop) == 6, f"{p['id']} daily_loop 不足 6 段（实际 {len(loop)}）"

    def test_daily_loop_segment_names_correct(self):
        profiles = _load_profiles()
        for p in profiles:
            for i, seg in enumerate(p["daily_loop"]):
                assert seg.get("segment") == SEGMENT_NAMES[i], (
                    f"{p['id']} 第 {i} 段 segment 名不对: {seg.get('segment')!r}"
                )

    def test_daily_loop_locations_valid(self):
        profiles = _load_profiles()
        valid_ids = _load_location_ids()
        for p in profiles:
            for seg in p["daily_loop"]:
                loc = seg.get("location", "")
                assert loc in valid_ids, (
                    f"{p['id']} loop 地点 {loc!r} 不在地图中"
                )

    def test_daily_loop_has_intent(self):
        profiles = _load_profiles()
        for p in profiles:
            for seg in p["daily_loop"]:
                assert seg.get("intent"), f"{p['id']} 某段缺少 intent"


# ─── 当前段选取逻辑 ─────────────────────────────────────────────────────────

class TestSegmentSelection:
    @pytest.mark.parametrize("tick,expected_idx", [
        (0, 0), (1, 1), (5, 5), (6, 0), (7, 1), (11, 5), (12, 0),
    ])
    def test_segment_index(self, tick, expected_idx):
        assert tick % 6 == expected_idx

    def test_render_plan_prompt_includes_loop_segment(self):
        profile = {"name": "测试", "persona": "x", "narrative_loop": "y", "daily_loop": []}
        percept = {"location": "sweetwater", "here_description": "", "scene": {}, "messages": [], "neighbors": []}
        seg = {"segment": "正午", "location": "sweetwater_saloon", "intent": "喝酒"}
        prompt = render_plan_prompt(profile, percept, "", 2, seg)
        assert "正午" in prompt
        assert "sweetwater_saloon" in prompt
        assert "喝酒" in prompt

    def test_render_plan_prompt_fallback_when_no_segment(self):
        profile = {"name": "测试", "persona": "x", "narrative_loop": "y"}
        percept = {"location": "sweetwater", "here_description": "", "scene": {}, "messages": [], "neighbors": []}
        prompt = render_plan_prompt(profile, percept, "", 3, None)
        # 应使用默认段名（tick 3 = 下午）
        assert "下午" in prompt
        assert "（未知）" in prompt


# ─── parse_decision 容错 ─────────────────────────────────────────────────────

class TestParseDecision:
    def test_valid_do(self):
        raw = '{"action": "do", "target": "", "detail": "看书", "recipient_ids": [], "next_read": []}'
        d = parse_decision(raw)
        assert d["action"] == "do"
        assert d["detail"] == "看书"

    def test_valid_move(self):
        raw = '{"action": "move", "target": "sweetwater", "detail": "", "recipient_ids": [], "next_read": []}'
        d = parse_decision(raw)
        assert d["action"] == "move"
        assert d["target"] == "sweetwater"

    def test_fallback_on_invalid_json(self):
        d = parse_decision("这不是 JSON")
        assert d["action"] == "stay"

    def test_fallback_on_unknown_action(self):
        d = parse_decision('{"action": "fly", "target": "", "detail": "", "recipient_ids": [], "next_read": []}')
        assert d["action"] == "stay"

    def test_strips_code_fence(self):
        raw = '```json\n{"action": "stay", "target": "", "detail": "", "recipient_ids": [], "next_read": []}\n```'
        d = parse_decision(raw)
        assert d["action"] == "stay"


# ─── compose_tick_memory / should_summarize ──────────────────────────────────

class TestReflectHelpers:
    @pytest.mark.parametrize("tick,interval,expected", [
        (5, 6, True), (11, 6, True), (0, 6, False), (4, 6, False), (5, 0, False),
    ])
    def test_should_summarize(self, tick, interval, expected):
        assert should_summarize(tick, interval) == expected

    def test_compose_memory_move(self):
        mem = compose_tick_memory({"action": "move", "target": "sweetwater"}, "", "abernathy_ranch", 3)
        assert "sweetwater" in mem
        assert "第3刻" in mem

    def test_compose_memory_do_with_feedback(self):
        mem = compose_tick_memory({"action": "do", "detail": "擦杯子"}, "完成了", "sweetwater_saloon", 7)
        assert "擦杯子" in mem
        assert "完成了" in mem

    def test_compose_memory_stay(self):
        mem = compose_tick_memory({"action": "stay"}, "", "sweetwater", 0)
        assert "原地停留" in mem


# ─── 测试用假 component/agent ────────────────────────────────────────────────

class _FakeComponent:
    def __init__(self, agent):
        self.agent = agent


def _make_agent(agent_id: str, profile: dict, model=None) -> MagicMock:
    agent = MagicMock()
    agent.agent_id = agent_id
    agent.model = model
    profile_plugin = MagicMock()
    profile_plugin.get_agent_profile.return_value = profile
    agent.get_component.return_value.get_plugin.return_value = profile_plugin
    return agent


# ─── replan 边界：只改 current_segment+1..5 ──────────────────────────────────

class TestReplanBoundary:
    """验证 replan_remaining 的分段写回逻辑，使用 mock model。"""

    def test_replan_writes_only_remaining_segments(self):
        from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import WestWorldPlanPlugin

        async def run():
            plugin = WestWorldPlanPlugin()

            agent = _make_agent("teddy", {"name": "泰迪", "daily_loop": []})
            plugin._component = _FakeComponent(agent)

            new_segs = [
                {"segment": "正午", "location": "sweetwater_saloon", "intent": "喝酒"},
                {"segment": "下午", "location": "sweetwater", "intent": "找人"},
                {"segment": "傍晚", "location": "abernathy_ranch", "intent": "护送"},
                {"segment": "夜晚", "location": "sweetwater", "intent": "回镇"},
            ]
            mock_model = AsyncMock()
            mock_model.chat = AsyncMock(return_value=json.dumps(new_segs, ensure_ascii=False))
            plugin.model = mock_model

            store = {
                "daily_loop": [
                    {"segment": "清晨", "location": "sweetwater_train_station", "intent": "抵达"},
                    {"segment": "上午", "location": "sweetwater", "intent": "进镇"},
                    {"segment": "正午", "location": "sweetwater_saloon", "intent": "喝酒"},
                    {"segment": "下午", "location": "sweetwater", "intent": "找人"},
                    {"segment": "傍晚", "location": "abernathy_ranch", "intent": "护送"},
                    {"segment": "夜晚", "location": "sweetwater", "intent": "回镇"},
                ],
                "known_map": ["sweetwater", "sweetwater_saloon", "abernathy_ranch"],
                "current_day": 0,
                "replan_log": [],
            }

            async def fake_get(key):
                return store.get(key)

            async def fake_set(key, val):
                store[key] = val

            state_plugin = MagicMock()
            state_plugin.get_state = AsyncMock(side_effect=fake_get)
            state_plugin.set_state = AsyncMock(side_effect=fake_set)

            result = await plugin.replan_remaining(current_tick=1, reason="发生冲突", state_plugin=state_plugin)

            assert result is True
            new_loop = store["daily_loop"]
            assert new_loop[0]["segment"] == "清晨"
            assert new_loop[1]["segment"] == "上午"
            assert new_loop[2:] == new_segs
            assert len(store["replan_log"]) == 1
            assert store["replan_log"][0]["from_segment"] == 2

        asyncio.run(run())

    def test_replan_skips_on_last_segment(self):
        from examples.west_world_test.plugins.agent.plan.WestWorldPlanPlugin import WestWorldPlanPlugin

        async def run():
            plugin = WestWorldPlanPlugin()
            agent = _make_agent("teddy", {"name": "泰迪"})
            plugin._component = _FakeComponent(agent)
            plugin.model = AsyncMock()

            state_plugin = MagicMock()
            state_plugin.get_state = AsyncMock(return_value=[{} for _ in range(6)])

            result = await plugin.replan_remaining(current_tick=5, reason="x", state_plugin=state_plugin)
            assert result is False
            plugin.model.chat.assert_not_called()

        asyncio.run(run())


# ─── 每日重置 host/guest 分支 ────────────────────────────────────────────────

class TestDayReset:
    def test_host_gets_teleported(self):
        from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin

        async def run():
            plugin = WestWorldReflectPlugin()
            agent = _make_agent("dolores", {"name": "德洛丽丝", "agent_type": "host"})
            plugin._component = _FakeComponent(agent)

            store = {"loop_origin": "abernathy_ranch", "location": "sweetwater"}

            async def fake_get(key):
                return store.get(key)

            async def fake_set(key, val):
                store[key] = val

            state_plugin = MagicMock()
            state_plugin.get_state = AsyncMock(side_effect=fake_get)
            state_plugin.set_state = AsyncMock(side_effect=fake_set)

            scene_calls = []

            async def fake_scene(controller, location_id, method, *args):
                scene_calls.append((location_id, method, args))
                return None

            plugin._scene_call = fake_scene

            await plugin._day_reset(state_plugin, current_tick=5)

            assert store["location"] == "abernathy_ranch"
            methods_called = [c[1] for c in scene_calls]
            assert "agent_leave" in methods_called
            assert "agent_enter" in methods_called

        asyncio.run(run())

    def test_guest_skips_reset(self):
        from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin

        async def run():
            plugin = WestWorldReflectPlugin()
            agent = _make_agent("william", {"name": "威廉", "agent_type": "guest"})
            plugin._component = _FakeComponent(agent)

            scene_calls = []

            async def fake_scene(controller, location_id, method, *args):
                scene_calls.append(method)

            plugin._scene_call = fake_scene

            state_plugin = MagicMock()
            state_plugin.get_state = AsyncMock(return_value="sweetwater")

            await plugin._day_reset(state_plugin, current_tick=5)

            assert scene_calls == []

        asyncio.run(run())

    def test_no_reset_when_already_at_origin(self):
        from examples.west_world_test.plugins.agent.reflect.WestWorldReflectPlugin import WestWorldReflectPlugin

        async def run():
            plugin = WestWorldReflectPlugin()
            agent = _make_agent("dolores", {"name": "德洛丽丝", "agent_type": "host"})
            plugin._component = _FakeComponent(agent)

            store = {"loop_origin": "abernathy_ranch", "location": "abernathy_ranch"}

            async def fake_get(key):
                return store.get(key)

            state_plugin = MagicMock()
            state_plugin.get_state = AsyncMock(side_effect=fake_get)

            scene_calls = []

            async def fake_scene(controller, location_id, method, *args):
                scene_calls.append(method)

            plugin._scene_call = fake_scene

            await plugin._day_reset(state_plugin, current_tick=5)

            assert scene_calls == []

        asyncio.run(run())
