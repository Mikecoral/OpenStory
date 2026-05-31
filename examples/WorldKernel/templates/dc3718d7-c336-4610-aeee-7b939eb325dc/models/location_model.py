"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    is_contested_zone: str = ""  # world-specific
    secret_purpose: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    current_occupant_faction: str = ""  # world-specific
    known_alias: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    curfew_applies: str = ""  # world-specific
    required_password_or_charm: str = ""  # world-specific
    patrolled_by_deatheaters: str = ""  # world-specific
    restricted_hours: str = ""  # world-specific
    emergency_exit_available: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    physical_integrity: str = ""  # world-specific
    magical_ward_status: str = ""  # world-specific
    functional_alteration: str = ""  # world-specific
    current_usage_intensity: str = ""  # world-specific
    secret_modifications: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
