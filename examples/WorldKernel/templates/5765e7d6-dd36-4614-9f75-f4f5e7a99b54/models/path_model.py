"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    symbolic_significance: str = ""  # world-specific
    physical_material: str = ""  # world-specific
    path_myth_status: str = ""  # world-specific
    narrative_phase: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    connection_type: str = ""  # world-specific
    narrative_importance: str = ""  # world-specific
    psychological_distance: str = ""  # world-specific
    layered_realm: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    access_condition_description: str = ""  # world-specific
    danger_source: str = ""  # world-specific
    temporal_significance: str = ""  # world-specific
    emotional_requirement: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
