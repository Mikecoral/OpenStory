"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    hidden_alias: str = ""  # world-specific
    known_to_death_eaters: str = ""  # world-specific
    password_protected: str = ""  # world-specific
    resistance_codename: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    has_secret_entrance: str = ""  # world-specific
    monitored_by_carow: str = ""  # world-specific
    connected_to_room_of_requirement: str = ""  # world-specific
    floo_network_accessible: str = ""  # world-specific
    vanishing_cabinet_pair: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    invisibility_bool: str = ""  # world-specific
    has_thiefs_downfall: str = ""  # world-specific
    is_floo_connected: str = ""  # world-specific
    anti_apparition_warded: str = ""  # world-specific
    patrol_frequency: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    curfew_restricted: str = ""  # world-specific
    requires_password: str = ""  # world-specific
    has_booby_trap: str = ""  # world-specific
    alert_level: str = ""  # world-specific
    requires_invisibility_cloak: str = ""  # world-specific
    dementor_patrolled: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
