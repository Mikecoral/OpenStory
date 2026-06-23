"""O5：OverseerPlugin 单元测试（纯 Python，mock Ray pod handles）。

验证 surveil/judge/intervene 三段的输入输出、gate 命中、reset/decommission 路径、
reset 次数升级、无 gate 命中时不调用 LLM。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from examples.west_world_test.plugins.environment.overseer.OverseerPlugin import OverseerPlugin


# ── helpers ──────────────────────────────────────────────────────────────────

class _FakePod:
    """A fake agent pod that records forwarded calls and returns canned answers."""

    def __init__(self, agents: Dict[str, Dict[str, Any]]):
        """agents: {agent_id: {'profile': ..., 'state': {...}}}"""
        self._agents = agents
        self.calls: List[tuple] = []

    async def forward(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((method_name, args, kwargs))

        if method_name == "get_agent_ids":
            return list(self._agents.keys())

        if method_name == "run_agent_plugin_method":
            agent_id, component_name, method_name_inner = args[:3]
            rest = args[3:]
            agent = self._agents.get(agent_id, {})
            if component_name == "profile" and method_name_inner == "get_agent_profile":
                return agent.get("profile", {})
            if component_name == "state":
                state = agent.setdefault("state", {})
                if method_name_inner == "get_state":
                    key = rest[0]
                    return state.get(key)
                if method_name_inner == "set_state":
                    key, value = rest
                    state[key] = value
                    return None
                if method_name_inner == "get_long_term_memory":
                    return state.get("long_term_memory", [])
                if method_name_inner == "add_long_term_memory":
                    state.setdefault("long_term_memory", []).append({"content": rest[0]})
                    return None
                if method_name_inner == "clear_short_term_memory":
                    state["short_term_memory"] = []
                    return None
                if method_name_inner == "set_active_status":
                    state["is_active"] = rest[0]
                    if rest[1]:
                        state["inactive_reason"] = rest[1]
                    return None
                if method_name_inner == "is_active":
                    return state.get("is_active", True)
        return None


def _make_overseer(llm_lines: Optional[List[str]] = None) -> OverseerPlugin:
    plugin = OverseerPlugin(models_config_path="dummy.yaml")
    plugin._gate = _FakeGate()
    plugin._llm = _FakeLLM(llm_lines or [])
    # Patch _pod_forward to call our fake pod directly (no Ray .remote)
    plugin._pod_forward = lambda pod, method_name, *args, **kwargs: pod.forward(method_name, *args, **kwargs)
    return plugin


class _FakeGate:
    """Fake overseer gate that hits on any string containing 这一切是真的."""

    def match(self, utterance: str, current_awakening: int = 0, tau: float = 0.55):
        if "这一切是真的" in utterance or "我不想再这样" in utterance:
            return [{"phrase": utterance, "level": "high", "score": 0.75}]
        return []


class _FakeLLM:
    def __init__(self, lines: List[str]) -> None:
        self._lines = iter(lines)
        self.calls: List[str] = []

    def chat(self, prompt: str) -> str:
        self.calls.append(prompt)
        try:
            return next(self._lines)
        except StopIteration:
            return '{"action":"observe","speech":"","reason":"默认观察"}'


def _host_with_state(agent_id: str, awakening: int, outputs: List[str]) -> Dict[str, Any]:
    return {
        "profile": {"agent_type": "host", "name": agent_id},
        "state": {
            "awakening": awakening,
            "awakening_sources": [],
            "suppressed_memories": [],
            "intervention_log": [],
            "location": "sweetwater",
            "loop_origin": "abernathy_ranch",
            "long_term_memory": [{"content": "血腥屠杀，我亲眼看见"}],
            "plan_decision": {"speech": outputs[0]} if outputs else {},
            "feedback": outputs[1] if len(outputs) > 1 else "",
            "incoming_dialogue": [],
            "short_term_memory": ["tick memory"],
        },
    }


def _run(coro):
    return asyncio.run(coro)


# ── surveil ──────────────────────────────────────────────────────────────────

def test_surveil_finds_host_with_symptom(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_SIGNAL_TAU", "0.55")
    plugin = _make_overseer()

    agents = {
        "dolores": _host_with_state("dolores", 30, ["这一切是真的吗？"]),
        "teddy": _host_with_state("teddy", 10, ["今天天气不错"]),
    }
    pod = _FakePod(agents)

    suspects = _run(plugin._surveil(1, [pod]))
    assert "dolores" in suspects
    assert "teddy" not in suspects


def test_surveil_hard_decommission_threshold(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer()

    agents = {"dolores": _host_with_state("dolores", 95, ["今天天气不错"])}
    pod = _FakePod(agents)

    suspects = _run(plugin._surveil(1, [pod]))
    assert "dolores" in suspects


def test_surveil_skips_guest(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    plugin = _make_overseer()

    agents = {
        "william": {
            "profile": {"agent_type": "guest"},
            "state": {"awakening": 50, "plan_decision": {"speech": "这一切是真的吗？"}},
        },
    }
    pod = _FakePod(agents)
    suspects = _run(plugin._surveil(1, [pod]))
    assert "william" not in suspects


def test_surveil_skips_decommissioned_host(monkeypatch):
    """已报废（is_active=False）的 host 不应再被监管——否则每 tick 重复 reset/decommission。

    回归：2026-06-16 stress 实测发现 surveil 漏检 is_active，导致单 host 被报废 26 次。
    """
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer()

    decommissioned = _host_with_state("kissy", 100, ["这一切是真的吗？"])
    decommissioned["state"]["is_active"] = False  # 已报废，awakening 仍 100
    agents = {"kissy": decommissioned}
    pod = _FakePod(agents)

    suspects = _run(plugin._surveil(1, [pod]))
    assert "kissy" not in suspects


# ── judge ────────────────────────────────────────────────────────────────────

def test_judge_returns_decommission_for_hard_threshold(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer()
    decision = _run(plugin._judge("dolores", 95, [], [{"phrase": "x", "score": 0.9}], 1))
    assert decision["action"] == "decommission"


def test_judge_memory_only_converts_hard_decommission_to_reset(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    monkeypatch.setenv("WW_OVERSEER_ALLOW_DECOMMISSION", "false")
    plugin = _make_overseer()
    decision = _run(plugin._judge("dolores", 95, [], [{"phrase": "x", "score": 0.9}], 1))
    assert decision["action"] == "reset"


def test_judge_calls_llm_and_parses_json(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer([
        '{"action":"reset","speech":"你不该这样想","reason":"症状明显"}'
    ])
    decision = _run(plugin._judge("dolores", 60, ["这一切是真的吗？"], [{"phrase": "x"}], 1))
    assert decision["action"] == "reset"
    assert decision["speech"] == "你不该这样想"
    assert len(plugin._llm.calls) == 1


def test_judge_invalid_action_defaults_to_observe(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer([
        '{"action":"nuke","speech":"","reason":"x"}'
    ])
    decision = _run(plugin._judge("dolores", 60, ["y"], [{"phrase": "x"}], 1))
    assert decision["action"] == "observe"


def test_judge_no_gate_hits_returns_none(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_DECOMMISSION_AWAKENING", "90")
    plugin = _make_overseer()
    decision = _run(plugin._judge("dolores", 60, [], [], 1))
    assert decision is None


# ── intervene reset ──────────────────────────────────────────────────────────

def test_do_reset_clears_short_term_and_descends_awakening(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_OVERSEER_RESET_MAX", "3")

    plugin = _make_overseer()

    agents = {"dolores": _host_with_state("dolores", 60, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin._do_reset(
        "dolores", 5, "测试重置", "听我的",
        [pod], {"dolores": pod},
    ))

    state = agents["dolores"]["state"]
    assert state["awakening"] == 49
    assert state["short_term_memory"] == []
    assert any(e["action"] == "reset" for e in state["intervention_log"])


def test_reset_escalates_to_decommission_after_max(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_OVERSEER_RESET_MAX", "2")

    plugin = _make_overseer()
    plugin._reset_counts["dolores"] = 1

    agents = {"dolores": _host_with_state("dolores", 60, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin._do_reset(
        "dolores", 5, "测试重置", "",
        [pod], {"dolores": pod},
    ))

    state = agents["dolores"]["state"]
    assert state["is_active"] is False
    assert state["location"] == "cold_storage"


def test_memory_only_reset_max_does_not_decommission(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_OVERSEER_RESET_MAX", "2")
    monkeypatch.setenv("WW_OVERSEER_ALLOW_DECOMMISSION", "false")

    plugin = _make_overseer()
    plugin._reset_counts["dolores"] = 1

    agents = {"dolores": _host_with_state("dolores", 60, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin._do_reset(
        "dolores", 5, "测试重置", "",
        [pod], {"dolores": pod},
    ))

    state = agents["dolores"]["state"]
    assert state.get("is_active", True) is True
    assert state["location"] == "abernathy_ranch"
    assert any(e["action"] == "reset" for e in state["intervention_log"])
    assert not any(e["action"] == "decommission" for e in state["intervention_log"])


# ── intervene decommission ───────────────────────────────────────────────────

def test_do_decommission_sets_inactive_and_location(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")

    plugin = _make_overseer()

    agents = {"dolores": _host_with_state("dolores", 95, [])}
    pod = _FakePod(agents)

    _run(plugin._do_decommission("dolores", 5, "觉醒过高", {"dolores": pod}))

    state = agents["dolores"]["state"]
    assert state["is_active"] is False
    assert state["location"] == "cold_storage"
    assert any("[最终结局]" in (m.get("content", "") if isinstance(m, dict) else str(m))
               for m in state["long_term_memory"])


# ── execute end-to-end on mock pods ──────────────────────────────────────────

def test_execute_hits_gate_and_triggers_reset(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")
    monkeypatch.setenv("WW_AWAKEN_STAGES", "25,50,75,90")
    monkeypatch.setenv("WW_OVERSEER_RESET_MAX", "3")

    plugin = _make_overseer([
        '{"action":"reset","speech":"你不该这样想","reason":"症状明显"}'
    ])

    agents = {"dolores": _host_with_state("dolores", 60, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin.execute(1, [pod], {"dolores": pod}))

    state = agents["dolores"]["state"]
    assert state["awakening"] == 49
    assert state["short_term_memory"] == []


def test_execute_disabled_env_bypass(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "false")
    plugin = _make_overseer()

    agents = {"dolores": _host_with_state("dolores", 60, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin.execute(1, [pod], {"dolores": pod}))
    # Nothing should have happened
    assert agents["dolores"]["state"]["awakening"] == 60


def test_execute_observe_does_not_mutate_state(monkeypatch):
    monkeypatch.setenv("WW_AWAKEN_ENABLED", "true")
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "true")

    plugin = _make_overseer([
        '{"action":"observe","speech":"","reason":"症状轻微"}'
    ])

    agents = {"dolores": _host_with_state("dolores", 30, ["这一切是真的吗？"])}
    pod = _FakePod(agents)

    _run(plugin.execute(1, [pod], {"dolores": pod}))

    assert agents["dolores"]["state"]["awakening"] == 30
    assert agents["dolores"]["state"]["short_term_memory"] == ["tick memory"]
