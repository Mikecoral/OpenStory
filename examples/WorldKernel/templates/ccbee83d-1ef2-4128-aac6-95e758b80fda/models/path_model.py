"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    emotional_imprint: str = ""  # world-specific
    time_period_association: str = ""  # world-specific
    narrative_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    visual_atmosphere: str = ""  # world-specific
    usage_frequency: str = ""  # world-specific
    memory_bond_location: str = ""  # world-specific
    length_category: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    psychological_barrier: str = ""  # world-specific
    weather_sensitivity: str = ""  # world-specific
    time_of_day_restriction: str = ""  # world-specific
    symbolic_function: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
