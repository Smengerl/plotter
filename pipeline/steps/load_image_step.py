"""
pipeline/steps/load_image_step.py - Load image from disk into ImageContext

This step is the canonical entry point for image data in the pipeline.
It loads the source image, converts it to RGB, and stores it in ``ctx.image``
(PIL).

CV stylization steps (Canny, XDoG, Adaptive, …) derive their grayscale
working array from ``ctx.image`` themselves via ``CVBaseStep._get_gray()``.
This keeps ``ctx.intermediates`` free of transient format conversions and
makes ``ctx.image`` the single source of truth for image data.

Data transport via ImageContext
--------------------------------
Reads   ctx.metadata["source_path"]  - Path to input image file (Path or str)
Writes  ctx.image                    - PIL.Image (RGB)
        ctx.metadata["source_shape"] - (H, W) of the loaded (possibly scaled) image
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image as PILImage

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.steps.base.stylizer_base import load_gray

logger = logging.getLogger(__name__)


class LoadImageStep(PipelineStep):
    """
    Load the source image from disk and populate ``ctx.image``.

    This step **must** be the first step in any pipeline that uses
    image data.  It reads ``metadata["source_path"]``, scales the image
    to at most ``style_res`` pixels on the longest side, and stores:

    * ``ctx.image``                   — PIL RGB image (canonical image carrier)
    * ``ctx.metadata["source_shape"]`` — (H, W) after scaling

    CV stylization steps (Canny, XDoG, Adaptive, …) derive their grayscale
    working array from ``ctx.image`` via ``CVBaseStep._get_gray()`` — they
    do not rely on a pre-computed ``ctx.intermediates["gray"]``.

    Config keys    Default  Meaning
    -----------------------------------------------
    style_res      1024     Maximum side length in pixels after scaling.
                            0 or None = load at full resolution.
    """

    def requires(self) -> list[str]:
        return ["metadata.source_path"]

    def process(self, ctx: ImageContext) -> ImageContext:
        # If an image is already present in the context, do not re-load from disk.
        # This can happen when callers (like the stylizer smoke runner) pre-load
        # the image into the context. In that case warn the user and keep the
        # existing image so downstream steps operate on the same object.
        if ctx.has_image:
            logger.warning(
                "LoadImageStep: ctx.image already set — skipping disk load (source_path=%s)",
                ctx.metadata.get("source_path"),
            )
            # Ensure source_shape metadata exists so downstream steps relying on
            # it (or tests) can access image dimensions.
            try:
                if "source_shape" not in ctx.metadata:
                    h, w = ctx.image_as_gray.shape
                    ctx.metadata["source_shape"] = (h, w)
            except Exception:
                # If anything goes wrong while querying the existing image,
                # don't prevent the pipeline from continuing — we've already
                # logged a warning above.
                pass
            return ctx

        source_path = Path(ctx.metadata["source_path"])
        max_side: int = int(self.config.get("style_res", 1024) or 0)

        if not source_path.exists():
            raise FileNotFoundError(f"LoadImageStep: image not found: {source_path}")

        # --- Load grayscale array (scaled) then convert to RGB PIL ---
        gray = load_gray(source_path, max_side) if max_side > 0 else _load_full_gray(source_path)
        h, w = gray.shape

        rgb_array = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        pil_image = PILImage.fromarray(rgb_array, mode="RGB")

        ctx.image = pil_image
        ctx.metadata["source_shape"] = (h, w)

        logger.debug(
            "LoadImageStep: %s → %dx%d px (style_res=%s)",
            source_path.name, w, h, max_side or "full",
        )
        return ctx


def _load_full_gray(path: Path) -> "np.ndarray":
    """Load image at full resolution as grayscale uint8 array."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image could not be loaded: {path}")
    return img.astype(np.uint8)
