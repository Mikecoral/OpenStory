"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    controller: str = ""  # world-specific
    secret_entrance: str = ""  # world-specific
    hidden_function: str = ""  # world-specific
    narrative_significance: str = ""  # world-specific
    historic_allegiance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    password_required: str = ""  # world-specific
    surveillance_charm: str = ""  # world-specific
    anti_apparition: str = ""  # world-specific
    anti_tracking: str = ""  # world-specific
    restricted_to_faction: str = ""  # world-specific
    ward_level: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    usage_state: str = ""  # world-specific
    defense_level: str = ""  # world-specific
    occupied_by_death_eaters: str = ""  # world-specific
    protective_enchantments: str = ""  # world-specific
    integrity_status: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
