"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    security_level: str = ""  # world-specific
    faction_allegiance: str = ""  # world-specific
    has_secret_passage: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    secret_function: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    password_required: str = ""  # world-specific
    special_permission_required: str = ""  # world-specific
    magical_barrier_type: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    secret_entry_available: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    usage_status: str = ""  # world-specific
    maintenance_condition: str = ""  # world-specific
    defensive_spells: str = ""  # world-specific
    lighting_condition: str = ""  # world-specific
    curse_status: str = ""  # world-specific
    occupancy_status: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
