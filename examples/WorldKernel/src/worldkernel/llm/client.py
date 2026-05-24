from __future__ import annotations

import re
from pathlib import Path

from openai import AsyncOpenAI

from worldkernel.llm.config_loader import load_model_config

_openai: AsyncOpenAI | None = None
_model: str = ""


def init(config_path: Path) -> None:
    global _openai, _model
    cfg = load_model_config(config_path)
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError(
            "WORLDKERNEL_API_KEY is not set. "
            "Copy .env.example to .env and fill in your API key."
        )
    _openai = AsyncOpenAI(api_key=api_key, base_url=cfg.get("base_url"))
    _model = cfg["model"]


async def chat(prompt: str, system: str = "") -> str:
    assert _openai is not None, "llm.client not initialized — call init() first"
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = await _openai.chat.completions.create(model=_model, messages=messages)
    return resp.choices[0].message.content or ""


async def chat_json(prompt: str, system: str = "") -> str:
    """调用 LLM 并返回清洗后的 JSON 字符串，自动剥离 markdown 代码块。"""
    raw = await chat(prompt, system)
    return _extract_json(raw)


def _extract_json(text: str) -> str:
    """从 LLM 输出中提取第一个完整的 JSON 对象或数组。"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()
    # 找到最先出现的 { 或 [，以位置靠前者为准
    first_brace = text.find('{')
    first_bracket = text.find('[')
    if first_brace == -1 and first_bracket == -1:
        return text
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        open_ch, close_ch, start = '[', ']', first_bracket
    else:
        open_ch, close_ch, start = '{', '}', first_brace
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                result = text[start:i + 1]
                result = re.sub(r',\s*([}\]])', r'\1', result)
                return _repair_json(result)
    return text


def _repair_json(text: str) -> str:
    """修复 LLM 输出中常见的 JSON 格式错误。

    处理的问题：
    - 数值后紧跟非 JSON 文本：``80（每座温室大约20-30盆植物）`` → ``80``
    """
    # 数值后面紧跟的非 JSON 合法字符全部剥离，包括可能的尾部多余引号
    text = re.sub(
        r'(?<=: )(-?\d+(?:\.\d+)?)[^,\]}\"]*"?',
        r'\1',
        text,
    )
    return text
