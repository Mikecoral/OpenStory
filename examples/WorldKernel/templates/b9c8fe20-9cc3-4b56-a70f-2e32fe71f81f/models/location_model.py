"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    affiliation: str = ""  # world-specific
    hidden_function: str = ""  # world-specific
    is_secret: str = ""  # world-specific
    lore_significance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    curfew_status: str = ""  # world-specific
    password_required: str = ""  # world-specific
    danger_level: str = ""  # world-specific
    lock_type: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    safety_level: str = ""  # world-specific
    magical_barrier: str = ""  # world-specific
    current_activity: str = ""  # world-specific
    damage_level: str = ""  # world-specific
    residual_magic: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
