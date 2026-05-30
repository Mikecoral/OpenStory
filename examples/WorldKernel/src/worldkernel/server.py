from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from worldkernel.constraints import load_generation_constraints
from worldkernel.llm import client as llm_client
from worldkernel.stage1.pipeline import Stage1Error, run_stage1

BASE_DIR = Path(__file__).parent.parent.parent
CONFIGS_DIR = BASE_DIR / "configs"
TEMPLATES_DIR = BASE_DIR / "templates"
FRONTEND_DIR = BASE_DIR / "frontend"

_constraints = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _constraints
    load_dotenv(BASE_DIR / ".env")
    llm_client.init(CONFIGS_DIR / "models.yaml")
    _constraints = load_generation_constraints(CONFIGS_DIR / "architect.yaml")
    yield


app = FastAPI(title="WorldKernel Stage 1", lifespan=lifespan)


@app.exception_handler(Stage1Error)
async def stage1_error_handler(request: Request, exc: Stage1Error) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": str(exc), "step": exc.step, "detail": str(exc.cause)},
    )


class ParseRequest(BaseModel):
    input: str


@app.post("/api/stage1/parse")
async def parse(req: ParseRequest):
    session = await run_stage1(req.input, constraints=_constraints)
    return session


@app.get("/api/stage1/session/{session_id}")
async def get_session(session_id: str):
    session_dir = TEMPLATES_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")
    files = sorted(
        str(f.relative_to(session_dir)).replace("\\", "/")
        for f in session_dir.rglob("*.json")
    )
    return {"session_id": session_id, "files": files}


@app.get("/api/stage1/session/{session_id}/{path:path}")
async def get_session_file(session_id: str, path: str):
    file_path = TEMPLATES_DIR / session_id / path
    if not file_path.exists() or file_path.suffix not in (".json", ".yaml"):
        raise HTTPException(status_code=404, detail="file not found")
    import json
    if file_path.suffix == ".yaml":
        import yaml
        return yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return json.loads(file_path.read_text(encoding="utf-8"))


@app.post("/api/stage2/generate/{session_id}")
async def stage2_generate(session_id: str):
    session_dir = TEMPLATES_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    from worldkernel.architect import (
        compile_stage1_init_context,
        create_default_schema_registry,
        create_default_tool_registry,
        load_stage1_session_schema_source,
        save_semantic_artifacts,
    )
    from worldkernel.architect.semantic.runner import InitDAGRunner

    sr = create_default_schema_registry()
    load_stage1_session_schema_source(
        session_dir, sr, source_id="visual-e2e", world_id=session_id,
    )
    tr = create_default_tool_registry(sr)
    ctx = compile_stage1_init_context(
        session_dir, tool_registry=tr, source_id="visual-e2e", world_id=session_id,
        constraints=_constraints,
    )

    runner = InitDAGRunner(schema_registry=sr, tool_registry=tr)
    state = await runner.run_async(ctx)

    loc_result = (
        state.result_store.get_step_result("generate_locations")
        if state.result_store.has_step_result("generate_locations")
        else None
    )
    report = save_semantic_artifacts(
        session_id, ctx, state,
        output_root=session_dir / "generated" / "artifacts",
    )

    return {
        "completed_steps": state.completed_steps,
        "errors": state.errors,
        "locations": {
            "count": len(loc_result.items) if loc_result else 0,
            "avg_score": (
                loc_result.provenance.get("quality_summary", {}).get("avg_review_score")
                if loc_result else None
            ),
        },
        "report": {"success": report.success, "counts": report.counts},
    }


@app.post("/api/spatial/generate/{session_id}")
async def spatial_generate(session_id: str):
    semantic_root = TEMPLATES_DIR / session_id / "generated" / "artifacts"
    if not semantic_root.exists():
        raise HTTPException(status_code=404, detail="semantic artifacts not found; run Stage2 first")

    from worldkernel.architect.spatial.config import load_spatial_generation_config
    from worldkernel.architect.spatial.input_assembler import (
        SpatialInputAssembler,
        SpatialInputAssemblyError,
    )
    from worldkernel.architect.spatial.models import SpatialBuildInput
    from worldkernel.architect.spatial.region_packer import RegionPacker
    from worldkernel.architect.spatial.route_rasterizer import RouteRasterizer
    from worldkernel.architect.spatial.topology_layout import TopologyLayoutGenerator

    config = load_spatial_generation_config(CONFIGS_DIR / "architect.yaml")

    try:
        assembler = SpatialInputAssembler()
        build_input = assembler.assemble(world_id=session_id, semantic_root=semantic_root)
    except SpatialInputAssemblyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    layout_gen = TopologyLayoutGenerator()
    layout_plan = layout_gen.generate(build_input, config)

    packer = RegionPacker()
    packing_result = packer.pack(layout_plan, build_input, config)

    rasterizer = RouteRasterizer()
    raster_result = rasterizer.rasterize(build_input, layout_plan, packing_result, config)

    all_warnings = packing_result.warnings + raster_result.warnings

    return {
        "world_id": session_id,
        "grid": {
            "width": config.canvas.grid_width,
            "height": config.canvas.grid_height,
            "tile_size": config.canvas.tile_size,
        },
        "regions": [r.model_dump(mode="json") for r in packing_result.regions],
        "routes": [r.model_dump(mode="json") for r in raster_result.routes],
        "layout": [loc.model_dump(mode="json") for loc in layout_plan.locations],
        "warnings": [w.model_dump(mode="json") for w in all_warnings],
        "provenance": {
            "packing": packing_result.provenance,
            "routing": raster_result.provenance,
        },
    }


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("worldkernel.server:app", host="0.0.0.0", port=8100, reload=True)
