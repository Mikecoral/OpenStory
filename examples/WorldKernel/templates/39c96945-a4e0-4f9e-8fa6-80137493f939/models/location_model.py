"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    forbidden_alias_in_terror_era: str = ""  # world-specific
    associated_key_event: str = ""  # world-specific
    faction_affiliation: str = ""  # world-specific
    dark_mark_branding: str = ""  # world-specific
    historical_significance_change: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    curfew_restriction: str = ""  # world-specific
    password_rotation_policy: str = ""  # world-specific
    death_eater_guard_presence: str = ""  # world-specific
    anti_apparition_charm_coverage: str = ""  # world-specific
    surveillance_portrait_network: str = ""  # world-specific
    muggleborn_exclusion_flag: str = ""  # world-specific
    secret_passage_availability: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    functional_alteration_type: str = ""  # world-specific
    physical_condition: str = ""  # world-specific
    hidden_content_flag: str = ""  # world-specific
    atmosphere_gauge: str = ""  # world-specific
    alarm_magic_activation: str = ""  # world-specific
    occupancy_trend: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
