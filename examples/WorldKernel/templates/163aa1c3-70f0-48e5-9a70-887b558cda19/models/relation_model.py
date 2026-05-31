"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    relation_subtype: str = ""  # world-specific
    temporal_status: str = ""  # world-specific
    political_affiliation: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    trust_level: str = ""  # world-specific
    power_balance: str = ""  # world-specific
    shared_goals: str = ""  # world-specific
    conflict_history: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
