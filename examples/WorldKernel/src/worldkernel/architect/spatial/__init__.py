"""WorldKernel spatial layer — generates walkable topology maps from semantic artifacts."""

from worldkernel.architect.spatial.config import (
    SpatialCanvasConfig,
    SpatialGenerationConfig,
    SpatialGridValuesConfig,
    SpatialLayoutConfig,
    SpatialRenderingConfig,
    SpatialRoutingConfig,
    SpatialValidationConfig,
    load_spatial_generation_config,
)
from worldkernel.architect.spatial.input_assembler import (
    SpatialInputAssembler,
    SpatialInputAssemblyError,
)
from worldkernel.architect.spatial.models import (
    CharacterPlacementFact,
    GridPoint,
    LocationLayout,
    LocationSpatialFact,
    LayoutPlan,
    PathSpatialFact,
    RegionPackingResult,
    RouteRasterizationResult,
    SpatialBuildInput,
    SpatialInputWarning,
    SpatialRegion,
    SpatialRoute,
)
from worldkernel.architect.spatial.region_packer import RegionPacker
from worldkernel.architect.spatial.route_rasterizer import RouteRasterizer
from worldkernel.architect.spatial.topology_layout import TopologyLayoutGenerator

__all__ = [
    "CharacterPlacementFact",
    "GridPoint",
    "LocationLayout",
    "LocationSpatialFact",
    "LayoutPlan",
    "PathSpatialFact",
    "RegionPacker",
    "RegionPackingResult",
    "RouteRasterizationResult",
    "RouteRasterizer",
    "SpatialBuildInput",
    "SpatialCanvasConfig",
    "SpatialGenerationConfig",
    "SpatialGridValuesConfig",
    "SpatialInputAssembler",
    "SpatialInputAssemblyError",
    "SpatialInputWarning",
    "SpatialLayoutConfig",
    "SpatialRegion",
    "SpatialRenderingConfig",
    "SpatialRoutingConfig",
    "SpatialRoute",
    "SpatialValidationConfig",
    "TopologyLayoutGenerator",
    "load_spatial_generation_config",
]
