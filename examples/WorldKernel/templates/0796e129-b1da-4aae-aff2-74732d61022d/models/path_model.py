"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    magical_properties: str = ""  # world-specific
    is_moving: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    alternate_names: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    intermediate_points: str = ""  # world-specific
    connection_visibility: str = ""  # world-specific
    portal_type: str = ""  # world-specific
    distance_or_time: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    activation_condition: str = ""  # world-specific
    failure_effect: str = ""  # world-specific
    protective_spells: str = ""  # world-specific
    tracking: str = ""  # world-specific
    illusion: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
