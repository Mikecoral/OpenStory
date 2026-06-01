from __future__ import annotations

import re
from pathlib import Path

from openai import AsyncOpenAI

from worldkernel.llm.config_loader import load_model_config

_openai: AsyncOpenAI | None = None
_model: str = ""
_default_max_tokens: int | None = None  # None = 不限制，让 API 自然生成到 finish=stop


def init(config_path: Path) -> None:
    global _openai, _model, _default_max_tokens
    cfg = load_model_config(config_path)
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError(
            "WORLDKERNEL_API_KEY is not set. "
            "Copy .env.example to .env and fill in your API key."
        )
    _openai = AsyncOpenAI(api_key=api_key, base_url=cfg.get("base_url"))
    _model = cfg["model"]
    # max_tokens: 0 或不设置 = 不限制；正整数 = 限制
    cfg_max = cfg.get("max_tokens")
    _default_max_tokens = cfg_max if cfg_max and cfg_max > 0 else None


async def chat(prompt: str, system: str = "", max_tokens: int | None = None) -> str:
    import logging as _logging
    _log = _logging.getLogger("worldkernel.llm")

    assert _openai is not None, "llm.client not initialized — call init() first"
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    effective_max_tokens = max_tokens or _default_max_tokens

    # 估算 prompt 总字符数（用于调试截断问题）
    prompt_chars = sum(len(m.get("content", "")) for m in messages)
    if prompt_chars > 8000:
        _log.info(
            "LLM prompt is large: %d chars (~%d tokens), model=%s",
            prompt_chars, prompt_chars // 3, _model,
        )

    try:
        # DeepSeek v4 Flash 的 OpenAI 兼容接口中，
        # max_tokens 会导致 finish=length 且 content 为空，
        # 必须使用 max_completion_tokens。
        # 不传该参数 = 不限制，API 自然生成到 finish=stop。
        create_kwargs: dict = dict(model=_model, messages=messages)
        if effective_max_tokens is not None:
            create_kwargs["max_completion_tokens"] = effective_max_tokens
        resp = await _openai.chat.completions.create(**create_kwargs)
    except Exception as exc:
        raise RuntimeError(f"LLM API call failed: {exc}") from exc

    content = resp.choices[0].message.content if resp.choices else ""
    if not content or not content.strip():
        raise RuntimeError(
            f"LLM returned empty response. model={_model}, "
            f"prompt_preview={prompt[:100]!r}..."
        )

    # 详细日志：finish_reason + usage
    finish_reason = resp.choices[0].finish_reason if resp.choices else ""
    usage = resp.usage
    if usage:
        _log.debug(
            "LLM call: model=%s max_tokens=%s finish=%s prompt=%d completion=%d total=%d",
            _model, effective_max_tokens or "unlimited", finish_reason,
            usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        )
    else:
        _log.debug(
            "LLM call: model=%s max_tokens=%s finish=%s (no usage info)",
            _model, effective_max_tokens or "unlimited", finish_reason,
        )

    if finish_reason == "length":
        _log.warning(
            "LLM response TRUNCATED (finish_reason=length). "
            "max_tokens=%d, model=%s, prompt_tokens=%s, completion_tokens=%s. "
            "Consider reducing batch_size or increasing max_tokens in configs/models.yaml.",
            effective_max_tokens, _model,
            getattr(usage, 'prompt_tokens', '?'),
            getattr(usage, 'completion_tokens', '?'),
        )

    return content


async def chat_json(prompt: str, system: str = "", max_tokens: int | None = None) -> str:
    """调用 LLM 并返回清洗后的 JSON 字符串，自动剥离 markdown 代码块。"""
    raw = await chat(prompt, system, max_tokens=max_tokens)
    return _extract_json(raw)


def _extract_json(text: str) -> str:
    """从 LLM 输出中提取第一个完整的 JSON 对象或数组，自动修复常见格式错误。"""
    import json as _json

    text = text.strip()
    # 剥离 markdown 代码块
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

    # 括号匹配提取
    depth = 0
    result = text[start:]
    truncated = True
    for i, ch in enumerate(text[start:], start):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                result = text[start:i + 1]
                truncated = False
                break

    # 截断恢复：补全未闭合的字符串和括号
    if truncated:
        result = _recover_truncated_json(result, open_ch, close_ch)

    # 逐步修复并尝试解析
    for attempt in range(7):
        try:
            _json.loads(result)
            return result
        except _json.JSONDecodeError:
            result = _repair_json_step(result, attempt)

    # 最后一次尝试
    try:
        _json.loads(result)
    except _json.JSONDecodeError:
        pass
    return result


