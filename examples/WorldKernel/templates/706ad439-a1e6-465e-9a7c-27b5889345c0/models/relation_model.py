"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    kinship_type: str = ""  # world-specific
    political_marriage_flag: str = ""  # world-specific
    master_servant_role: str = ""  # world-specific
    love_type: str = ""  # world-specific
    power_chain_rank: str = ""  # world-specific
    gender_restriction_level: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    intimacy_level: str = ""  # world-specific
    conflict_intensity: str = ""  # world-specific
    ritual_weight: str = ""  # world-specific
    economic_bond: str = ""  # world-specific
    dependency_degree: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
