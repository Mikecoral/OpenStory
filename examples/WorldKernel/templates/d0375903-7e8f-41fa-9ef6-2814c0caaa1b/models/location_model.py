"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    symbolic_meaning: str = ""  # world-specific
    associated_plot_events: str = ""  # world-specific
    historical_literary_reference: str = ""  # world-specific
    custom_function: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    social_hierarchy_level: str = ""  # world-specific
    specific_access_rules: str = ""  # world-specific
    ceremonial_use_restriction: str = ""  # world-specific
    seasonal_access_conditions: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    current_event_occurring: str = ""  # world-specific
    maintenance_status: str = ""  # world-specific
    significance_state: str = ""  # world-specific
    administrator_person_id: str = ""  # world-specific
    ritual_owner_person_id: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
