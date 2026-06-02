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
from worldkernel.architect.spatial.blueprint_exporter import SpatialBlueprintExporter
from worldkernel.architect.spatial.pipeline_adapter import SpatialPipelineAdapter
from worldkernel.architect.spatial.spatial_pipeline import SpatialPipeline, SpatialPipelineResult
from worldkernel.architect.spatial.models import (
    BlueprintGrid,
    BlueprintRegion,
    BlueprintRoute,
    BlueprintSpawnPoint,
    CanonicalSpatialArtifact,
    CharacterPlacementFact,
    E1ValidationResult,
    GridPoint,
    LocationLayout,
    LocationSpatialFact,
    LayoutPlan,
    PathSpatialFact,
    RegionPackingResult,
    RouteRasterizationResult,
    SpatialBlueprint,
    SpatialBuildInput,
    SpatialIndexes,
    SpatialInputWarning,
    SpatialRegion,
    SpatialRoute,
    ValidationIssue,
    ValidationReport,
)
from worldkernel.architect.spatial.region_packer import RegionPacker
from worldkernel.architect.spatial.route_rasterizer import RouteRasterizer
from worldkernel.architect.spatial.spatial_validator import StructuralValidator
from worldkernel.architect.spatial.topology_layout import TopologyLayoutGenerator

__all__ = [
    "BlueprintGrid",
    "BlueprintRegion",
    "BlueprintRoute",
    "BlueprintSpawnPoint",
    "CanonicalSpatialArtifact",
    "CharacterPlacementFact",
    "E1ValidationResult",
    "GridPoint",
    "LocationLayout",
    "LocationSpatialFact",
    "LayoutPlan",
    "PathSpatialFact",
    "RegionPacker",
    "RegionPackingResult",
    "RouteRasterizationResult",
    "RouteRasterizer",
    "SpatialBlueprint",
    "SpatialBlueprintExporter",
    "SpatialBuildInput",
    "SpatialPipeline",
    "SpatialPipelineAdapter",
    "SpatialPipelineResult",
    "SpatialCanvasConfig",
    "SpatialGenerationConfig",
    "SpatialGridValuesConfig",
    "SpatialIndexes",
    "SpatialInputAssembler",
    "SpatialInputAssemblyError",
    "SpatialInputWarning",
    "SpatialLayoutConfig",
    "SpatialRegion",
    "SpatialRenderingConfig",
    "SpatialRoutingConfig",
    "SpatialRoute",
    "SpatialValidationConfig",
    "StructuralValidator",
    "TopologyLayoutGenerator",
    "ValidationIssue",
    "ValidationReport",
    "load_spatial_generation_config",
]
