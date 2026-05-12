"""Jobs API — start, cancel, and inspect the single pipeline worker slot.

Only one job can run at a time.  A ``POST /api/jobs`` schedules the job
asynchronously and returns 202 immediately so the frontend can start
listening to the SSE stream for progress updates.

Endpoints:
  POST   /api/jobs
  DELETE /api/jobs/current
  GET    /api/jobs/current
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pipeline.gui import filesystem, job_manager

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartJobRequest(BaseModel):
    """Request body for POST /api/jobs."""

    image_name: str
    pipeline_stem: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_class=JSONResponse)
async def start_job(body: StartJobRequest, request: Request) -> dict[str, Any]:
    """Start a new pipeline job.

    Args:
        body: ``{image_name, pipeline_stem}``
        request: FastAPI request (provides app.state.cfg).

    Returns:
        202 with the current job dict.

    Raises:
        HTTPException:
            - 409 if a job is already running
            - 404 if image_name or pipeline_stem not found in cache
            - 422 if the pipeline YAML is marked invalid
    """
    cfg = request.app.state.cfg

    # 409 — already running
    current = job_manager.get_current_job()
    if current and current.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail={"error": "A job is already running"},
        )

    # 404 — image not in cache
    images = {img["name"] for img in filesystem.get_input_images()}
    if body.image_name not in images:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Input image '{body.image_name}' not found"},
        )

    # 404 / 422 — pipeline
    pipeline = filesystem.get_pipeline_by_stem(body.pipeline_stem)
    if pipeline is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Pipeline '{body.pipeline_stem}' not found"},
        )
    if not pipeline["valid"]:
        raise HTTPException(
            status_code=422,
            detail={"error": f"Pipeline '{body.pipeline_stem}' is invalid: {pipeline['error']}"},
        )

    # Resolve paths
    input_path = cfg.input_dir / body.image_name
    image_stem = Path(body.image_name).stem
    output_path = cfg.output_dir / f"{image_stem}__{body.pipeline_stem}.png"

    # Schedule the job without blocking the response
    asyncio.create_task(
        job_manager.run_job(
            image_name=body.image_name,
            pipeline_path=pipeline["path"],
            input_path=input_path,
            output_path=output_path,
        )
    )

    # Return the freshly created job state (status will be "running" momentarily)
    return job_manager.get_current_job() or {
        "image_name": body.image_name,
        "pipeline_stem": body.pipeline_stem,
        "status": "scheduled",
    }


@router.delete("/current")
async def cancel_job() -> Response:
    """Cancel the currently running job.

    Returns:
        204 if a job was running and cancel was requested.

    Raises:
        HTTPException: 404 if no job is currently running.
    """
    was_running = job_manager.request_cancel()
    if not was_running:
        raise HTTPException(
            status_code=404,
            detail={"error": "No job is currently running"},
        )
    return Response(status_code=204)


@router.get("/current", response_class=JSONResponse)
async def get_current_job() -> Response:
    """Return the current (or last completed) job state.

    Returns:
        200 with job dict, or 204 if no job has been run yet.
    """
    job = job_manager.get_current_job()
    if job is None:
        return Response(status_code=204)
    return JSONResponse(content=job)
