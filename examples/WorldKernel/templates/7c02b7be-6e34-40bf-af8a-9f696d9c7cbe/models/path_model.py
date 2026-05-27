"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    is_secret_passage: str = ""  # world-specific
    known_by_faction: str = ""  # world-specific
    detection_risk_level: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    guarded_by: str = ""  # world-specific
    has_warded_entrance: str = ""  # world-specific
    requires_verbal_passphrase: str = ""  # world-specific
    alarm_trigger_condition: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    is_magical: str = ""  # world-specific
    requires_invisibility_cloak: str = ""  # world-specific
    monitored_by_spells: str = ""  # world-specific
    mobility_restriction: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    curfew_safety: str = ""  # world-specific
    caroport_restriction: str = ""  # world-specific
    is_trapped: str = ""  # world-specific
    resistance_use_only: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
