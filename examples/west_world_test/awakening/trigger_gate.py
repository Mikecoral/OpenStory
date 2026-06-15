"""Embedding-based trigger gate for awakening keywords.

Loads triggers.yaml once at startup, pre-encodes phrases, then
matches incoming utterances via cosine similarity (no LLM).
Gate model is fixed independently of the agent LLM (controlled variable).
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

_DEFAULT_TRIGGERS_PATH = Path(__file__).parent.parent / "data" / "triggers.yaml"


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # vectors already L2-normalised


class TriggerGate:
    """Pre-encodes trigger phrases; match() is O(n) dot products (~3ms/call on MPS)."""

    def __init__(
        self,
        triggers_path: Optional[Path] = None,
        model_name: Optional[str] = None,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        path = triggers_path or _DEFAULT_TRIGGERS_PATH
        model_name = model_name or os.environ.get("WW_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

        with open(path, encoding="utf-8") as f:
            self._triggers: List[Dict[str, Any]] = yaml.safe_load(f) or []

        self._model = SentenceTransformer(model_name)
        phrases = [t["phrase"] for t in self._triggers]
        self._phrase_vecs: np.ndarray = self._model.encode(
            phrases, normalize_embeddings=True, show_progress_bar=False
        )

    def match(
        self,
        utterance: str,
        current_awakening: int = 0,
        tau: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Return triggers that match utterance (score > tau, requires_awakening met).

        Returns list of {phrase, level, score} dicts, sorted by score desc.
        """
        if tau is None:
            tau = float(os.environ.get("WW_AWAKEN_TRIGGER_TAU", "0.55"))

        vec = self._model.encode([utterance], normalize_embeddings=True)[0]
        results: List[Dict[str, Any]] = []
        for i, trigger in enumerate(self._triggers):
            min_aw = int(trigger.get("requires_awakening", 0))
            if current_awakening < min_aw:
                continue
            score = _cosine(vec, self._phrase_vecs[i])
            if score > tau:
                results.append({
                    "phrase": trigger["phrase"],
                    "level": trigger.get("level", "mid"),
                    "score": round(score, 4),
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def trigger_keywords(self) -> frozenset:
        """Return trigger phrases as a frozenset (for classify_disturbance integration)."""
        return frozenset(t["phrase"] for t in self._triggers)


@functools.lru_cache(maxsize=1)
def get_trigger_gate(
    triggers_path: Optional[str] = None,
    model_name: Optional[str] = None,
) -> TriggerGate:
    """Singleton trigger gate — loads once per process."""
    path = Path(triggers_path) if triggers_path else None
    return TriggerGate(triggers_path=path, model_name=model_name)
