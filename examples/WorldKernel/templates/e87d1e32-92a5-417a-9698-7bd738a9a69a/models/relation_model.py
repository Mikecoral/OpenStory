"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    relation_subtype: str = ""  # world-specific
    is_direct: str = ""  # world-specific
    hierarchy_gap: str = ""  # world-specific
    ritual_obligation: str = ""  # world-specific
    cause_effect_link: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    emotional_bond: str = ""  # world-specific
    interest_tie: str = ""  # world-specific
    karma_weight: str = ""  # world-specific
    dependence_level: str = ""  # world-specific
    conflict_potential: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
