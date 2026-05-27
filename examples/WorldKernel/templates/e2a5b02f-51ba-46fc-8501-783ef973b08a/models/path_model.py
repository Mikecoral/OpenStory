"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    secret_channel: str = ""  # world-specific
    alias_name: str = ""  # world-specific
    marked_by_death_eaters: str = ""  # world-specific
    phoenix_order_affiliated: str = ""  # world-specific
    historical_significance: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    hidden_door: str = ""  # world-specific
    password_required: str = ""  # world-specific
    one_way_blocked: str = ""  # world-specific
    guarded_entrance: str = ""  # world-specific
    requires_magical_trigger: str = ""  # world-specific


class PropertiesDim(BaseModel):
    distance: str = ""
    travel_time: str = ""
    visibility: str = ""
    magical_barrier: str = ""  # world-specific
    illusion_magic: str = ""  # world-specific
    time_variant: str = ""  # world-specific
    cursed_path: str = ""  # world-specific
    guardian_creature: str = ""  # world-specific
    anti_apparition_ward: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    invisibility_required: str = ""  # world-specific
    under_surveillance: str = ""  # world-specific
    alarm_trigger: str = ""  # world-specific
    pass_demanded: str = ""  # world-specific
    disillusionment_charm_active: str = ""  # world-specific
    restricted_hours_usage: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    properties: PropertiesDim = PropertiesDim()
    conditions: ConditionsDim = ConditionsDim()
