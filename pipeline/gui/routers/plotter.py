"""Plotter API — send a processed output image to the physical plotter.

Dispatches the dedicated plotter pipeline (configured via
``ServerConfig.plotter_pipeline_stem``) with the given output image as input.

Endpoints:
  POST /api/plotter/send
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.gui import filesystem, job_manager

router = APIRouter()


class SendToPlotterRequest(BaseModel):
    """Request body for POST /api/plotter/send."""

    output_image_name: str


@router.post("/send", status_code=202, response_class=JSONResponse)
async def send_to_plotter(body: SendToPlotterRequest, request: Request) -> dict[str, Any]:
    """Dispatch the plotter pipeline for a given output image.

    Uses the pipeline whose stem matches ``ServerConfig.plotter_pipeline_stem``
    (default: ``"plotter"``).  The output image path is passed as the input to
    the job so the plotter pipeline reads the already-processed artifact.

    Args:
        body: ``{output_image_name}``
        request: FastAPI request (provides app.state.cfg).

    Returns:
        202 with the scheduled job dict.

    Raises:
        HTTPException:
            - 409 if a job is already running
            - 404 if output_image_name not found in filesystem cache
            - 422 if no plotter pipeline is configured / found
    """
    cfg = request.app.state.cfg

    # 409 — already running
    current = job_manager.get_current_job()
    if current and current.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail={"error": "A job is already running"},
        )

    # 404 — output image not in cache
    outputs = {o["name"] for o in filesystem.get_output_images()}
    if body.output_image_name not in outputs:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Output image '{body.output_image_name}' not found"},
        )

    # 422 — no plotter pipeline configured
    plotter_pipeline = filesystem.get_pipeline_by_stem(cfg.plotter_pipeline_stem)
    if plotter_pipeline is None or not plotter_pipeline["valid"]:
        reason = (
            plotter_pipeline["error"]
            if plotter_pipeline and not plotter_pipeline["valid"]
            else f"No pipeline named '{cfg.plotter_pipeline_stem}' found in tools-dir"
        )
        raise HTTPException(
            status_code=422,
            detail={"error": f"Plotter pipeline not available: {reason}"},
        )

    # The output image is used as *input* for the plotter pipeline
    input_path = cfg.output_dir / body.output_image_name
    # Plotter jobs write nothing to the output dir (send_gcode step); use a
    # conventional path so job_manager can clean up on error
    output_path = cfg.output_dir / f"_plotter__{body.output_image_name}"

    asyncio.create_task(
        job_manager.run_job(
            image_name=body.output_image_name,
            pipeline_path=plotter_pipeline["path"],
            input_path=input_path,
            output_path=output_path,
        )
    )

    return job_manager.get_current_job() or {
        "image_name": body.output_image_name,
        "pipeline_stem": cfg.plotter_pipeline_stem,
        "status": "scheduled",
    }
