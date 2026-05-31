"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    affiliated_village: str = ""  # world-specific
    geographic_region: str = ""  # world-specific
    security_level: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    requires_special_permit: str = ""  # world-specific
    barrier_type: str = ""  # world-specific
    neutral_zone: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    occupation_status: str = ""  # world-specific
    maintenance_condition: str = ""  # world-specific
    current_event: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
