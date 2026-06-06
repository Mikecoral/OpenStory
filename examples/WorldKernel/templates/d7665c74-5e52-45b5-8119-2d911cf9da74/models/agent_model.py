"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    supernatural_identity_marker: str = ""  # world-specific
    cursed_by_fate: str = ""  # world-specific
    fragmented_memory_indicator: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    cross_species_relation_status: str = ""  # world-specific
    fate_woven_connections: str = ""  # world-specific
    isolated_reputation: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    cat_communication: str = ""  # world-specific
    stone_reading: str = ""  # world-specific
    reality_blurring_vision: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    philosophical_reflection_tendency: str = ""  # world-specific
    surreal_perception: str = ""  # world-specific
    existential_anxiety: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    fate_fulfillment_goal: str = ""  # world-specific
    escape_from_curse: str = ""  # world-specific
    spiritual_enlightenment: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    fragmented_memory_pieces: str = ""  # world-specific
    surreal_knowledge_of_stone: str = ""  # world-specific
    drenched_with_fate: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    surreal_flux_state: str = ""  # world-specific
    dimension_proximity: str = ""  # world-specific
    time_distortion_effect: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
