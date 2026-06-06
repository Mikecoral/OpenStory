"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    has_supernatural_connection: str = ""  # world-specific
    symbolic_meaning: str = ""  # world-specific
    associated_character: str = ""  # world-specific
    is_threshold_space: str = ""  # world-specific
    time_paradox: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    requires_solitude: str = ""  # world-specific
    secret_entrance_condition: str = ""  # world-specific
    supernatural_gateway: str = ""  # world-specific
    restricted_to_certain_roles: str = ""  # world-specific
    emotional_prerequisite: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    temporal_anomaly: str = ""  # world-specific
    material_instability: str = ""  # world-specific
    ambient_feeling: str = ""  # world-specific
    supernatural_activity_level: str = ""  # world-specific
    metaphysical_cycle: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
