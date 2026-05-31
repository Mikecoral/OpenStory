"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    is_secret: str = ""  # world-specific
    currently_active: str = ""  # world-specific
    known_to_carers: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    requires_password: str = ""  # world-specific
    requires_specific_item: str = ""  # world-specific
    is_monitored: str = ""  # world-specific
    has_threshold_enchantment: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    blood_status_restriction: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    curfew_penalty: str = ""  # world-specific
    detection_risk: str = ""  # world-specific
    requires_concealment_spell: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
