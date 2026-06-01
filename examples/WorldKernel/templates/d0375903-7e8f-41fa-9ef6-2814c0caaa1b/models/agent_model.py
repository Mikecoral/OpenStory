"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    family_rank: str = ""  # world-specific
    lineage: str = ""  # world-specific
    marital_status: str = ""  # world-specific
    is_legitimate: str = ""  # world-specific
    house_branch: str = ""  # world-specific
    generation: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    alliances: str = ""  # world-specific
    enemies: str = ""  # world-specific
    social_class_rank: str = ""  # world-specific
    public_perception: str = ""  # world-specific
    rumor_status: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    special_knowledge: str = ""  # world-specific
    unique_skills: str = ""  # world-specific
    quack_remedies: str = ""  # world-specific
    literary_talent: str = ""  # world-specific
    manipulation_techniques: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    motivations_detail: str = ""  # world-specific
    emotional_state: str = ""  # world-specific
    mental_health: str = ""  # world-specific
    hidden_traits: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    hidden_agenda: str = ""  # world-specific
    desperate_goal: str = ""  # world-specific
    secondary_goal: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    recent_incidents: str = ""  # world-specific
    traumatic_memories: str = ""  # world-specific
    biased_beliefs: str = ""  # world-specific
    superstitious_knowledge: str = ""  # world-specific
    family_lore: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    health_state: str = ""  # world-specific
    current_action: str = ""  # world-specific
    possession: str = ""  # world-specific
    injury_status: str = ""  # world-specific
    confinement_status: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
