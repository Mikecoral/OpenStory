"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    allegiance_clash: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    secret_alliance: str = ""  # world-specific
    surveillance_aspect: str = ""  # world-specific
    power_dynamic: str = ""  # world-specific
    emotional_connection: str = ""  # world-specific
    information_channel: str = ""  # world-specific
    historical_relation: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    backstory_impact: str = ""  # world-specific
    current_tension: str = ""  # world-specific
    hidden_motives: str = ""  # world-specific
    loyalty_timeline: str = ""  # world-specific
    resistance_involvement: str = ""  # world-specific
    blood_status_influence: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
