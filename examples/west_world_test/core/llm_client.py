"""Model client protocols and deterministic test fakes."""
from __future__ import annotations

from typing import List, Protocol, Tuple


class LLMClient(Protocol):
    def chat(self, prompt: str) -> str: ...


class ImageGen(Protocol):
    def create_initial(self, prompt: str) -> str: ...

    def apply_event(self, previous_image: str, prompt: str) -> str: ...


class VLM(Protocol):
    def ask(self, image_handle: str, question: str) -> str: ...


class FakeLLM:
    def __init__(self, replies: List[str], default: str = "") -> None:
        self._replies = list(replies)
        self._default = default
        self.calls: List[str] = []

    def chat(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._replies.pop(0) if self._replies else self._default


class FakeImageGen:
    def __init__(self) -> None:
        self.initial_prompts: List[str] = []
        self.event_calls: List[Tuple[str, str]] = []

    def create_initial(self, prompt: str) -> str:
        self.initial_prompts.append(prompt)
        return "fake-image://initial"

    def apply_event(self, previous_image: str, prompt: str) -> str:
        self.event_calls.append((previous_image, prompt))
        return f"fake-image://event-{len(self.event_calls)}"


class FakeVLM:
    def __init__(self, replies: List[str], default: str = "") -> None:
        self._replies = list(replies)
        self._default = default
        self.calls: List[Tuple[str, str]] = []

    def ask(self, image_handle: str, question: str) -> str:
        self.calls.append((image_handle, question))
        return self._replies.pop(0) if self._replies else self._default
