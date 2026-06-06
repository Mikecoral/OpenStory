"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    symbolic_name: str = ""  # world-specific
    curse_bearer: str = ""  # world-specific
    supernatural_origin: str = ""  # world-specific
    shadow_self: str = ""  # world-specific
    mother_sister_incarnation: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    symbolic_role_in_cosmos: str = ""  # world-specific
    phantom_connection_degree: str = ""  # world-specific
    animal_community_rel: str = ""  # world-specific
    historical_figure_echo: str = ""  # world-specific
    taboo_group_membership: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    cat_telepathy: str = ""  # world-specific
    boundary_crossing_ability: str = ""  # world-specific
    dream_weaving: str = ""  # world-specific
    historical_echo_hearing: str = ""  # world-specific
    portal_recognition: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    introspective_silence: str = ""  # world-specific
    fatalistic_acceptance: str = ""  # world-specific
    duality_nature: str = ""  # world-specific
    metaphorical_speech_tendency: str = ""  # world-specific
    trauma_repression: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    escape_prophecy: str = ""  # world-specific
    seek_truth_of_curse: str = ""  # world-specific
    encounter_phantom_figure: str = ""  # world-specific
    reconcile_past_wounds: str = ""  # world-specific
    achieve_self_redemption: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    repressed_childhood_trauma: str = ""  # world-specific
    ancestral_curse_knowledge: str = ""  # world-specific
    war_trauma_imprint: str = ""  # world-specific
    phantom_encounter_records: str = ""  # world-specific
    cat_memory_exchange: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    threshold_proximity: str = ""  # world-specific
    liminal_state_flag: str = ""  # world-specific
    weather_affects_mentality: str = ""  # world-specific
    time_of_day_mood: str = ""  # world-specific
    supernatural_encounter_countdown: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
