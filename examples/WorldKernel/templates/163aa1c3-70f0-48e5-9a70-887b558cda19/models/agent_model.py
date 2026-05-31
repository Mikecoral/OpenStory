"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    ninja_rank: str = ""  # world-specific
    affiliation: str = ""  # world-specific
    bloodline_limit: str = ""  # world-specific
    political_stance: str = ""  # world-specific
    relation_to_summit: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    organization_rank: str = ""  # world-specific
    fame: str = ""  # world-specific
    social_network: str = ""  # world-specific
    bounty: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    ninjutsu_type: str = ""  # world-specific
    taijutsu_rank: str = ""  # world-specific
    genjutsu_ability: str = ""  # world-specific
    special_ability: str = ""  # world-specific
    chakra_nature: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    loyalty: str = ""  # world-specific
    ambition: str = ""  # world-specific
    caution: str = ""  # world-specific
    emotional_expression: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    goal_for_summit: str = ""  # world-specific
    stance_on_akatsuki: str = ""  # world-specific
    personal_ambition: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    important_memories: str = ""  # world-specific
    summit_memory: str = ""  # world-specific
    training_history: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_status: str = ""  # world-specific
    action_mode: str = ""  # world-specific
    stamina: str = ""  # world-specific
    chakra_amount: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
