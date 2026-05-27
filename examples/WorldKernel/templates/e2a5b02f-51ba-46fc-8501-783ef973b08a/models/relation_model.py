"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    is_secret: str = ""  # world-specific
    is_monitored: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    allegiance: str = ""  # world-specific
    risk_level: str = ""  # world-specific
    has_double_agent: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    interaction_frequency: str = ""  # world-specific
    public_visibility: str = ""  # world-specific
    coercion_present: str = ""  # world-specific
    mutual_benefit: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
