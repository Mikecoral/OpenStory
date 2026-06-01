"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    belongs_to_household: str = ""  # world-specific
    path_type: str = ""  # world-specific
    is_inside_garden: str = ""  # world-specific
    hierarchy_rank: str = ""  # world-specific
    connected_courtyard: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    physical_form: str = ""  # world-specific
    traffic_restriction: str = ""  # world-specific
    guarded_by: str = ""  # world-specific
    ritual_use: str = ""  # world-specific
    seasonal_condition: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    time_window: str = ""  # world-specific
    pass_required: str = ""  # world-specific
    gender_rule: str = ""  # world-specific
    supervisor_control: str = ""  # world-specific
    emergency_override: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
