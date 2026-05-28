"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    dark_alias: str = ""  # world-specific
    symbolic_significance: str = ""  # world-specific
    resistance_code_name: str = ""  # world-specific
    occupied_purpose: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    surveillance_spells: str = ""  # world-specific
    secret_passages: str = ""  # world-specific
    alert_level: str = ""  # world-specific
    curfew_restriction: str = ""  # world-specific
    blood_status_checkpoint: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    atmosphere_index: str = ""  # world-specific
    damage_level: str = ""  # world-specific
    temporary_purpose: str = ""  # world-specific
    occupation_stage: str = ""  # world-specific
    terror_rating: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
