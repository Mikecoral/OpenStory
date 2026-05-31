"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    mythical_causality: str = ""  # world-specific
    prophecy_link: str = ""  # world-specific
    temporal_marker: str = ""  # world-specific
    spatial_context: str = ""  # world-specific
    fate_class: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    divine_origin: str = ""  # world-specific
    karmic_weight: str = ""  # world-specific
    transformation_catalyst: str = ""  # world-specific
    social_power: str = ""  # world-specific
    emotional_bond: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