def _recover_truncated_json(text: str, open_ch: str, close_ch: str) -> str:
    """尝试恢复被截断的 JSON。

    策略：从后往前扫描，找到最后一个完整元素的边界，
    截断掉不完整的尾部，然后补全括号。
    """
    import json as _json

    # 1. 尝试直接补全括号（最简单的情况：只是最后一个括号没闭合）
    quick_fix = _try_close_brackets(text)
    try:
        _json.loads(quick_fix)
        return quick_fix
    except _json.JSONDecodeError:
        pass

    # 2. 从后往前找到最后一个合法的截断点
    #    在数组中，找到最后一个完整的 }, 或 ] 位置
    #    在对象中，找到最后一个完整的 "value", 或 } 位置
    best = _find_last_complete_boundary(text, open_ch, close_ch)
    if best is not None and best > 0:
        truncated = text[:best]
        fixed = _try_close_brackets(truncated)
        try:
            _json.loads(fixed)
            return fixed
        except _json.JSONDecodeError:
            pass

    # 3. 兜底：逐字符截断，尝试找到最长可解析前缀
    for i in range(len(text) - 1, 0, -1):
        ch = text[i]
        if ch in ('}', ']', '"', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'e', 'l'):
            candidate = text[:i + 1]
            fixed = _try_close_brackets(candidate)
            try:
                _json.loads(fixed)
                return fixed
            except _json.JSONDecodeError:
                continue

    # 4. 最终兜底：原始文本 + 补全括号
    return _try_close_brackets(text)


def _try_close_brackets(text: str) -> str:
    """补全未闭合的括号（不处理字符串截断）。"""
    bracket_stack = []
    in_str = False
    esc = False
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            bracket_stack.append(ch)
        elif ch == '}' and bracket_stack and bracket_stack[-1] == '{':
            bracket_stack.pop()
        elif ch == ']' and bracket_stack and bracket_stack[-1] == '[':
            bracket_stack.pop()

    result = text.rstrip()
    # 去除尾部逗号
    result = re.sub(r',\s*$', '', result)
    close_map = {'{': '}', '[': ']'}
    for bracket in reversed(bracket_stack):
        result += close_map.get(bracket, '')
    return result


def _find_last_complete_boundary(text: str, open_ch: str, close_ch: str) -> int | None:
    """从后往前扫描，找到最后一个完整 JSON 元素的结束位置。

    对于数组 [a, b, c]：找到最后一个 }, 或 ] 的位置
    对于对象 {k: v}：找到最后一个 }, 的位置
    """
    # 从后往前找 close_ch 或 }, 的位置
    depth = 0
    in_str = False
    esc = False
    # 先用正向扫描记录每个 } 或 ] 的嵌套深度
    positions = []  # (index, char, depth_at_close)
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            depth += 1
        elif ch == '}':
            positions.append((i, '}', depth))
            depth -= 1
        elif ch == ']':
            positions.append((i, ']', depth))
            depth -= 1

    # 从后往前，找第一个 depth==1 的 }（即顶层数组/对象内的最后一个完整元素）
    for idx, ch, d in reversed(positions):
        if d == 1 and ch == '}':
            # 找到 }, 的位置，返回逗号之后的位置
            after = text[idx + 1:].lstrip()
            if after.startswith(','):
                return idx + 1 + (len(text[idx + 1:]) - len(text[idx + 1:].lstrip())) + 1
            return idx + 1
    return None


def _repair_json_step(text: str, step: int) -> str:
    """按步骤逐步修复 JSON，每步处理一类常见错误。"""
    if step == 0:
        # 最高优先级：转义 JSON 字符串值内的控制字符（\n \r \t 等）
        # 必须在其他修复之前执行，否则控制字符会导致 json.loads 失败
        text = _escape_control_chars_in_strings(text)
    elif step == 1:
        # 去除尾部逗号：,} → } , ] → ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
    elif step == 2:
        # 数值后紧跟非 JSON 文本：80（注释）→ 80
        # 不跨行匹配，避免吞掉换行后的下一个 key
        # 冒号后可选空格，用非捕获组替代 lookbehind
        text = re.sub(
            r':\s*(-?\d+(?:\.\d+)?)[^,\]}\n\"]*"?',
            lambda m: ':' + m.group(1),
            text,
        )
    elif step == 3:
        # 去除行尾注释：// ... 或 # ...
        text = re.sub(r'//[^\n]*', '', text)
        text = re.sub(r'#[^\n]*', '', text)
        text = re.sub(r',\s*([}\]])', r'\1', text)
    elif step == 4:
        # 单引号 → 双引号（简单替换，不处理嵌套）
        text = re.sub(r"'([^']*)'", r'"\1"', text)
        text = re.sub(r',\s*([}\]])', r'\1', text)
    elif step == 5:
        # 补缺失的逗号：在 }" 或数字后面紧跟 "key" 时插入逗号
        # 匹配：值结尾（"、数字、}、]）后紧跟可选空白和 "key":
        text = re.sub(
            r'(["\d}\]])\s*\n?\s*(")',
            lambda m: f'{m.group(1)},\n  {m.group(2)}',
            text,
        )
        text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _escape_control_chars_in_strings(text: str) -> str:
    """转义 JSON 字符串值内部的裸控制字符（\n \r \t 等）。

    LLM 有时会在 description 等长字符串中输出真实的换行符，
    但 JSON 规范要求字符串内的换行必须写成 \\n。
    """
    result: list[str] = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string:
            if ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            elif ord(ch) < 0x20:  # 其他控制字符
                result.append(f'\\u{ord(ch):04x}')
            else:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)
