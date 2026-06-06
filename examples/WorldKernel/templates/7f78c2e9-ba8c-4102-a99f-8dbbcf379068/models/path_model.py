"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    area_danger_rating: str = ""  # world-specific
    function_tag: str = ""  # world-specific
    scene_atmosphere: str = ""  # world-specific
    governing_faction: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    from_area_type: str = ""  # world-specific
    to_area_type: str = ""  # world-specific
    from_security_level: str = ""  # world-specific
    to_security_level: str = ""  # world-specific
    hidden_endpoint: str = ""  # world-specific
    transport_type: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    access_requirement: str = ""  # world-specific
    monster_encounter_probability: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    combat_allowed: str = ""  # world-specific
    ability_restriction: str = ""  # world-specific
    time_restriction: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
