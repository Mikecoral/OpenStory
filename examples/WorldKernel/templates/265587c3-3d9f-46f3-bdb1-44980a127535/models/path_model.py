"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    security_level: str = ""  # world-specific
    hidden_feature: str = ""  # world-specific
    atmosphere: str = ""  # world-specific
    is_secret_passage: str = ""  # world-specific
    requires_permit: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    monitored_by: str = ""  # world-specific
    connects_to_restricted_area: str = ""  # world-specific
    escape_route_for_resistance: str = ""  # world-specific
    traverses_house_territory: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    curfew_restriction: str = ""  # world-specific
    required_house_permission: str = ""  # world-specific
    punishable_if_caught: str = ""  # world-specific
    invisibility_cloak_needed: str = ""  # world-specific
    password_required: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
