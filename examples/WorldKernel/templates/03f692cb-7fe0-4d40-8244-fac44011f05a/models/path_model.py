"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    surface_material: str = ""  # world-specific
    has_restriction: str = ""  # world-specific
    connected_to_vein: str = ""  # world-specific
    transformable: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    gate_type: str = ""  # world-specific
    teleportable: str = ""  # world-specific
    unidirectional_allowed: str = ""  # world-specific
    war_status: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    need_permission: str = ""  # world-specific
    minimum_magic_level: str = ""  # world-specific
    allowed_for_celestial: str = ""  # world-specific
    forbidden_for_demon: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
