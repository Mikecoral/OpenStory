"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    usage_level: str = ""  # world-specific
    symbolic_significance: str = ""  # world-specific
    associated_items: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    security_level: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    secret_passage: str = ""  # world-specific
    jurisdiction_owner: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    weather_effect: str = ""  # world-specific
    cleaning_status: str = ""  # world-specific
    guard_presence: str = ""  # world-specific
    religious_fix: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
