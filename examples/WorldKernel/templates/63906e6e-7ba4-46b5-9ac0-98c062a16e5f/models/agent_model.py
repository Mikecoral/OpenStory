"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    risk_level: str = ""  # world-specific
    cover_identity: str = ""  # world-specific
    loyalty_status: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    cover_story: str = ""  # world-specific
    suspicion_level: str = ""  # world-specific
    pureblood_standing: str = ""  # world-specific
    relative_influence: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    dark_magic_proficiency: str = ""  # world-specific
    resistance_skills: str = ""  # world-specific
    occlumency_level: str = ""  # world-specific
    forbidden_spell_knowledge: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    internal_conflict_severity: str = ""  # world-specific
    trust_tendency: str = ""  # world-specific
    fear_of_exposure: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    hidden_agenda: str = ""  # world-specific
    resistance_contribution: str = ""  # world-specific
    survival_priority: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    secret_knowledge: str = ""  # world-specific
    compromising_information: str = ""  # world-specific
    loyalty_test_events: str = ""  # world-specific
    observed_blackmail: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_hideout: str = ""  # world-specific
    disguise_active: str = ""  # world-specific
    last_resistance_meeting: str = ""  # world-specific
    alert_level: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
