"""Kernel environment plugin wrapping the tested recorder comparison core."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from agentkernel_distributed.mas.environment.base.plugin_base import GenericPlugin

from examples.west_world_test.core.compare import _is_relevant
from examples.west_world_test.core.image_representation import ImageRepresentation
from examples.west_world_test.core.metrics import is_correct, normalize
from examples.west_world_test.core.oracle import OracleState
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


class SceneRecorderPlugin(GenericPlugin):
    COMPONENT_TYPE = "scene"

    def __init__(
        self,
        method: str = "both",
        config_path: str = "configs/models_config.yaml",
        llm_factory: Optional[Callable[[], Any]] = None,
        image_gen_factory: Optional[Callable[[], Any]] = None,
        vlm_factory: Optional[Callable[[], Any]] = None,
        **_: Any,
    ) -> None:
        super().__init__()
        self.method = method
        self.config_path = config_path
        self._llm_factory = llm_factory
        self._image_gen_factory = image_gen_factory
        self._vlm_factory = vlm_factory
        self.oracle = OracleState()
        self.reps: Dict[str, Any] = {}
        self._last_event: Optional[Event] = None

    async def init(self) -> None:
        if self._llm_factory is None:
            from examples.west_world_test.adapters.model_clients import build_image_gen, build_llm, build_vlm

            self._llm_factory = lambda: build_llm(self.config_path)
            self._image_gen_factory = lambda: build_image_gen(self.config_path)
            self._vlm_factory = lambda: build_vlm(self.config_path)
        if self.method in ("text", "both") and "text" not in self.reps:
            self.reps["text"] = TextRepresentation(self._llm_factory())
        if self.method in ("image", "both") and "image" not in self.reps:
            self.reps["image"] = ImageRepresentation(self._image_gen_factory(), self._vlm_factory())

    async def apply_event(self, event_dict: Dict[str, Any]) -> None:
        if not self.reps:
            await self.init()
        event = Event.from_dict(event_dict)
        self._last_event = event
        self.oracle.apply(event)
        for representation in self.reps.values():
            representation.update(event)

    async def probe(self, probe_dict: Dict[str, Any]) -> Dict[str, Any]:
        if not self.reps:
            await self.init()
        probe = Probe.from_dict(probe_dict)
        truth = self.oracle.answer(probe)
        answers = {}
        for name, representation in self.reps.items():
            raw = representation.answer(probe)
            answers[name] = {"answer": raw, "norm": normalize(raw, probe.answer_type), "correct": is_correct(raw, truth, probe.answer_type)}
        return {
            "probe_id": probe.id,
            "truth": truth,
            "had_relevant_event": bool(self._last_event and _is_relevant(probe, self._last_event)),
            "answers": answers,
        }

    async def save_to_db(self) -> None:
        return None

    async def load_from_db(self) -> None:
        return None
