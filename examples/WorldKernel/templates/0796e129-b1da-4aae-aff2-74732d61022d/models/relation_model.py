"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    historical_event: str = ""  # world-specific
    faction_alignment: str = ""  # world-specific
    house_dynamic: str = ""  # world-specific
    special_bond: str = ""  # world-specific
    narrative_role: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    emotional_state: str = ""  # world-specific
    secrecy: str = ""  # world-specific
    power_dynamic: str = ""  # world-specific
    magical_contract: str = ""  # world-specific
    transformative_event: str = ""  # world-specific
    longevity: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
