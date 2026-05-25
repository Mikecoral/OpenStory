"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    is_secret: str = ""  # world-specific
    is_violent: str = ""  # world-specific
    control_type: str = ""  # world-specific
    cooperation_type: str = ""  # world-specific
    has_soul_correspondence: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    loyalty_dynamic: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    fear_factor: str = ""  # world-specific
    hidden_motive: str = ""  # world-specific
    contact_frequency: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
