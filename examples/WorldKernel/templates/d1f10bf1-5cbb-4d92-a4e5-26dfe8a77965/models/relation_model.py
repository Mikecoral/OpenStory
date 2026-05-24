"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    relation_type: str = ""  # world-specific
    relation_subtype: str = ""  # world-specific
    interaction_history: str = ""  # world-specific
    conflict_trigger: str = ""  # world-specific
    disguise_level: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
