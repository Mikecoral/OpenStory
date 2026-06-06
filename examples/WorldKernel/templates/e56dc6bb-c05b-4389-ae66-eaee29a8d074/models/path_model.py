"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    controlled_by: str = ""  # world-specific
    connects_to_cities: str = ""  # world-specific
    route_type: str = ""  # world-specific
    historical_name: str = ""  # world-specific
    is_famous_route: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    intermediate_stops: str = ""  # world-specific
    distance_category: str = ""  # world-specific
    strategic_importance: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    terrain_type: str = ""  # world-specific
    seasonal_impact: str = ""  # world-specific
    ambush_suitability: str = ""  # world-specific
    supply_difficulty: str = ""  # world-specific
    water_source_availability: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    pass_requires_permit: str = ""  # world-specific
    seasonal_closure: str = ""  # world-specific
    special_event_risk: str = ""  # world-specific
    toll_cost: str = ""  # world-specific
    cavalry_passable: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
