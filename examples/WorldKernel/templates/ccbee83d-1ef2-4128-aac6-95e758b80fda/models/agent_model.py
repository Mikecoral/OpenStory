"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    psychological_state_label: str = ""  # world-specific
    deceased_relationship: str = ""  # world-specific
    era_background: str = ""  # world-specific
    residence_status: str = ""  # world-specific
    student_movement_involvement: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    group_affiliation: str = ""  # world-specific
    reputation_label: str = ""  # world-specific
    emotional_dependency_object: str = ""  # world-specific
    circle_of_trust: str = ""  # world-specific
    stigma_related_to_trauma: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    instrument_playing_skill: str = ""  # world-specific
    writing_ability: str = ""  # world-specific
    coping_mechanism: str = ""  # world-specific
    alcohol_tolerance: str = ""  # world-specific
    psychotherapy_receptiveness: str = ""  # world-specific
    memory_vividness: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    inner_monologue_tendency: str = ""  # world-specific
    attitude_toward_death: str = ""  # world-specific
    attitude_toward_suicide: str = ""  # world-specific
    music_taste: str = ""  # world-specific
    loneliness_intensity: str = ""  # world-specific
    social_avoidance_level: str = ""  # world-specific
    nostalgia_frequency: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    alleviate_mental_pain: str = ""  # world-specific
    find_meaning_in_life: str = ""  # world-specific
    process_loss: str = ""  # world-specific
    maintain_connection_with_deceased: str = ""  # world-specific
    escape_into_isolation: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    memory_of_deceased_person: str = ""  # world-specific
    memory_of_specific_well: str = ""  # world-specific
    memory_of_amibe_sanatorium: str = ""  # world-specific
    music_associated_memory: str = ""  # world-specific
    traumatic_recollection: str = ""  # world-specific
    childhood_attachment_memory: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    emotional_state: str = ""  # world-specific
    season: str = ""  # world-specific
    year: str = ""  # world-specific
    flashback_triggered: str = ""  # world-specific
    current_drunkenness_level: str = ""  # world-specific
    location_mood_projection: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
