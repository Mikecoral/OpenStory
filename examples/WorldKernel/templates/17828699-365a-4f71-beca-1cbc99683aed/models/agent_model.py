"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    age_range: str = ""  # world-specific
    cultural_reference: str = ""  # world-specific
    summer_detail: str = ""  # world-specific
    secret_story: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    encounter_type: str = ""  # world-specific
    friendship_depth: str = ""  # world-specific
    family_distance: str = ""  # world-specific
    memory_bond_level: str = ""  # world-specific
    emotional_temperature: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    jazz_appreciation: str = ""  # world-specific
    american_literature_knowledge: str = ""  # world-specific
    loneliness_endurance: str = ""  # world-specific
    conversation_strip_skill: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    inner_monologue_weight: str = ""  # world-specific
    silence_tolerance: str = ""  # world-specific
    melancholy_tendency: str = ""  # world-specific
    memory_preoccupation: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    meaningless_action_tendency: str = ""  # world-specific
    escape_desire: str = ""  # world-specific
    nostalgia_fixation: str = ""  # world-specific
    self_discovery_through_others: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    unreliable_memory_flag: str = ""  # world-specific
    time_jump_capacity: str = ""  # world-specific
    trigger_event_list: str = ""  # world-specific
    forgotten_detail: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_season: str = ""  # world-specific
    time_of_day: str = ""  # world-specific
    weather_condition: str = ""  # world-specific
    ambient_sound_type: str = ""  # world-specific
    ambient_odor_type: str = ""  # world-specific
    drink_consumed: str = ""  # world-specific
    cigarette_brand: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
