"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    safety_level: str = ""  # world-specific
    hidden_passages: str = ""  # world-specific
    dark_magic_contamination: str = ""  # world-specific
    resistance_activity_use: str = ""  # world-specific
    historical_event_marker: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    surveillance_level: str = ""  # world-specific
    password_required: str = ""  # world-specific
    alarm_charms: str = ""  # world-specific
    entry_restrictions_by_faction: str = ""  # world-specific
    cursed_entries: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    hidden_functionality: str = ""  # world-specific
    damage_level: str = ""  # world-specific
    soul_fragment_influence: str = ""  # world-specific
    prisoner_hideout: str = ""  # world-specific
    functional_alteration_by_deatheaters: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
