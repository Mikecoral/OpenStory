"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    examination_phase: str = ""  # world-specific
    is_hidden_role: str = ""  # world-specific
    faction_identity: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    reputation_in_sea_god_island: str = ""  # world-specific
    relation_with_seven_pillars: str = ""  # world-specific
    internal_faction_standing: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    soul_element_attribute: str = ""  # world-specific
    domain_type: str = ""  # world-specific
    special_combat_skill: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    faith_in_sea_god: str = ""  # world-specific
    reaction_to_crisis: str = ""  # world-specific
    emotional_attachment_style: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    current_exam_sub_goal: str = ""  # world-specific
    hidden_agenda: str = ""  # world-specific
    emotional_breakthrough_target: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    critical_exam_memories: str = ""  # world-specific
    memory_of_loved_ones: str = ""  # world-specific
    hidden_trauma_or_secret: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    examination_stage_progress: str = ""  # world-specific
    health_status_percentage: str = ""  # world-specific
    corruption_level_for_hidden_roles: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
