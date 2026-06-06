"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    memory_retention_status: str = ""  # world-specific
    appearance_token: str = ""  # world-specific
    original_name_hash: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    trust_network: str = ""  # world-specific
    alliance_status: str = ""  # world-specific
    memory_sharing_group_id: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    game_skills: str = ""  # world-specific
    knowledge_systems: str = ""  # world-specific
    rule_understanding_level: str = ""  # world-specific
    resistance_tendency: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    fear_level: str = ""  # world-specific
    determination: str = ""  # world-specific
    madness_level: str = ""  # world-specific
    suspicion_tendency: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    survival_priority: str = ""  # world-specific
    rebellion_goal: str = ""  # world-specific
    information_gathering_goal: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    reincarnation_memories: str = ""  # world-specific
    secret_knowledge_level: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_cycle_number: str = ""  # world-specific
    memory_cycle_count: str = ""  # world-specific
    health_status: str = ""  # world-specific
    resource_count: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
