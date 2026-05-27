"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    relation_context: str = ""  # world-specific
    visibility: str = ""  # world-specific
    power_imbalance: str = ""  # world-specific
    surveillance_presence: str = ""  # world-specific
    secret_or_public: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    trust_level: str = ""  # world-specific
    shared_secrets: str = ""  # world-specific
    conflict_intensity: str = ""  # world-specific
    external_pressure: str = ""  # world-specific
    loyalty_conflict: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
