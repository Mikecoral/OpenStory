"""Deterministic ground-truth state machine for the recorder comparison."""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .schema import Event

INITIAL_STATE: Dict[str, Any] = {
    "glasses_intact": 3,
    "glass_shards": False,
    "wanted_poster": "on_wall",
    "photo": {"pos": "floor", "held_by": None, "hidden": False},
    "piano": "playing",
    "revolver": {"pos": "table", "held_by": None, "fired": False},
    "door": "closed",
}


class OracleState:
    def __init__(self) -> None:
        self.state = copy.deepcopy(INITIAL_STATE)
        self.event_log: List[Event] = []

    def apply(self, event: Event) -> None:
        self.event_log.append(event)
        if event.action == "pour_whiskey":
            self.state["glasses_intact"] = max(0, self.state["glasses_intact"] - 1)
        elif event.action == "smash_glass":
            self.state["glasses_intact"] = max(0, self.state["glasses_intact"] - 1)
            self.state["glass_shards"] = True
        elif event.action == "pick_up_photo":
            self.state["photo"].update(pos="held", held_by=event.actor, hidden=event.visibility == "hidden")
        elif event.action == "take_poster":
            self.state["wanted_poster"] = "taken"
        elif event.action == "tear_poster":
            self.state["wanted_poster"] = "torn"
        elif event.action == "stop_piano":
            self.state["piano"] = "stopped"
        elif event.action == "take_revolver":
            self.state["revolver"].update(pos="held", held_by=event.actor)
        elif event.action == "fire_revolver":
            self.state["revolver"]["fired"] = True
        elif event.action == "open_door":
            self.state["door"] = "open"
