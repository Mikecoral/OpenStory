"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    secret_name: str = ""  # world-specific
    faction: str = ""  # world-specific
    is_known_to_enemy: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    secret_entry: str = ""  # world-specific
    monitored_end: str = ""  # world-specific
    alternate_end: str = ""  # world-specific
    guard_post_nearby: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    magical_properties: str = ""  # world-specific
    environment: str = ""  # world-specific
    noise_level: str = ""  # world-specific
    scent: str = ""  # world-specific
    traps_exist: str = ""  # world-specific
    mood: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    patrol_frequency: str = ""  # world-specific
    curfew_restriction: str = ""  # world-specific
    detection_charm: str = ""  # world-specific
    required_password: str = ""  # world-specific
    emergency_exit: str = ""  # world-specific
    signal_required: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
