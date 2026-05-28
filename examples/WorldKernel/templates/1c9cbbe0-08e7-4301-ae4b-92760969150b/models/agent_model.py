"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    public_identity: str = ""  # world-specific
    true_allegiance: str = ""  # world-specific
    blood_status: str = ""  # world-specific
    house: str = ""  # world-specific
    cover_story: str = ""  # world-specific
    known_affiliation: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    allies: str = ""  # world-specific
    enemies: str = ""  # world-specific
    network: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    notoriety: str = ""  # world-specific
    protector: str = ""  # world-specific
    informer: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    combat_skills: str = ""  # world-specific
    espionage_skills: str = ""  # world-specific
    resistance_experience: str = ""  # world-specific
    knowledge_of_secret_passage: str = ""  # world-specific
    magical_abilities: str = ""  # world-specific
    danger_awareness: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    fear_level: str = ""  # world-specific
    bravery_index: str = ""  # world-specific
    suspicion_level: str = ""  # world-specific
    ideological_flexibility: str = ""  # world-specific
    response_to_oppression: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    priority: str = ""  # world-specific
    risk_tolerance: str = ""  # world-specific
    sacrifice_willingness: str = ""  # world-specific
    primary_loyalty: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    traumatic_memories: str = ""  # world-specific
    loyalty_oaths: str = ""  # world-specific
    hidden_knowledge: str = ""  # world-specific
    moral_conflicts: str = ""  # world-specific
    information_sources: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_activity: str = ""  # world-specific
    disguise_state: str = ""  # world-specific
    health_status: str = ""  # world-specific
    captivity_status: str = ""  # world-specific
    cover_status: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
