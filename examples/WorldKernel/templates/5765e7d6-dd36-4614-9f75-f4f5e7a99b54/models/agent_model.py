"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    previous_life_role: str = ""  # world-specific
    mortal_mission: str = ""  # world-specific
    karmic_symbol: str = ""  # world-specific
    celestial_registry: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    celestial_rank_title: str = ""  # world-specific
    mortal_class_marker: str = ""  # world-specific
    fate_label: str = ""  # world-specific
    karma_reputation: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    divine_residual_power: str = ""  # world-specific
    prophetic_insight: str = ""  # world-specific
    anomaly_detection: str = ""  # world-specific
    moral_sensitivity: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    prophecy_tied_trait: str = ""  # world-specific
    former_life_temperament: str = ""  # world-specific
    emotional_bond_mark: str = ""  # world-specific
    fate_imprint: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    celestial_mission_fullfillment: str = ""  # world-specific
    karmic_debt_repayment: str = ""  # world-specific
    earthly_ambition: str = ""  # world-specific
    destiny_fulfillment_path: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    previous_life_memory_segment: str = ""  # world-specific
    prophetic_dream_content: str = ""  # world-specific
    hidden_truth_fragment: str = ""  # world-specific
    forgotten_encounter_record: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    spatial_realm_type: str = ""  # world-specific
    temporal_event_marker: str = ""  # world-specific
    memory_seal_level: str = ""  # world-specific
    transformation_phase: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
