"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    house_affiliation: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    magical_features: str = ""  # world-specific
    aliases: str = ""  # world-specific
    is_forbidden_area: str = ""  # world-specific
    founder_associated: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    password_required: str = ""  # world-specific
    time_restriction: str = ""  # world-specific
    item_required: str = ""  # world-specific
    protective_enchantments: str = ""  # world-specific
    blood_status_restriction: str = ""  # world-specific
    invisibility_required: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    cursed_status: str = ""  # world-specific
    sealed_status: str = ""  # world-specific
    transformable: str = ""  # world-specific
    damage_state: str = ""  # world-specific
    seasonal_variation: str = ""  # world-specific
    magical_instability: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
