"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    era_decade: str = ""  # world-specific
    cultural_vibe: str = ""  # world-specific
    soundtrack_genre: str = ""  # world-specific
    associated_memory: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    seasonal_hours: str = ""  # world-specific
    rain_days_closed: str = ""  # world-specific
    regular_crowd_type: str = ""  # world-specific
    invitation_required: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    hourly_atmosphere: str = ""  # world-specific
    current_occupancy_feel: str = ""  # world-specific
    maintenance_level: str = ""  # world-specific
    lingering_note: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
