"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    secret_identity: str = ""  # world-specific
    blood_status: str = ""  # world-specific
    death_eater_registration_status: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    underground_reputation: str = ""  # world-specific
    suspicion_level: str = ""  # world-specific
    house_point_standing: str = ""  # world-specific
    death_eater_trust_level: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    unforgivable_curses_mastery: str = ""  # world-specific
    patronus_form: str = ""  # world-specific
    occlumency_proficiency: str = ""  # world-specific
    galleon_communicator: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    attitude_towards_voldemort: str = ""  # world-specific
    fear_level: str = ""  # world-specific
    loyalty_to_order: str = ""  # world-specific
    compliance_with_carros: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    seeking_horcrux: str = ""  # world-specific
    planning_escape: str = ""  # world-specific
    undermining_carros_regime: str = ""  # world-specific
    protecting_other_students: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    horcrux_knowledge: str = ""  # world-specific
    deathly_hallows_knowledge: str = ""  # world-specific
    direct_harry_contact: str = ""  # world-specific
    order_communication_methods: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    under_surveillance: str = ""  # world-specific
    current_hiding_spot: str = ""  # world-specific
    invisibility_status: str = ""  # world-specific
    last_interaction_with_carros: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
