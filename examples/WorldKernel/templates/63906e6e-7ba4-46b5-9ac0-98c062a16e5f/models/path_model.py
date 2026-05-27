"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    known_as: str = ""  # world-specific
    is_secret: str = ""  # world-specific
    is_monitored: str = ""  # world-specific
    is_cursed: str = ""  # world-specific
    affiliated_group: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    has_secret_entrance: str = ""  # world-specific
    requires_password: str = ""  # world-specific
    passage_type: str = ""  # world-specific
    is_blocked: str = ""  # world-specific
    alternate_endpoints: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    lighting_condition: str = ""  # world-specific
    noise_level: str = ""  # world-specific
    magical_ward: str = ""  # world-specific
    is_spider_infested: str = ""  # world-specific
    dimensional_stability: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    curfew_restriction: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific
    escape_route: str = ""  # world-specific
    required_permission: str = ""  # world-specific
    last_checked: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
