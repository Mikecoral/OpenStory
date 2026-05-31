"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    mythological_layer: str = ""  # world-specific
    narrative_function: str = ""  # world-specific
    associated_objects: str = ""  # world-specific
    symbolic_meaning: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    immortal_access_condition: str = ""  # world-specific
    mortal_perception: str = ""  # world-specific
    time_constraint: str = ""  # world-specific
    special_entrance_requirement: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    seasonal_state: str = ""  # world-specific
    atmosphere: str = ""  # world-specific
    temporal_markers: str = ""  # world-specific
    functional_cycle: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
