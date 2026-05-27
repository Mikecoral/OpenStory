"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    relation_type_detail: str = ""  # world-specific
    secret_level: str = ""  # world-specific
    allegiance: str = ""  # world-specific
    power_imbalance: str = ""  # world-specific
    context: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    trust_level: str = ""  # world-specific
    risk_level: str = ""  # world-specific
    interaction_frequency: str = ""  # world-specific
    hidden_activity: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
