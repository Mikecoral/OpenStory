"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    blood_status: str = ""  # world-specific
    faction: str = ""  # world-specific
    public_role: str = ""  # world-specific
    secret_role: str = ""  # world-specific
    house: str = ""  # world-specific
    year: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    trust_rating_with_carols: str = ""  # world-specific
    membership_in_resistance_cell: str = ""  # world-specific
    informer_suspicion_level: str = ""  # world-specific
    house_prefect_status: str = ""  # world-specific
    relationship_with_snape: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    occlumency_proficiency: str = ""  # world-specific
    animagus_form: str = ""  # world-specific
    patronus_type: str = ""  # world-specific
    dark_arts_knowledge: str = ""  # world-specific
    illegal_spell_mastery: str = ""  # world-specific
    undercover_communication_skills: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    fear_of_authority: str = ""  # world-specific
    loyalty_to_resistance: str = ""  # world-specific
    tolerance_for_dark_magic: str = ""  # world-specific
    suspicion_towards_others: str = ""  # world-specific
    sense_of_humor_under_pressure: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    survive_carol_harassment: str = ""  # world-specific
    protect_muggleborn_friends: str = ""  # world-specific
    gather_intelligence_on_death_eaters: str = ""  # world-specific
    rebuild_dumbledores_army: str = ""  # world-specific
    sabotage_carol_reign: str = ""  # world-specific
    find_horcrux_information: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    witnessed_cruciatus_cast: str = ""  # world-specific
    attended_secret_da_meeting: str = ""  # world-specific
    knows_room_of_requirement_location: str = ""  # world-specific
    carried_messages_for_order: str = ""  # world-specific
    hidden_muggleborn_escape_route: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_hiding_status: str = ""  # world-specific
    under_surveillance_flag: str = ""  # world-specific
    injury_level: str = ""  # world-specific
    polyjuice_disguise_active: str = ""  # world-specific
    last_safe_room_visited: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
