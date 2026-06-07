"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    spatial_hierarchy: str = ""  # world-specific
    celestial_bureau: str = ""  # world-specific
    restriction_level: str = ""  # world-specific
    associated_event: str = ""  # world-specific
    mythical_significance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    required_token: str = ""  # world-specific
    guard_type: str = ""  # world-specific
    unlock_condition: str = ""  # world-specific
    teleport_array: str = ""  # world-specific
    banishment_proof: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    integrity_level: str = ""  # world-specific
    spiritual_energy: str = ""  # world-specific
    combat_state: str = ""  # world-specific
    fortification_status: str = ""  # world-specific
    contamination_level: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
