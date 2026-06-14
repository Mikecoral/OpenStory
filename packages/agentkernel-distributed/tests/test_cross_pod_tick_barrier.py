import asyncio
import unittest

from agentkernel_distributed.mas.pod.pod_manager import PodManagerImpl


class _FakeRemoteMethod:
    def __init__(self, func):
        self.remote = func


class _FakePodForwarder:
    def __init__(self, pod_name, events, delays):
        self._pod_name = pod_name
        self._events = events
        self._delays = delays
        self.remote = self._remote

    async def _remote(self, method_name, *args):
        self._events.append((self._pod_name, method_name, "start"))
        await asyncio.sleep(self._delays.get((self._pod_name, method_name), 0))
        self._events.append((self._pod_name, method_name, "end"))
        return None


class _FakePod:
    def __init__(self, pod_name, events, delays):
        self.forward = _FakePodForwarder(pod_name, events, delays)


class CrossPodTickBarrierTest(unittest.IsolatedAsyncioTestCase):
    async def test_step_agent_uses_global_pre_reflect_barrier_across_pods(self):
        events = []
        delays = {
            ("pod_a", "step_pre_reflect"): 0.05,
            ("pod_b", "step_pre_reflect"): 0.0,
            ("pod_a", "step_reflect"): 0.0,
            ("pod_b", "step_reflect"): 0.0,
        }
        manager = PodManagerImpl()
        manager._pod_id_to_pod = {
            "pod_a": _FakePod("pod_a", events, delays),
            "pod_b": _FakePod("pod_b", events, delays),
        }

        await manager.step_agent()

        pod_a_pre_end = events.index(("pod_a", "step_pre_reflect", "end"))
        pod_b_pre_end = events.index(("pod_b", "step_pre_reflect", "end"))
        pod_a_reflect_start = events.index(("pod_a", "step_reflect", "start"))
        pod_b_reflect_start = events.index(("pod_b", "step_reflect", "start"))

        self.assertLess(pod_a_pre_end, pod_a_reflect_start)
        self.assertLess(pod_a_pre_end, pod_b_reflect_start)
        self.assertLess(pod_b_pre_end, pod_a_reflect_start)
        self.assertLess(pod_b_pre_end, pod_b_reflect_start)
