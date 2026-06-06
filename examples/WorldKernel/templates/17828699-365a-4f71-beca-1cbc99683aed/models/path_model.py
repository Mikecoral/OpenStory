"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    atmosphere_description: str = ""  # world-specific
    time_period_feel: str = ""  # world-specific
    cultural_reference: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    seasonal_variation: str = ""  # world-specific
    lighting_condition: str = ""  # world-specific
    soundscape: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    encounter_probability: str = ""  # world-specific
    narrative_memory_weight: str = ""  # world-specific
    weather_dependency: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
