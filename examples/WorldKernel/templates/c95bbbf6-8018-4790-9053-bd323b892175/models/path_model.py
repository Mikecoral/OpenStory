"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    discovered_by: str = ""  # world-specific
    used_for: str = ""  # world-specific
    alias: str = ""  # world-specific
    secret_passage: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    secret_exit: str = ""  # world-specific
    monitored: str = ""  # world-specific
    requires_communication: str = ""  # world-specific
    hidden_entrance: str = ""  # world-specific
    connected_to_secret_room: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    time_restriction: str = ""  # world-specific
    curse_protection: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific
    password: str = ""  # world-specific
    is_monitored: str = ""  # world-specific
    magical_ward: str = ""  # world-specific
    requires_permission: str = ""  # world-specific
    noise_check: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
