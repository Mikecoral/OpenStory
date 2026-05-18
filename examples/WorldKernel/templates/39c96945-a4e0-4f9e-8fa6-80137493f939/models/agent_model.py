"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    house: str = ""  # world-specific
    blood_status: str = ""  # world-specific
    cover_identity: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    faction_role: str = ""  # world-specific
    ally_ids: str = ""  # world-specific
    enemy_ids: str = ""  # world-specific
    informant_network_rank: str = ""  # world-specific
    trust_level_by_faction: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    magical_specialization: str = ""  # world-specific
    occlumency_level: str = ""  # world-specific
    legilimency_resistance: str = ""  # world-specific
    dark_arts_proficiency: str = ""  # world-specific
    animagus_form: str = ""  # world-specific
    patronus_type: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    psychological_state: str = ""  # world-specific
    loyalty_level: str = ""  # world-specific
    rebellious_tendency: str = ""  # world-specific
    paranoia_index: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    secret_mission: str = ""  # world-specific
    hidden_motive: str = ""  # world-specific
    survival_priority: str = ""  # world-specific
    resistance_contribution: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    known_horcrux_locations: str = ""  # world-specific
    critical_secret_events: str = ""  # world-specific
    recent_encounter_log: str = ""  # world-specific
    betrayal_memory_flag: str = ""  # world-specific
    trust_rating_towards_others: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_disguise: str = ""  # world-specific
    safety_level: str = ""  # world-specific
    emotional_arousal: str = ""  # world-specific
    under_surveillance: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
