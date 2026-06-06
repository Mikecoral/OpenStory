"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    emotional_aura: str = ""  # world-specific
    associated_characters: str = ""  # world-specific
    historical_period: str = ""  # world-specific
    narrative_significance: str = ""  # world-specific
    symbolic_theme: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    visiting_hours: str = ""  # world-specific
    entry_ritual: str = ""  # world-specific
    seasonal_availability: str = ""  # world-specific
    social_restrictions: str = ""  # world-specific
    psychological_barrier: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    atmospheric_condition: str = ""  # world-specific
    occupancy_rate: str = ""  # world-specific
    maintenance_level: str = ""  # world-specific
    temporal_phase: str = ""  # world-specific
    weather_affinity: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
