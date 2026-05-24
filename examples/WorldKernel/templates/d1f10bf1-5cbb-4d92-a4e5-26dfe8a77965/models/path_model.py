"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    secret_name: str = ""  # world-specific
    passage_type: str = ""  # world-specific
    is_under_surveillance: str = ""  # world-specific
    has_been_tampered: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    requires_password: str = ""  # world-specific
    time_restricted: str = ""  # world-specific
    is_blocked: str = ""  # world-specific
    password_required_direction: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    magical_property: str = ""  # world-specific
    has_trap: str = ""  # world-specific
    is_enchanted: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    password: str = ""  # world-specific
    identification_method: str = ""  # world-specific
    requires_invisibility: str = ""  # world-specific
    special_exemption: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
