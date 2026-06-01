"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    belongs_to_estate: str = ""  # world-specific
    symbolic_meaning: str = ""  # world-specific
    key_plot_events: str = ""  # world-specific
    literary_imagery: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    access_scope: str = ""  # world-specific
    gender_restriction: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    special_event_access: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    seasonal_state: str = ""  # world-specific
    maintenance_condition: str = ""  # world-specific
    function_changed: str = ""  # world-specific
    current_resident: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
