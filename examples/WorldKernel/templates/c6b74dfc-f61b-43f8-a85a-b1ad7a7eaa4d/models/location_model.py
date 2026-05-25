"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    affiliation: str = ""  # world-specific
    hidden_purpose: str = ""  # world-specific
    key_event: str = ""  # world-specific
    related_to_horcrux: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    password_required: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    alarm_system: str = ""  # world-specific
    death_eater_patrol: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    temporary_defense: str = ""  # world-specific
    damage_status: str = ""  # world-specific
    secret_gathering: str = ""  # world-specific
    hidden_objects: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
