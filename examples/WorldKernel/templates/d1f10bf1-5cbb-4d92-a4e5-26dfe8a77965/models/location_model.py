"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    code_name: str = ""  # world-specific
    alternate_names: str = ""  # world-specific
    horcrux_related: str = ""  # world-specific
    danger_rating: str = ""  # world-specific
    historical_significance: str = ""  # world-specific
    dark_magic_resonance: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    current_password: str = ""  # world-specific
    surveillance_level: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific
    forbidden_charm_ward: str = ""  # world-specific
    secret_entrance_hint: str = ""  # world-specific
    floo_network_allowed: str = ""  # world-specific
    portkey_activation: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    current_occupying_faction: str = ""  # world-specific
    last_incident: str = ""  # world-specific
    mood_aura: str = ""  # world-specific
    restricted_items_stored: str = ""  # world-specific
    damage_level: str = ""  # world-specific
    contamination_type: str = ""  # world-specific
    emotional_ambience: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
