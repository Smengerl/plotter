"""Input images API — list, serve, upload, and delete source images.

Endpoints:
  GET    /api/input_images
  GET    /api/input_images/{name}/thumbnail
  GET    /api/input_images/{name}/full
  GET    /api/input_images/{name}/download
  POST   /api/input_images/upload
  DELETE /api/input_images/{name}
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from pipeline.gui import filesystem, notify
from pipeline.gui import job_manager

router = APIRouter()

_THUMB_SIZE = 256
_ACCEPTED_MIME = {"image/jpeg", "image/png", "image/tiff"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_status(
    image_name: str,
    output_images: list[dict[str, Any]],
    current_job: dict[str, Any] | None,
) -> tuple[str, str | None]:
    """Derive (status, error_reason) for an input image.

    Priority: running > error > done > new.

    Args:
        image_name: Filename of the input image (with extension).
        output_images: All cached output image entries.
        current_job: Current job dict from job_manager, or None.

    Returns:
        Tuple of (status_string, error_reason_or_None).
    """
    stem = Path(image_name).stem

    if current_job and current_job.get("status") == "running":
        if current_job.get("image_name") == image_name:
            return "running", None

    # Count outputs derived from this image
    related = [o for o in output_images if o.get("source_image") == stem]
    done_count = len(related)

    # Check the last job for this image (error detection)
    if current_job and current_job.get("image_name") == image_name:
        if current_job.get("status") == "error":
            return "error", current_job.get("error_reason")

    if done_count > 0:
        return "done", None

    return "new", None


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_class=JSONResponse)
async def list_input_images(request: Request) -> list[dict[str, Any]]:
    """Return all input images with status information.

    Returns:
        List of dicts with name, width, height, size_bytes, format,
        status, done_count, error_reason.
    """
    images = filesystem.get_input_images()
    outputs = filesystem.get_output_images()
    current_job = job_manager.get_current_job()

    result = []
    for img in images:
        stem = Path(img["name"]).stem
        done_count = sum(1 for o in outputs if o.get("source_image") == stem)
        status, error_reason = _derive_status(img["name"], outputs, current_job)
        result.append(
            {
                "name": img["name"],
                "width": img["width"],
                "height": img["height"],
                "size_bytes": img["size_bytes"],
                "format": img["format"],
                "status": status,
                "done_count": done_count,
                "error_reason": error_reason,
            }
        )
    return result


@router.get("/{name}/thumbnail")
async def thumbnail(name: str, request: Request) -> Response:
    """Return a JPEG thumbnail (max 256 px) for the named input image.

    Args:
        name: Input image filename (with extension).

    Returns:
        JPEG thumbnail bytes.

    Raises:
        HTTPException: 404 if image not found.
    """
    cfg = request.app.state.cfg
    path = cfg.input_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": f"Image '{name}' not found"})
    try:
        data = _make_thumbnail(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc
    return Response(content=data, media_type="image/jpeg")


@router.get("/{name}/full")
async def full_image(name: str, request: Request) -> FileResponse:
    """Serve the full input image inline.

    Args:
        name: Input image filename (with extension).

    Returns:
        File response with Content-Disposition: inline.

    Raises:
        HTTPException: 404 if image not found.
    """
    cfg = request.app.state.cfg
    path = cfg.input_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": f"Image '{name}' not found"})
    return FileResponse(path, headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.get("/{name}/download")
async def download_image(name: str, request: Request) -> FileResponse:
    """Serve the input image as a file download.

    Args:
        name: Input image filename (with extension).

    Returns:
        File response with Content-Disposition: attachment.

    Raises:
        HTTPException: 404 if image not found.
    """
    cfg = request.app.state.cfg
    path = cfg.input_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": f"Image '{name}' not found"})
    return FileResponse(
        path,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/upload", response_class=JSONResponse)
async def upload_images(request: Request, files: list[UploadFile]) -> JSONResponse:
    """Upload one or more input images.

    Accepted MIME types: image/jpeg, image/png, image/tiff.
    Existing files with the same name are silently overwritten; their
    matching output images are also deleted.

    Args:
        files: Uploaded files from multipart/form-data.

    Returns:
        200 with list of uploaded filenames.

    Raises:
        HTTPException: 422 if any file has an unsupported MIME type.
    """
    cfg = request.app.state.cfg

    for f in files:
        if f.content_type not in _ACCEPTED_MIME:
            raise HTTPException(
                status_code=422,
                detail={"error": f"Unsupported MIME type '{f.content_type}' for '{f.filename}'"},
            )

    uploaded: list[str] = []
    for f in files:
        filename = f.filename or "upload"
        dest = cfg.input_dir / filename
        stem = Path(filename).stem

        # Delete matching output images on overwrite
        if dest.exists():
            for out in cfg.output_dir.glob(f"{stem}__*"):
                try:
                    out.unlink()
                except OSError:
                    pass

        dest.write_bytes(await f.read())
        uploaded.append(filename)

    filesystem.invalidate("input_images")
    filesystem.invalidate("output_images")
    notify.emit_refresh()

    return JSONResponse(content={"uploaded": uploaded})


@router.delete("/{name}")
async def delete_image(name: str, request: Request) -> Response:
    """Delete an input image and all associated output images.

    Args:
        name: Input image filename (with extension).

    Returns:
        204 No Content.

    Raises:
        HTTPException: 404 if image not found.
    """
    cfg = request.app.state.cfg
    path = cfg.input_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": f"Image '{name}' not found"})

    stem = Path(name).stem
    path.unlink()

    for out in cfg.output_dir.glob(f"{stem}__*"):
        try:
            out.unlink()
        except OSError:
            pass

    filesystem.invalidate("input_images")
    filesystem.invalidate("output_images")
    notify.emit_refresh()

    return Response(status_code=204)
