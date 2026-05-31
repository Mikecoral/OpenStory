"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    region: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    secret_type: str = ""  # world-specific
    occupier_status: str = ""  # world-specific
    is_signposted: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    password_required: str = ""  # world-specific
    cursed_entry: str = ""  # world-specific
    monitoring_level: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    invisibility_required: str = ""  # world-specific
    alarm_triggered: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    condition_status: str = ""  # world-specific
    garrison_count: str = ""  # world-specific
    hidden_feature_available: str = ""  # world-specific
    evidence_of_resistance: str = ""  # world-specific
    curfew_applicable: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
