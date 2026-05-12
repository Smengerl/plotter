"""Output images API — list, serve, thumbnail, and download pipeline artifacts.

Filename convention for output images::

    <image_stem>__<pipeline_stem>.png

Endpoints:
  GET /api/output_images
  GET /api/output_images/{name}
  GET /api/output_images/{name}/thumbnail
  GET /api/output_images/{name}/download
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from pipeline.gui import filesystem

router = APIRouter()

_THUMB_SIZE = 256


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thumbnail(path: Path) -> bytes:
    """Create an in-memory JPEG thumbnail (max _THUMB_SIZE px on longest side).

    Args:
        path: Path to the source image.

    Returns:
        JPEG bytes of the thumbnail.
    """
    from PIL import Image  # noqa: PLC0415

    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((_THUMB_SIZE, _THUMB_SIZE))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()


def _get_output_path(name: str, request: Request) -> Path:
    """Resolve *name* to a filesystem path, raising 404 if absent.

    Args:
        name: Output image filename (with extension).
        request: FastAPI request (provides app.state.cfg).

    Returns:
        Resolved Path to the output image.

    Raises:
        HTTPException: 404 if the file does not exist.
    """
    cfg = request.app.state.cfg
    path: Path = cfg.output_dir / name
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": f"Output image '{name}' not found"},
        )
    return path


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_class=JSONResponse)
async def list_output_images() -> list[dict[str, Any]]:
    """Return all output images from the in-memory cache.

    Returns:
        List of dicts with keys: name, source_image, pipeline_stem.
    """
    outputs = filesystem.get_output_images()
    return [
        {
            "name": o["name"],
            "source_image": o["source_image"],
            "pipeline_stem": o["pipeline_stem"],
        }
        for o in outputs
    ]


@router.get("/{name}/thumbnail")
async def thumbnail(name: str, request: Request) -> Response:
    """Return a JPEG thumbnail (max 256 px) for the named output image.

    Args:
        name: Output image filename (with extension).

    Returns:
        JPEG thumbnail bytes.

    Raises:
        HTTPException: 404 if not found, 500 on read error.
    """
    path = _get_output_path(name, request)
    try:
        data = _make_thumbnail(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc
    return Response(content=data, media_type="image/jpeg")


@router.get("/{name}/download")
async def download_output(name: str, request: Request) -> FileResponse:
    """Serve the output image as a file download.

    Args:
        name: Output image filename (with extension).

    Returns:
        File response with Content-Disposition: attachment.

    Raises:
        HTTPException: 404 if not found.
    """
    path = _get_output_path(name, request)
    return FileResponse(
        path,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{name}")
async def serve_output(name: str, request: Request) -> FileResponse:
    """Serve the output image inline.

    Args:
        name: Output image filename (with extension).

    Returns:
        File response with Content-Disposition: inline.

    Raises:
        HTTPException: 404 if not found.
    """
    path = _get_output_path(name, request)
    return FileResponse(
        path,
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
