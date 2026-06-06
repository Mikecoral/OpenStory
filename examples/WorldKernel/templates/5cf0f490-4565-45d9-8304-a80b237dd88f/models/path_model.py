"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    karma_index: str = ""  # world-specific
    is_hidden_passage: str = ""  # world-specific
    barrier_type: str = ""  # world-specific
    terrain_feature: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    unlock_condition: str = ""  # world-specific
    is_hidden: str = ""  # world-specific
    directional_restriction: str = ""  # world-specific
    temporal_availability: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    soul_power_suppression_level: str = ""  # world-specific
    emotional_trial_required: str = ""  # world-specific
    time_limit_seconds: str = ""  # world-specific
    abyss_corruption_level: str = ""  # world-specific
    requires_karma_pass: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
