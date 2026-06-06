"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    surveillance_level: str = ""  # world-specific
    is_hidden: str = ""  # world-specific
    access_limit_per_day: str = ""  # world-specific
    code_name: str = ""  # world-specific
    zone_id: str = ""  # world-specific
    camouflage_type: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    connection_type: str = ""  # world-specific
    key_required: str = ""  # world-specific
    biometric_required: str = ""  # world-specific
    has_trap: str = ""  # world-specific
    is_reversible: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    required_character_type: str = ""  # world-specific
    required_time_window: str = ""  # world-specific
    required_game_clear: str = ""  # world-specific
    required_stamina: str = ""  # world-specific
    required_sanity: str = ""  # world-specific
    max_passengers_per_time: str = ""  # world-specific
    triggers_alarm: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
