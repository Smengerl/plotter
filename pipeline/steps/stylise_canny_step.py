"""
pipeline/steps/stylise_canny_step.py — Canny-Kantenerkennung als PipelineStep

Datentransport via ImageContext
--------------------------------
Liest   ctx.metadata["source_path"]  — Pfad zur Eingabebilddatei
Schreibt ctx.intermediates["binary"] — uint8-Array (H, W), 255=Linie
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.steps.base.stylizer_base import ensure_odd, load_gray

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class StyliseCannyStep(PipelineStep):
    """
    Stylization step with Canny edge detector.

    Config key     Default  Corresponds to CLI flag
    ------------------------------------------------
    style_res         1024     --style-res
    canny_low         50       --canny-low
    canny_high        150      --canny-high
    canny_blur        3        --canny-blur
    """

    def process(self, ctx: ImageContext) -> ImageContext:
        c = self.config
        low: int = int(c.get("canny_low", 50))
        high: int = int(c.get("canny_high", 150))
        blur: int = ensure_odd(int(c.get("canny_blur", 3)))
        max_side: int = int(c.get("style_res", 1024))

        gray: npt.NDArray[np.uint8] = load_gray(ctx.metadata["source_path"], max_side)
        logger.debug("[canny] Bild geladen: %dx%d px", gray.shape[1], gray.shape[0])

        blurred = cv2.GaussianBlur(gray, (blur, blur), 0)
        binary = cv2.Canny(blurred, low, high).astype("uint8")
        logger.debug(
            "StyliseCannyStep: low=%d  high=%d  blur=%d  → %dx%d px",
            low, high, blur, binary.shape[1], binary.shape[0],
        )

        ctx.intermediates["binary"] = binary
        return ctx

