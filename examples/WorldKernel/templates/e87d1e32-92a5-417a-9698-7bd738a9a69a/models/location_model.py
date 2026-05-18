"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    user_type: str = ""  # world-specific
    associated_character: str = ""  # world-specific
    literary_reference: str = ""  # world-specific
    ritual_significance: str = ""  # world-specific
    name_origin_poem: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    time_restriction: str = ""  # world-specific
    gender_restriction: str = ""  # world-specific
    rank_requirement: str = ""  # world-specific
    special_event_only: str = ""  # world-specific
    guest_permission: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    seasonal_aspect: str = ""  # world-specific
    maintenance_level: str = ""  # world-specific
    spiritual_state: str = ""  # world-specific
    historic_event: str = ""  # world-specific
    current_usage_status: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
