"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    hidden_identity: str = ""  # world-specific
    house: str = ""  # world-specific
    blood_status: str = ""  # world-specific
    cover_role: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    faction_reputation: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    codename: str = ""  # world-specific
    trust_circle: str = ""  # world-specific
    public_perception: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    nonverbal_magic_proficiency: str = ""  # world-specific
    dark_arts_knowledge: str = ""  # world-specific
    silent_spell_mastery: str = ""  # world-specific
    transfiguration_specialty: str = ""  # world-specific
    occult_knowledge: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    loyalty_dynamic: str = ""  # world-specific
    fear_level: str = ""  # world-specific
    moral_boundary: str = ""  # world-specific
    suspicion_index: str = ""  # world-specific
    resilience: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    secret_goal: str = ""  # world-specific
    coerced_goal: str = ""  # world-specific
    sacrifice_willingness: str = ""  # world-specific
    betrayal_threshold: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    suppressed_memory: str = ""  # world-specific
    false_memory_implanted: str = ""  # world-specific
    trauma_event: str = ""  # world-specific
    forbidden_knowledge: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_activity: str = ""  # world-specific
    hidden_status: str = ""  # world-specific
    injury_level: str = ""  # world-specific
    stamina: str = ""  # world-specific
    surrounding_threat: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
