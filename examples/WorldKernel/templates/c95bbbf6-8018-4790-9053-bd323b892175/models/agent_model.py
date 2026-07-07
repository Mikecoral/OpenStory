"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    house: str = ""  # world-specific
    year: str = ""  # world-specific
    blood_status: str = ""  # world-specific
    position_in_resistance: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    membership_in_organizations: str = ""  # world-specific
    trust_level: str = ""  # world-specific
    intimidation_factor: str = ""  # world-specific
    popularity: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    magical_specialization: str = ""  # world-specific
    patronus_type: str = ""  # world-specific
    animagus_form: str = ""  # world-specific
    wand_core: str = ""  # world-specific
    proficiency_in_occlumency: str = ""  # world-specific
    proficiency_in_legilimency: str = ""  # world-specific
    resistance_to_cruciatus: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    loyalty_to_voldemort: str = ""  # world-specific
    willingness_to_betray: str = ""  # world-specific
    courage_level: str = ""  # world-specific
    paranoia_level: str = ""  # world-specific
    trust_in_others: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    secret_mission: str = ""  # world-specific
    person_to_protect: str = ""  # world-specific
    target_to_eliminate: str = ""  # world-specific
    information_to_obtain: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    traumatic_memories: str = ""  # world-specific
    knowledge_of_horcruxes: str = ""  # world-specific
    knowledge_of_deathly_hallows: str = ""  # world-specific
    cursed_wound_related_memory: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    under_surveillance: str = ""  # world-specific
    current_disguise: str = ""  # world-specific
    health_status: str = ""  # world-specific
    holds_horcrux_fragment: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
