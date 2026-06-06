"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    faction: str = ""  # world-specific
    strategic_importance: str = ""  # world-specific
    historical_event: str = ""  # world-specific
    cultural_significance: str = ""  # world-specific
    founding_date: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    garrison: str = ""  # world-specific
    control_status: str = ""  # world-specific
    trade_route: str = ""  # world-specific
    siege_history: str = ""  # world-specific
    blockade: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    fortification_level: str = ""  # world-specific
    resource_richness: str = ""  # world-specific
    population: str = ""  # world-specific
    morale: str = ""  # world-specific
    supply_level: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
