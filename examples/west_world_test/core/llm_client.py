"""Model client protocols and deterministic test fakes."""
from __future__ import annotations

from typing import List, Protocol, Tuple


class LLMClient(Protocol):
    def chat(self, prompt: str) -> str: ...


class ImageGen(Protocol):
    def generate(self, prompt: str) -> str: ...


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
        self.prompts: List[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"fake-image://{len(self.prompts)}"


class FakeVLM:
    def __init__(self, replies: List[str], default: str = "") -> None:
        self._replies = list(replies)
        self._default = default
        self.calls: List[Tuple[str, str]] = []

    def ask(self, image_handle: str, question: str) -> str:
        self.calls.append((image_handle, question))
        return self._replies.pop(0) if self._replies else self._default
