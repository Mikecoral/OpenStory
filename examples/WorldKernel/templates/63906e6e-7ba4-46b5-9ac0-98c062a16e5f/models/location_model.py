"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    occupying_faction: str = ""  # world-specific
    secret_alias: str = ""  # world-specific
    hiding_capabilities: str = ""  # world-specific
    battle_relevance: str = ""  # world-specific
    defilement_level: str = ""  # world-specific
    institutional_role_changed: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    blood_status_required: str = ""  # world-specific
    password_required: str = ""  # world-specific
    patrolled_by_carros: str = ""  # world-specific
    secret_entrance_available: str = ""  # world-specific
    time_restrictions: str = ""  # world-specific
    cleansing_certificate_required: str = ""  # world-specific
    monitoring_spells_active: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    atmosphere_type: str = ""  # world-specific
    occupation_utility: str = ""  # world-specific
    hidden_capacity_used: str = ""  # world-specific
    maintenance_neglect: str = ""  # world-specific
    temporary_modifications: str = ""  # world-specific
    curse_wards_active: str = ""  # world-specific
    contraband_storage_present: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
