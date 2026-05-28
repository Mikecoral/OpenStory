"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    secret_passage: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    atmosphere_description: str = ""  # world-specific
    associated_resistance_network: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    endpoint_surveillance: str = ""  # world-specific
    connection_type_description: str = ""  # world-specific
    is_guarded: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    stealth_travel_suitability: str = ""  # world-specific
    magical_enhancements: str = ""  # world-specific
    visibility_under_detection_charm: str = ""  # world-specific
    acoustic_privacy: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    required_skills: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    password_or_charm: str = ""  # world-specific
    associated_rule_ids: str = ""  # world-specific
    activation_trigger: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
