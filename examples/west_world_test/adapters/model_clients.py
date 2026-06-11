"""Config-driven OpenAI-compatible clients for text, vision, and Image 2."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml
from openai import OpenAI


def _load_models(path: str) -> Dict[str, Dict[str, Any]]:
    rows: List[Dict[str, Any]] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {row["role"]: row for row in rows}


class OpenAICompatibleLLM:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    def chat(self, prompt: str) -> str:
        response = self.client.chat.completions.create(model=self.config["model"], messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content or ""


class OpenAICompatibleVLM(OpenAICompatibleLLM):
    def ask(self, image_handle: str, question: str) -> str:
        content = [{"type": "text", "text": question}, {"type": "image_url", "image_url": {"url": image_handle}}]
        response = self.client.chat.completions.create(model=self.config["model"], messages=[{"role": "user", "content": content}])
        return response.choices[0].message.content or ""


class OpenAICompatibleImageGen:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    @staticmethod
    def _handle(response: Any) -> str:
        item = response.data[0]
        if item.url:
            return item.url
        if item.b64_json:
            return f"data:image/png;base64,{item.b64_json}"
        raise RuntimeError("Image response contained neither URL nor base64 image data")

    @staticmethod
    def _image_file(handle: str) -> io.BytesIO:
        if handle.startswith("data:image/"):
            content = base64.b64decode(handle.split(",", 1)[1])
        elif handle.startswith(("http://", "https://")):
            response = requests.get(handle, timeout=60)
            response.raise_for_status()
            content = response.content
        else:
            content = Path(handle).read_bytes()
        image = io.BytesIO(content)
        image.name = "previous-state.png"
        return image

    def create_initial(self, prompt: str) -> str:
        response = self.client.images.generate(model=self.config["model"], prompt=prompt, size=self.config.get("size", "1024x1024"))
        return self._handle(response)

    def apply_event(self, previous_image: str, prompt: str) -> str:
        image = self._image_file(previous_image)
        response = self.client.images.edit(
            model=self.config["model"],
            image=image,
            prompt=prompt,
            size=self.config.get("size", "1024x1024"),
            input_fidelity=self.config.get("input_fidelity", "high"),
        )
        return self._handle(response)


def build_llm(config_path: str) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(_load_models(config_path)["text"])


def build_vlm(config_path: str) -> OpenAICompatibleVLM:
    return OpenAICompatibleVLM(_load_models(config_path)["vision"])


def build_image_gen(config_path: str) -> OpenAICompatibleImageGen:
    return OpenAICompatibleImageGen(_load_models(config_path)["image"])
