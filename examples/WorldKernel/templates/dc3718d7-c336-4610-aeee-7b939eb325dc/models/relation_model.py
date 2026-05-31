"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    political_stance: str = ""  # world-specific
    allegiance: str = ""  # world-specific
    visibility: str = ""  # world-specific
    authority_level: str = ""  # world-specific
    collaboration_secret: str = ""  # world-specific
    hostility_level: str = ""  # world-specific
    emotional_bond: str = ""  # world-specific
    supervision_role: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    duration: str = ""  # world-specific
    trigger_event: str = ""  # world-specific
    historical_context: str = ""  # world-specific
    conditional_constraints: str = ""  # world-specific
    mutual_knowledge: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
