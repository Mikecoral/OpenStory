"""Auto-generated Relation Pydantic model."""
from pydantic import BaseModel


class EdgeDim(BaseModel):
    id: str = ""
    from_id: str = ""
    to_id: str = ""
    type: str = ""
    direction: str = ""
    shared_memory: str = ""  # world-specific
    interaction_frequency: str = ""  # world-specific
    first_meeting_context: str = ""  # world-specific
    current_status: str = ""  # world-specific
    tragic_element: str = ""  # world-specific
    emotional_tone: str = ""  # world-specific
    sanatorium_context: str = ""  # world-specific


class PropertiesDim(BaseModel):
    strength: str = ""
    description: str = ""
    power_dynamics: str = ""  # world-specific
    communication_pattern: str = ""  # world-specific
    emotional_dependence_level: str = ""  # world-specific
    trauma_sharing: str = ""  # world-specific
    physical_intimacy_level: str = ""  # world-specific
    future_prospect: str = ""  # world-specific
    parallel_to_other_relationship: str = ""  # world-specific
    class_difference: str = ""  # world-specific
    age_gap: str = ""  # world-specific
    shared_interest: str = ""  # world-specific


class RelationModel(BaseModel):
    edge: EdgeDim = EdgeDim()
    properties: PropertiesDim = PropertiesDim()
