"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    danger_level: str = ""  # world-specific
    function_tags: str = ""  # world-specific
    jurisdiction: str = ""  # world-specific
    significance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    public_access: str = ""  # world-specific
    min_luck_level: str = ""  # world-specific
    requires_clearance: str = ""  # world-specific
    time_restriction: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    infestation_level: str = ""  # world-specific
    security_state: str = ""  # world-specific
    resource_stockpile: str = ""  # world-specific
    anomalies: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
