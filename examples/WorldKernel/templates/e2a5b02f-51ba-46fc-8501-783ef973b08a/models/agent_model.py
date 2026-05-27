"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    war_stance: str = ""  # world-specific
    public_allegiance: str = ""  # world-specific
    hidden_identity: str = ""  # world-specific
    group_role_in_resistance: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    trust_rating_with_peers: str = ""  # world-specific
    suspected_by_carros: str = ""  # world-specific
    phoenix_contact_status: str = ""  # world-specific
    reputation_among_slytherin: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    forbidden_magic_knowledge: str = ""  # world-specific
    underground_communication_skill: str = ""  # world-specific
    combat_experience: str = ""  # world-specific
    interrogation_resistance: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    fear_level: str = ""  # world-specific
    resistance_impulse: str = ""  # world-specific
    deception_ability: str = ""  # world-specific
    loyalty_toward_allies: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    survival_priority: str = ""  # world-specific
    resistance_contribution: str = ""  # world-specific
    exposure_risk_tolerance: str = ""  # world-specific
    longterm_secrecy_intent: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    witnessed_atrocity: str = ""  # world-specific
    preexisting_punishment_record: str = ""  # world-specific
    known_death_eater_secrets: str = ""  # world-specific
    memory_modified_incident: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    current_cover_story: str = ""  # world-specific
    suspicion_level: str = ""  # world-specific
    emotional_distress_indicator: str = ""  # world-specific
    physical_evidence_of_punishment: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
