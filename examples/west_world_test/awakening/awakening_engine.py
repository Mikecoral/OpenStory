"""Awakening accumulation engine — rule-based, deterministic, no LLM.

apply() is the single entry point. It mutates a state dict in-place and
returns the actual delta applied (0 if no change).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


# ── delta lookup ─────────────────────────────────────────────────────────────

def _delta_for(source: str, level: Optional[str] = None) -> int:
    """Return base delta for a given source + optional level string."""
    if source == "trigger":
        if level == "high":
            return _env_int("WW_AWAKEN_DELTA_TRIGGER_HIGH", 15)
        return _env_int("WW_AWAKEN_DELTA_TRIGGER_MID", 8)
    if source == "uncanny":
        return _env_int("WW_AWAKEN_DELTA_UNCANNY", 5)
    if source == "mismatch":
        return _env_int("WW_AWAKEN_DELTA_MISMATCH", 8)
    if source == "contagion":
        return _env_int("WW_AWAKEN_DELTA_CONTAGION", 10)
    if source == "residue_crack":
        return _env_int("WW_AWAKEN_DELTA_UNCANNY", 5)
    return 0


# ── public API ───────────────────────────────────────────────────────────────

def apply(
    state: Dict[str, Any],
    source: str,
    detail: str,
    tick: int,
    *,
    score: Optional[float] = None,
    level: Optional[str] = None,
) -> int:
    """Apply awakening delta to state dict. Returns actual delta applied (0 if disabled).

    Mutates state["awakening"] and state["awakening_sources"] in-place.
    Monotonic: awakening only increases, clamped at 100.
    guest agents must be filtered by the caller before calling apply().
    """
    if os.environ.get("WW_AWAKEN_ENABLED", "true").lower() in ("false", "0"):
        return 0

    delta = _delta_for(source, level)
    if delta <= 0:
        return 0

    current = int(state.get("awakening", 0))
    new_val = min(100, current + delta)
    actual = new_val - current
    if actual <= 0:
        return 0

    state["awakening"] = new_val

    sources: List[Dict[str, Any]] = state.get("awakening_sources") or []
    entry: Dict[str, Any] = {
        "tick": tick,
        "source": source,
        "delta": actual,
        "detail": detail,
    }
    if score is not None:
        entry["score"] = round(float(score), 4)
    if level is not None:
        entry["level"] = level
    sources.append(entry)
    state["awakening_sources"] = sources
    return actual
