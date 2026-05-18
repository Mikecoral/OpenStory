"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    path_name: str = ""  # world-specific
    path_function: str = ""  # world-specific
    cultural_connotation: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    connects_inner_outer: str = ""  # world-specific
    connects_hierarchy_zones: str = ""  # world-specific
    connects_scenic_spots: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    paving_material: str = ""  # world-specific
    width: str = ""  # world-specific
    has_cover: str = ""  # world-specific
    has_gate: str = ""  # world-specific
    has_lantern: str = ""  # world-specific
    has_decoration: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    access_time_restriction: str = ""  # world-specific
    person_type_restriction: str = ""  # world-specific
    weather_impact: str = ""  # world-specific
    maintenance_state: str = ""  # world-specific
    seasonal_variation: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
