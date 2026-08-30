"""In-memory cache of input images, output images, and pipeline configs.

The cache is populated once at server startup via ``init_cache()`` and can be
partially refreshed via ``invalidate(section)``.  All query helpers return
shallow copies so callers cannot accidentally mutate the cached state.

Cache structure::

    {
        "input_images":  list[dict],   # see _scan_input_images()
        "output_images": list[dict],   # see _scan_output_images()
        "pipelines":     list[dict],   # see _scan_pipelines()
    }

No FastAPI or HTTP concerns belong here.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pipeline.gui.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Image formats accepted as "input" images
# ---------------------------------------------------------------------------
_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
)

# ---------------------------------------------------------------------------
# Module-level cache — single source of truth at runtime
# ---------------------------------------------------------------------------
_cache: dict[str, list[dict[str, Any]]] = {
    "input_images": [],
    "output_images": [],
    "pipelines": [],
}

# ServerConfig stored during init so invalidate() can re-use it
_cfg: ServerConfig | None = None


# ---------------------------------------------------------------------------
# Internal scanners
# ---------------------------------------------------------------------------


def _scan_input_images(input_dir: Path) -> list[dict[str, Any]]:
    """Scan *input_dir* and return metadata dicts for every image file found.

    Args:
        input_dir: Directory to scan for input images.

    Returns:
        List of dicts with keys: name, path, width, height, size_bytes, format.
    """
    results: list[dict[str, Any]] = []

    if not input_dir.exists():
        logger.warning("input_dir does not exist: %s", input_dir)
        return results

    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        logger.error("Pillow is not installed — cannot read image metadata")
        Image = None  # type: ignore[assignment]

    for entry in sorted(os.scandir(input_dir), key=lambda e: e.name):
        if not entry.is_file():
            continue
        suffix = Path(entry.name).suffix.lower()
        if suffix not in _IMAGE_EXTENSIONS:
            continue

        width: int | None = None
        height: int | None = None
        fmt: str | None = None

        if Image is not None:
            try:
                with Image.open(entry.path) as img:
                    width, height = img.size
                    fmt = img.format
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not open image %s: %s", entry.path, exc)

        results.append(
            {
                "name": entry.name,
                "path": Path(entry.path),
                "width": width,
                "height": height,
                "size_bytes": entry.stat().st_size,
                "format": fmt,
            }
        )

    return results


def _scan_output_images(output_dir: Path) -> list[dict[str, Any]]:
    """Scan *output_dir* and return metadata dicts for output images.

    Output image naming convention::

        <source_image_stem>__<pipeline_stem>.<ext>

    Args:
        output_dir: Directory to scan for output images.

    Returns:
        List of dicts with keys: name, path, source_image, pipeline_stem.
    """
    results: list[dict[str, Any]] = []

    if not output_dir.exists():
        logger.warning("output_dir does not exist: %s", output_dir)
        return results

    for entry in sorted(os.scandir(output_dir), key=lambda e: e.name):
        if not entry.is_file():
            continue
        suffix = Path(entry.name).suffix.lower()
        if suffix not in _IMAGE_EXTENSIONS:
            continue

        stem = Path(entry.name).stem
        source_image: str | None = None
        pipeline_stem: str | None = None

        if "__" in stem:
            parts = stem.split("__", 1)
            source_image = parts[0]
            pipeline_stem = parts[1]

        results.append(
            {
                "name": entry.name,
                "path": Path(entry.path),
                "source_image": source_image,
                "pipeline_stem": pipeline_stem,
            }
        )

    return results


def _scan_pipelines(tools_dir: Path) -> list[dict[str, Any]]:
    """Scan *tools_dir* for YAML pipeline configs and return metadata dicts.

    Each YAML file is loaded via ``PipelineRunner.from_yaml()`` to read its
    ``name`` (falls back to the file stem) and ``description``.  If loading
    fails the entry is still included with ``valid=False`` and the exception
    message in ``error``.

    Args:
        tools_dir: Directory to scan for ``*.yaml`` / ``*.yml`` pipeline files.

    Returns:
        List of dicts with keys: stem, path, name, description, valid, error.
    """
    # Import here to avoid circular imports at module load time
    from pipeline.core.runner import PipelineRunner  # noqa: PLC0415

    results: list[dict[str, Any]] = []

    if not tools_dir.exists():
        logger.warning("tools_dir does not exist: %s", tools_dir)
        return results

    yaml_extensions = frozenset({".yaml", ".yml"})

    for entry in sorted(os.scandir(tools_dir), key=lambda e: e.name):
        if not entry.is_file():
            continue
        path = Path(entry.path)
        if path.suffix.lower() not in yaml_extensions:
            continue

        stem = path.stem
        name: str = stem
        description: str | None = None
        valid: bool = True
        error: str | None = None

        try:
            runner = PipelineRunner.from_yaml(path)
            # from_yaml falls back to the file stem when the YAML has no
            # "name" key, so runner.name is always a usable display name.
            name = runner.name
            description = runner.description
        except Exception as exc:  # noqa: BLE001
            valid = False
            error = str(exc)
            logger.warning("Could not load pipeline '%s': %s", stem, exc)

        results.append(
            {
                "stem": stem,
                "path": path,
                "name": name,
                "description": description,
                "valid": valid,
                "error": error,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_cache(cfg: ServerConfig) -> None:
    """Populate all three cache sections by scanning the configured directories.

    Must be called once at server startup before any query function is used.

    Args:
        cfg: Server configuration providing the directory paths.
    """
    global _cfg  # noqa: PLW0603
    _cfg = cfg

    logger.info("Initialising filesystem cache …")
    _cache["input_images"] = _scan_input_images(cfg.input_dir)
    _cache["output_images"] = _scan_output_images(cfg.output_dir)
    _cache["pipelines"] = _scan_pipelines(cfg.tools_dir)

    logger.info(
        "Cache ready — %d input image(s), %d output image(s), %d pipeline(s)",
        len(_cache["input_images"]),
        len(_cache["output_images"]),
        len(_cache["pipelines"]),
    )


def invalidate(section: Literal["input_images", "output_images", "pipelines"]) -> None:
    """Rescan only the affected directory and refresh the cache section.

    Args:
        section: Which cache section to refresh.

    Raises:
        RuntimeError: If ``init_cache()`` has not been called yet.
    """
    if _cfg is None:
        raise RuntimeError("filesystem.init_cache() must be called before invalidate()")

    if section == "input_images":
        _cache["input_images"] = _scan_input_images(_cfg.input_dir)
    elif section == "output_images":
        _cache["output_images"] = _scan_output_images(_cfg.output_dir)
    elif section == "pipelines":
        _cache["pipelines"] = _scan_pipelines(_cfg.tools_dir)
    else:
        raise ValueError(f"Unknown cache section: {section!r}")

    logger.debug("Cache section '%s' refreshed (%d item(s))", section, len(_cache[section]))


# ---------------------------------------------------------------------------
# Query helpers — always return copies
# ---------------------------------------------------------------------------


def get_input_images() -> list[dict[str, Any]]:
    """Return a copy of all cached input image metadata dicts.

    Returns:
        List of dicts with keys: name, path, width, height, size_bytes, format.
    """
    return copy.deepcopy(_cache["input_images"])


def get_output_images() -> list[dict[str, Any]]:
    """Return a copy of all cached output image metadata dicts.

    Returns:
        List of dicts with keys: name, path, source_image, pipeline_stem.
    """
    return copy.deepcopy(_cache["output_images"])


def get_pipelines() -> list[dict[str, Any]]:
    """Return a copy of all cached pipeline metadata dicts.

    Returns:
        List of dicts with keys: stem, path, name, description, valid, error.
    """
    return copy.deepcopy(_cache["pipelines"])


def get_pipeline_by_stem(stem: str) -> dict[str, Any] | None:
    """Return a copy of the pipeline entry matching *stem*, or ``None``.

    Args:
        stem: Pipeline filename stem (without extension).

    Returns:
        Pipeline metadata dict, or None if not found.
    """
    for entry in _cache["pipelines"]:
        if entry["stem"] == stem:
            return copy.deepcopy(entry)
    return None


def get_output_images_for_input(image_name: str) -> list[dict[str, Any]]:
    """Return all output images derived from a specific input image.

    Matches on ``source_image`` field (the stem part before ``__``).

    Args:
        image_name: Input image filename (with or without extension).

    Returns:
        List of matching output image metadata dicts.
    """
    # Support both "photo.jpg" and "photo" as the query
    stem = Path(image_name).stem
    return copy.deepcopy(
        [e for e in _cache["output_images"] if e.get("source_image") == stem]
    )
