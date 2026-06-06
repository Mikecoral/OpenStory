"""Auto-generated Agent Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    role: str = ""
    lucky_level: str = ""  # world-specific
    ability_type: str = ""  # world-specific
    faction_affiliation: str = ""  # world-specific
    role_backstory: str = ""  # world-specific
    relationship_network: str = ""  # world-specific


class SocialProfileDim(BaseModel):
    group_id: str = ""
    reputation: str = ""
    trust_level: str = ""  # world-specific
    social_role_in_group: str = ""  # world-specific
    factional_stance: str = ""  # world-specific
    reputation_tier: str = ""  # world-specific
    information_clearance_level: str = ""  # world-specific


class CapabilitiesDim(BaseModel):
    skills: list[str] = []
    level: str = ""
    weaknesses: str = ""
    ability_proficiency: str = ""  # world-specific
    combat_style: str = ""  # world-specific
    ability_side_effects: str = ""  # world-specific
    energy_consumption_rate: str = ""  # world-specific
    special_ability_synergy: str = ""  # world-specific


class PersonalityDim(BaseModel):
    traits: list[str] = []
    values: list[str] = []
    speech_style: str = ""
    ability_personality_synergy: str = ""  # world-specific
    combat_mannerisms: str = ""  # world-specific
    decision_style_under_pressure: str = ""  # world-specific
    morality_under_stress: str = ""  # world-specific


class GoalsDim(BaseModel):
    short_term_goal: str = ""
    long_term_goal: str = ""
    motivation: str = ""
    faction_missions: str = ""  # world-specific
    level_up_goal: str = ""  # world-specific
    partner_protection_goal: str = ""  # world-specific
    power_balance_goal: str = ""  # world-specific
    truth_seeking_goal: str = ""  # world-specific


class KnowledgeGroup(BaseModel):
    world_knowledge: list[str] = []
    social_knowledge: list[str] = []


class MemoriesDim(BaseModel):
    knowledge: KnowledgeGroup = KnowledgeGroup()
    background_summary: str = ""
    key_events: list[str] = []
    secrets: list[str] = []
    suppressed_memories: str = ""  # world-specific
    memory_access_level: str = ""  # world-specific
    emotional_charge: str = ""  # world-specific
    shared_memory_trauma: str = ""  # world-specific
    memory_integrity: str = ""  # world-specific


class LocationGroup(BaseModel):
    location_id: str = ""


class PositionGroup(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StateDim(BaseModel):
    location: LocationGroup = LocationGroup()
    position: PositionGroup = PositionGroup()
    health_status: str = ""  # world-specific
    ability_overload_level: str = ""  # world-specific
    current_action_state: str = ""  # world-specific
    fatigue_level: str = ""  # world-specific
    ability_cooldown_remaining: str = ""  # world-specific


class AgentModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    social_profile: SocialProfileDim = SocialProfileDim()
    capabilities: CapabilitiesDim = CapabilitiesDim()
    personality: PersonalityDim = PersonalityDim()
    goals: GoalsDim = GoalsDim()
    memories: MemoriesDim = MemoriesDim()
    state: StateDim = StateDim()
