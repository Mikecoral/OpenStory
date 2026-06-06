"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    path_symbol: str = ""  # world-specific
    path_realm_type: str = ""  # world-specific
    is_cursed: str = ""  # world-specific
    metaphor_theme: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    is_portal: str = ""  # world-specific
    portal_type: str = ""  # world-specific
    requires_special_item: str = ""  # world-specific
    has_guardian: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    requires_emotional_state: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    weather_condition: str = ""  # world-specific
    spatial_anomaly: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
