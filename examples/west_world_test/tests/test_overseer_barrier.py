"""O5：Overseer barrier 顺序测试。

验证 `run_overseer_barrier()` 正确调用 world pod 的 overseer 组件，
并传入 agent_pods 与 agent_id_to_pod。

纯 Python，mock Ray handles（不启动 Ray）。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from examples.west_world_test.WestWorldPodManager import run_overseer_barrier


def _make_forward(pod: "_FakeWorldPod"):
    """Return a callable that also exposes a `.remote` alias (like Ray actor handles)."""
    async def _forward(method_name: str, *args: Any, **kwargs: Any) -> Any:
        pod.calls.append((method_name, args, kwargs))
        return None
    _forward.remote = _forward
    return _forward


class _FakeWorldPod:
    def __init__(self):
        self.calls: List[tuple] = []
        self.forward = _make_forward(self)


class _FakeAgentPod:
    pass


def test_overseer_barrier_calls_execute_with_correct_args():
    world_pod = _FakeWorldPod()
    agent_pods = [_FakeAgentPod(), _FakeAgentPod()]
    agent_id_to_pod: Dict[str, Any] = {"dolores": agent_pods[0]}

    _run = lambda coro: asyncio.run(coro)
    _run(run_overseer_barrier(world_pod, agent_pods, agent_id_to_pod, current_tick=5))

    assert len(world_pod.calls) == 1
    method_name, args, kwargs = world_pod.calls[0]
    assert method_name == "run_environment"
    assert args[0] == "overseer"
    assert args[1] == "execute"
    assert args[2] == 5
    assert args[3] is agent_pods
    assert args[4] is agent_id_to_pod


def test_overseer_barrier_disabled_when_env_off(monkeypatch):
    monkeypatch.setenv("WW_OVERSEER_ENABLED", "false")
    world_pod = _FakeWorldPod()
    asyncio.run(run_overseer_barrier(world_pod, [], {}, current_tick=5))
    assert len(world_pod.calls) == 0
