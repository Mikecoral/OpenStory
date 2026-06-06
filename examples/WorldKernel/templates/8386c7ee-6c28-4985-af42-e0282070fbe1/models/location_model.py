"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    associated_game_rules: str = ""  # world-specific
    danger_level: str = ""  # world-specific
    location_function: str = ""  # world-specific
    secret_room_indicator: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    hidden_passage_exists: str = ""  # world-specific
    surveillance_density: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific
    key_or_permission_required: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    cycle_damage_status: str = ""  # world-specific
    resource_availability: str = ""  # world-specific
    reset_in_new_cycle: str = ""  # world-specific
    contamination_or_curse: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
