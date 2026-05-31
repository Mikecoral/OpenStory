"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    blood_status: str = ""  # world-specific
    wand_core: str = ""  # world-specific
    patronus_form: str = ""  # world-specific
    family_background: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    da_member_status: str = ""  # world-specific
    caro_favorability: str = ""  # world-specific
    slytherin_secret_sympathy: str = ""  # world-specific
    house_peer_trust_level: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    dark_arts_defense_level: str = ""  # world-specific
    nonverbal_magic_proficiency: str = ""  # world-specific
    illegal_spells_known: str = ""  # world-specific
    polyjuice_awareness: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    loyalty_bias: str = ""  # world-specific
    fear_of_carous: str = ""  # world-specific
    secret_resistance_urge: str = ""  # world-specific
    trust_threshold: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    escape_school_priority: str = ""  # world-specific
    protect_fellow_students: str = ""  # world-specific
    undermine_carregime: str = ""  # world-specific
    survival_over_honor: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    dumbledores_army_activation_phrase: str = ""  # world-specific
    known_room_of_requirement_entrances: str = ""  # world-specific
    deatheater_curfew_routes: str = ""  # world-specific
    hogwarts_ghost_interactions: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    hidden_object_inventory: str = ""  # world-specific
    current_curfew_compliance: str = ""  # world-specific
    wand_ownership_verified: str = ""  # world-specific
    magical_tracking_status: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
