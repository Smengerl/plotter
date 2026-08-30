"""Pipelines API — exposes the in-memory pipeline config cache.

Endpoints:
  GET /api/pipelines   — list all pipeline configs with metadata
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pipeline.gui import filesystem

router = APIRouter()


@router.get("", response_class=JSONResponse)
async def list_pipelines(request: Request) -> list[dict[str, Any]]:
    """Return the runnable stylizer pipeline configs from the cache.

    The dedicated "Send to Plotter" pipeline (stem
    ``ServerConfig.plotter_pipeline_stem``) is excluded — it is dispatched
    only via ``POST /api/plotter/send``, not run as a regular pipeline.

    Invalid YAML configs are included with ``valid=false`` and an ``error``
    message so the frontend can show an "invalid" badge.
    """
    plotter_stem = request.app.state.cfg.plotter_pipeline_stem
    return [
        {
            "stem":        p["stem"],
            "name":        p["name"],
            "description": p["description"],
            "valid":       p["valid"],
            "error":       p["error"],
        }
        for p in filesystem.get_pipelines()
        if p["stem"] != plotter_stem
    ]
