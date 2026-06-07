from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from worldkernel.architect.tools.generators.base_generator import parse_and_validate  # noqa: E402
from worldkernel.architect.tools.generators.path_generator import PathGenerationTool  # noqa: E402


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""


class EndpointsDim(BaseModel):
    from_id: str = ""
    to_id: str = ""
    bidirectional: bool = False


class ConditionsDim(BaseModel):
    access_level: str = ""
    danger_level: str = ""
    required_items: str = ""


class PathModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    endpoints: EndpointsDim = EndpointsDim()
    conditions: ConditionsDim = ConditionsDim()


def test_normalizes_stage3_location_endpoint_aliases_before_validation() -> None:
    raw = [
        {
            "identity": {"name": "Garden path", "type": "walkway"},
            "from_location_id": "loc-001",
            "to_location_id": "loc-002",
            "conditions": {"access_level": "open"},
        }
    ]

    normalized, warnings = PathGenerationTool._normalize_endpoint_fields(raw)
    validated, val_warnings = parse_and_validate(normalized, PathModel, [])

    assert warnings == ["normalized endpoint aliases in path[0]"]
    assert val_warnings == []
    assert validated[0].endpoints.from_id == "loc-001"
    assert validated[0].endpoints.to_id == "loc-002"


def test_normalizes_nested_source_target_endpoint_aliases() -> None:
    raw = [
        {
            "identity": {"name": "Secret route", "type": "shortcut"},
            "endpoints": {
                "source": {"location_id": "loc-003"},
                "target": {"id": "loc-004"},
                "bidirectional": True,
            },
        }
    ]

    normalized, _warnings = PathGenerationTool._normalize_endpoint_fields(raw)
    validated, _val_warnings = parse_and_validate(normalized, PathModel, [])

    assert validated[0].endpoints.from_id == "loc-003"
    assert validated[0].endpoints.to_id == "loc-004"
    assert validated[0].endpoints.bidirectional is True


def test_coerces_wrapped_path_collection() -> None:
    raw = {"paths": [{"from_location_id": "loc-001", "to_location_id": "loc-002"}]}

    paths = PathGenerationTool._coerce_path_collection(raw)

    assert paths == [{"from_location_id": "loc-001", "to_location_id": "loc-002"}]
