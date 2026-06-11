"""Image-only recorder that evolves the previous image with each event."""
from __future__ import annotations

from typing import Optional

from .llm_client import ImageGen, VLM
from .schema import Event, Probe
from .text_representation import DEFAULT_INITIAL_TEXT

_INITIAL_IMAGE_PROMPT = (
    "Create a fixed-camera, wide overview of the Sweetwater saloon. "
    "This image is the complete initial world state. Preserve object identity, "
    "count, position, and camera composition in later edits.\n{scene}"
)

_EVENT_EDIT_PROMPT = """Edit the previous world-state image to apply exactly one event.
Preserve every unaffected object, character, count, position, and the fixed camera.
Do not use or infer any hidden textual state beyond what is visible in the previous image
and the event below.

event_id={id} tick={tick} actor={actor} action={action} target={target} visibility={visibility}
"""


class ImageRepresentation:
    def __init__(self, image_gen: ImageGen, vlm: VLM, initial_text: str = DEFAULT_INITIAL_TEXT) -> None:
        self._image_gen = image_gen
        self._vlm = vlm
        self._initial_prompt = _INITIAL_IMAGE_PROMPT.format(scene=initial_text)
        self.current_image: Optional[str] = None

    def update(self, event: Event) -> None:
        previous_image = self._ensure_current_image()
        prompt = _EVENT_EDIT_PROMPT.format(
            id=event.id,
            tick=event.tick,
            actor=event.actor,
            action=event.action,
            target=event.target,
            visibility=event.visibility,
        )
        self.current_image = self._image_gen.apply_event(previous_image, prompt)

    def _ensure_current_image(self) -> str:
        if self.current_image is None:
            self.current_image = self._image_gen.create_initial(self._initial_prompt)
        return self.current_image

    def answer(self, probe: Probe) -> str:
        return self._vlm.ask(self._ensure_current_image(), probe.text).strip()
