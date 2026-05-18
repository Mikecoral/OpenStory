"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    is_secret_tunnel: str = ""  # world-specific
    is_monitored: str = ""  # world-specific
    is_blocked: str = ""  # world-specific
    requires_password_or_item: str = ""  # world-specific
    name_in_history: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    from_faction_control: str = ""  # world-specific
    to_faction_control: str = ""  # world-specific
    has_surveillance_post: str = ""  # world-specific
    same_house_region: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    has_magical_traps: str = ""  # world-specific
    requires_invisibility: str = ""  # world-specific
    patrolled_by_portraits_ghosts: str = ""  # world-specific
    lighting_level: str = ""  # world-specific
    acoustic_magic_effects: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    needs_password: str = ""  # world-specific
    needs_invisibility_cloak: str = ""  # world-specific
    needs_marauders_map: str = ""  # world-specific
    blocked_by_death_eaters: str = ""  # world-specific
    time_restricted_access: str = ""  # world-specific
    anti_apparition_warding: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
