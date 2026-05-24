"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    faction: str = ""  # world-specific
    disguise_identity: str = ""  # world-specific
    dark_mark_present: str = ""  # world-specific
    order_of_phoenix_rank: str = ""  # world-specific
    death_eater_affiliation_level: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    resistance_group_role: str = ""  # world-specific
    suspicion_level: str = ""  # world-specific
    informant_tag: str = ""  # world-specific
    neutrality_credibility: str = ""  # world-specific
    familial_vulnerability: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    occlumency_mastery: str = ""  # world-specific
    defense_against_dark_arts_proficiency: str = ""  # world-specific
    transfiguration_specialization: str = ""  # world-specific
    legilimency_resistance: str = ""  # world-specific
    horcrux_knowledge: str = ""  # world-specific
    forbidden_spells_knowledge: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    fear_level: str = ""  # world-specific
    defiance_tendency: str = ""  # world-specific
    loyalty_test_result: str = ""  # world-specific
    paranoia_index: str = ""  # world-specific
    mask_of_compliance: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    horcrux_hunt_target: str = ""  # world-specific
    intelligence_gathering_objective: str = ""  # world-specific
    survival_priority: str = ""  # world-specific
    resistance_communication_duty: str = ""  # world-specific
    ward_bypass_objective: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    horcrux_location_clues: str = ""  # world-specific
    dumbledore_secret_trust: str = ""  # world-specific
    snapes_duality_evidence: str = ""  # world-specific
    carror_punishment_events: str = ""  # world-specific
    password_network_history: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_alertness: str = ""  # world-specific
    hidden_status: str = ""  # world-specific
    injury_severity: str = ""  # world-specific
    magic_residue_detection_risk: str = ""  # world-specific
    under_surveillance: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
