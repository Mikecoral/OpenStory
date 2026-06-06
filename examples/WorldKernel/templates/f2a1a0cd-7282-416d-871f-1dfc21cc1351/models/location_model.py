"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    symbolic_name: str = ""  # world-specific
    threshold_type: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    supernatural_property: str = ""  # world-specific
    metaphorical_role: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    entry_ritual: str = ""  # world-specific
    weather_requirement: str = ""  # world-specific
    time_of_day_requirement: str = ""  # world-specific
    psychic_state_requirement: str = ""  # world-specific
    invisible_guardian: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    reality_stability: str = ""  # world-specific
    echo_intensity: str = ""  # world-specific
    spiritual_temperature: str = ""  # world-specific
    temporal_anomaly: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
