"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    blood_status: str = ""  # world-specific
    house: str = ""  # world-specific
    wartime_stance: str = ""  # world-specific
    is_death_eater: str = ""  # world-specific
    is_disguised: str = ""  # world-specific
    is_da_member: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    secret_organization_affiliation: str = ""  # world-specific
    death_eater_reputation: str = ""  # world-specific
    student_leadership: str = ""  # world-specific
    is_ostracized: str = ""  # world-specific
    family_imprisonment_status: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    defense_against_dark_arts_proficiency: str = ""  # world-specific
    dueling_skill: str = ""  # world-specific
    clandestine_magic_use: str = ""  # world-specific
    patronus_type: str = ""  # world-specific
    wordless_magic_mastery: str = ""  # world-specific
    special_aptitude: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    attitude_to_authority: str = ""  # world-specific
    secretive_tendency: str = ""  # world-specific
    loyalty_behavior: str = ""  # world-specific
    trauma_exposure: str = ""  # world-specific
    duality_persona: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    join_dark_side_goal: str = ""  # world-specific
    protect_someone_goal: str = ""  # world-specific
    horcrux_hunt_goal: str = ""  # world-specific
    intel_gathering_goal: str = ""  # world-specific
    survival_priority_goal: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    memory_of_dumbledore_death: str = ""  # world-specific
    memory_of_betrayal: str = ""  # world-specific
    secret_passage_knowledge: str = ""  # world-specific
    room_of_requirement_hidden_room_knowledge: str = ""  # world-specific
    death_eater_plan_knowledge: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_concealment_status: str = ""  # world-specific
    under_surveillance: str = ""  # world-specific
    health_status: str = ""  # world-specific
    wand_in_hand: str = ""  # world-specific
    dark_mark_marking: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
