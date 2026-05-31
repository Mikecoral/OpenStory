"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    affiliated_village: str = ""  # world-specific
    path_type: str = ""  # world-specific
    under_surveillance: str = ""  # world-specific
    barrier_type: str = ""  # world-specific
    strategic_significance: str = ""  # world-specific
    historical_artifact: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    distance_km: str = ""  # world-specific
    checkpoints: str = ""  # world-specific
    passes_neutral_territory: str = ""  # world-specific
    pilgrimage_route: str = ""  # world-specific
    trade_cities: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    pass_required: str = ""  # world-specific
    rank_restriction: str = ""  # world-specific
    night_travel_allowed: str = ""  # world-specific
    weather_vulnerability: str = ""  # world-specific
    hostile_threat_level: str = ""  # world-specific
    trap_density: str = ""  # world-specific
    special_ability_needed: str = ""  # world-specific
    time_window: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
