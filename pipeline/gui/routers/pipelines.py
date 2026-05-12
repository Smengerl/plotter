"""Pipelines API — exposes the in-memory pipeline config cache.

Endpoints:
  GET /api/pipelines   — list all pipeline configs with metadata
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from pipeline.gui import filesystem

router = APIRouter()


@router.get("", response_class=JSONResponse)
async def list_pipelines() -> list[dict[str, Any]]:
    """Return all pipeline configs from the in-memory cache.

    Invalid YAML configs are included with ``valid=false`` and an
    ``error`` message so the frontend can show an "invalid" badge.

    Returns:
        List of pipeline metadata dicts with keys:
        stem, name, description, valid, error.
    """
    pipelines = filesystem.get_pipelines()
    return [
        {
            "stem":        p["stem"],
            "name":        p["name"],
            "description": p["description"],
            "valid":       p["valid"],
            "error":       p["error"],
        }
        for p in pipelines
    ]
