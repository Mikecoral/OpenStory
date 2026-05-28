"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    has_secret_allegiance: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    monitoring_intensity: str = ""  # world-specific
    blood_status_relevance: str = ""  # world-specific
    communication_channel: str = ""  # world-specific
    is_publicly_known: str = ""  # world-specific
    spy_risk_level: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    relationship_duration: str = ""  # world-specific
    public_perception: str = ""  # world-specific
    resistance_affiliation: str = ""  # world-specific
    punishment_risk: str = ""  # world-specific
    emotional_tone: str = ""  # world-specific
    power_dynamic: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
