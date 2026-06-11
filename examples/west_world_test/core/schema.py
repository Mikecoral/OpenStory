"""Core data models and JSONL loaders for the recorder comparison."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    tick: int
    actor: str
    action: str
    target: str
    visibility: str = "public"
    id: Optional[str] = None
    affected_probe_ids: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            tick=int(data["tick"]),
            actor=data["actor"],
            action=data["action"],
            target=data["target"],
            visibility=data.get("visibility", "public"),
            id=data.get("id"),
            affected_probe_ids=tuple(data.get("affected_probe_ids", ())),
        )


@dataclass
class Probe:
    id: str
    kind: str
    text: str
    answer_type: str
    field: Optional[str] = None
    equals: Optional[Any] = None
    subject: Optional[str] = None
    fact_event_id: Optional[str] = None
    score_group: str = "visual_physical"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Probe":
        return cls(
            id=data["id"],
            kind=data["kind"],
            text=data["text"],
            answer_type=data.get("answer_type", "str"),
            field=data.get("field"),
            equals=data.get("equals"),
            subject=data.get("subject"),
            fact_event_id=data.get("fact_event_id"),
            score_group=data.get("score_group", "visual_physical"),
        )


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_events(path: str) -> List[Event]:
    return [Event.from_dict(row) for row in _load_jsonl(path)]


def load_probes(path: str) -> List[Probe]:
    return [Probe.from_dict(row) for row in _load_jsonl(path)]
