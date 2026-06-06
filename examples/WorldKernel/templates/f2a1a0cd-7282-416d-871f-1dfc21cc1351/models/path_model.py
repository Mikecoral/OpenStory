"""Auto-generated Path Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    symbolic_meaning: str = ""  # world-specific
    threshold_nature: str = ""  # world-specific
    morph_property: str = ""  # world-specific


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False
    realm_transition: str = ""  # world-specific
    synchronicity_link: str = ""  # world-specific
    dream_connection: str = ""  # world-specific


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""
    rain_trigger: str = ""  # world-specific
    sleep_required: str = ""  # world-specific
    cat_mediation: str = ""  # world-specific
    trauma_threshold: str = ""  # world-specific


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()
