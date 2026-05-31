"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    power_dynamics: str = ""  # world-specific
    secret_contact: str = ""  # world-specific
    loyalty_based: str = ""  # world-specific
    monitoring_role: str = ""  # world-specific
    allegiance_type: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    trust_level: str = ""  # world-specific
    collaboration_type: str = ""  # world-specific
    risk_level: str = ""  # world-specific
    frequency: str = ""  # world-specific
    emotional_tone: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
