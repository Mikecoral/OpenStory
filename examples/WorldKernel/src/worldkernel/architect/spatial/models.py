"""Spatial layer data models for input assembly and annotation maps."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input assembly models
# ---------------------------------------------------------------------------


class SpatialInputWarning(BaseModel):
    code: str
    message: str
    source: str = ""
    item_index: int | None = None
    item_id: str = ""


class LocationSpatialFact(BaseModel):
    location_id: str
    name: str
    location_type: str = ""
    description: str = ""
    importance: str = ""
    access_level: str = ""
    capacity: int = 0
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class PathSpatialFact(BaseModel):
    path_id: str
    from_location_id: str
    to_location_id: str
    name: str = ""
    path_type: str = ""
    bidirectional: bool = True
    is_secret: bool = False
    access_level: str = ""
    danger_level: str = ""
    movement_hint: str = ""
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CharacterPlacementFact(BaseModel):
    character_id: str
    name: str
    home_location_id: str = ""
    current_location_id: str = ""
    preferred_location_id: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class SpatialBuildInput(BaseModel):
    world_id: str
    source_root: str
    locations: list[LocationSpatialFact] = Field(default_factory=list)
    paths: list[PathSpatialFact] = Field(default_factory=list)
    characters: list[CharacterPlacementFact] = Field(default_factory=list)
    warnings: list[SpatialInputWarning] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Layout models
# ---------------------------------------------------------------------------


class LocationLayout(BaseModel):
    location_id: str
    center_x: int
    center_y: int
    layer_id: str = "ground"


class LayoutPlan(BaseModel):
    world_id: str
    grid_width: int
    grid_height: int
    tile_size: int
    locations: list[LocationLayout] = Field(default_factory=list)
    synthetic_edges: list[tuple[str, str]] = Field(default_factory=list)
    warnings: list[SpatialInputWarning] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Region packing models
# ---------------------------------------------------------------------------


class SpatialRegion(BaseModel):
    location_id: str
    name: str
    layer_id: str = "ground"
    x: int
    y: int
    width: int
    height: int
    entrance_x: int
    entrance_y: int
    tags: list[str] = Field(default_factory=list)


class RegionPackingResult(BaseModel):
    regions: list[SpatialRegion] = Field(default_factory=list)
    warnings: list[SpatialInputWarning] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Route rasterization models
# ---------------------------------------------------------------------------


class GridPoint(BaseModel):
    x: int
    y: int


class SpatialRoute(BaseModel):
    path_edge_id: str
    from_location_id: str
    to_location_id: str
    route_tiles: list[GridPoint] = Field(default_factory=list)
    route_type: str = "corridor"
    bidirectional: bool = True
    movement_cost: float = 1.0
    access_tags: list[str] = Field(default_factory=list)


class RouteRasterizationResult(BaseModel):
    routes: list[SpatialRoute] = Field(default_factory=list)
    road_tiles: list[GridPoint] = Field(default_factory=list)
    collision_grid: list[list[int]] = Field(default_factory=list)
    warnings: list[SpatialInputWarning] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
