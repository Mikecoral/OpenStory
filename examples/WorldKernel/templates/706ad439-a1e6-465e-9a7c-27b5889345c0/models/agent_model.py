"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    family_generation: str = ""  # world-specific
    noble_rank_or_official_title: str = ""  # world-specific
    jinling_twelve_belles_catalogue: str = ""  # world-specific
    fate_couplet: str = ""  # world-specific
    lineage_position: str = ""  # world-specific
    palace_title_if_applicable: str = ""  # world-specific
    marital_status: str = ""  # world-specific
    dowry_or_estate_inheritance: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    standing_in_rong_ning_houses: str = ""  # world-specific
    reputation_among_servants: str = ""  # world-specific
    alliance_with_other_noble_families: str = ""  # world-specific
    appraisal_by_elder_matrons: str = ""  # world-specific
    criticized_or_admired_by_peers: str = ""  # world-specific
    role_in_family_power_structure: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    literary_composition_skill: str = ""  # world-specific
    painting_or_calligraphy_skill: str = ""  # world-specific
    music_or_dance_skill: str = ""  # world-specific
    domestic_management_ability: str = ""  # world-specific
    medical_or_herbal_knowledge: str = ""  # world-specific
    strategic_maneuvering: str = ""  # world-specific
    reading_proficiency_for_women: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    poetic_talent_level: str = ""  # world-specific
    confucian_moral_alignment: str = ""  # world-specific
    attitude_toward_feudal_rites: str = ""  # world-specific
    romantic_or_love_view: str = ""  # world-specific
    religious_or_superstitious_disposition: str = ""  # world-specific
    loyalty_to_jia_family: str = ""  # world-specific
    social_ambition: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    jinling_twelve_belles_prophesied_fate: str = ""  # world-specific
    marriage_alliance_target: str = ""  # world-specific
    clan_restoration_ambition: str = ""  # world-specific
    escape_or_reform_of_oppression: str = ""  # world-specific
    protection_of_certain_family_members: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    memory_of_imperial_consort_shengqin: str = ""  # world-specific
    key_poem_society_events: str = ""  # world-specific
    childhood_interactions_with_cousins: str = ""  # world-specific
    secret_knowledge_of_family_corruption: str = ""  # world-specific
    traumatic_experiences: str = ""  # world-specific
    seasonal_festival_memories: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_courtyard_residence: str = ""  # world-specific
    physical_health_condition: str = ""  # world-specific
    emotional_mood_state: str = ""  # world-specific
    current_activity_or_seasonal_event: str = ""  # world-specific
    indoors_or_outdoors_restriction: str = ""  # world-specific
    time_of_day_and_schedule: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
