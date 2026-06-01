"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    hidden: str = ""  # world-specific
    monitored: str = ""  # world-specific
    magical_properties: str = ""  # world-specific
    requires_magic: str = ""  # world-specific
    known_to_resistance: str = ""  # world-specific
    known_to_death_eaters: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    secret_route: str = ""  # world-specific
    requires_password: str = ""  # world-specific
    password: str = ""  # world-specific
    associated_map: str = ""  # world-specific
    one_way_if_condition: str = ""  # world-specific
    escape_route: str = ""  # world-specific
    blocked_by_enemy: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    curfew_restricted: str = ""  # world-specific
    patrolled: str = ""  # world-specific
    safe_house: str = ""  # world-specific
    trap: str = ""  # world-specific
    visibility: str = ""  # world-specific
    detection_charm: str = ""  # world-specific
    permission_needed: str = ""  # world-specific
    emergency_disable: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
