"""Image-backed readout using the same textual update path as the baseline."""
from __future__ import annotations

from typing import Optional

from .llm_client import ImageGen, LLMClient, VLM
from .schema import Event, Probe
from .text_representation import DEFAULT_INITIAL_TEXT, _UPDATE_PROMPT

_IMAGE_PROMPT = "Sweetwater 酒馆俯视全景。严格呈现描述中的数量、人物与位置：\n{scene}"


class ImageRepresentation:
    def __init__(self, llm: LLMClient, image_gen: ImageGen, vlm: VLM, initial_text: str = DEFAULT_INITIAL_TEXT) -> None:
        self._llm = llm
        self._image_gen = image_gen
        self._vlm = vlm
        self.scene_text = initial_text
        self._cached_handle: Optional[str] = None
        self._cached_for: Optional[str] = None

    def update(self, event: Event) -> None:
        self.scene_text = self._llm.chat(
            _UPDATE_PROMPT.format(prev=self.scene_text, tick=event.tick, actor=event.actor, action=event.action, target=event.target, visibility=event.visibility)
        ).strip()
        self._cached_handle = None

    def _current_image(self) -> str:
        if self._cached_handle is None or self._cached_for != self.scene_text:
            self._cached_handle = self._image_gen.generate(_IMAGE_PROMPT.format(scene=self.scene_text))
            self._cached_for = self.scene_text
        return self._cached_handle

    def answer(self, probe: Probe) -> str:
        return self._vlm.ask(self._current_image(), probe.text).strip()
