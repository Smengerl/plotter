"""
pipeline/steps/stylise_adaptive_step.py - Adaptive threshold stylization as PipelineStep

Data transport via ImageContext
--------------------------------
Reads   ctx.image                    - PIL RGB image set by LoadImageStep
Writes  ctx.intermediates["binary"]  - uint8 array (H, W), 255=line
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2

from pipeline.core.base import ImageContext
from pipeline.steps.base.stylizer_base import StylizerStep, ensure_odd

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class StyliseAdaptiveStep(StylizerStep):
    """
    Stylization step using adaptive threshold.

    Requires ``LoadImageStep`` to run first so that ``ctx.image`` is set.
    Converts ``ctx.image`` to grayscale via ``ctx.gray``.

    config keys    Default     Corresponds to CLI flag
    ------------------------------------------------
    style_res      1024        --style-res  (handled by LoadImageStep)
    block_size     11          --block-size
    adapt_c        2.0         --adapt-c
    adapt_method   "gaussian"  --adapt-method
    adapt_blur     0           --adapt-blur
    """

    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        c = self.config
        block_size: int = ensure_odd(max(3, int(c.get("block_size", 11))))
        adapt_c: float = float(c.get("adapt_c", 2.0))
        method: str = str(c.get("adapt_method", "gaussian"))
        blur: int = int(c.get("adapt_blur", 0))

        gray: npt.NDArray[np.uint8] = ctx.image_as_gray
        logger.debug("[adaptive] Image: %dx%d px", gray.shape[1], gray.shape[0])

        img = gray.copy()
        if blur > 0:
            k = ensure_odd(blur)
            img = cv2.GaussianBlur(img, (k, k), 0)

        adaptive_method = (
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C
            if method == "gaussian"
            else cv2.ADAPTIVE_THRESH_MEAN_C
        )
        binary = cv2.adaptiveThreshold(
            img,
            maxValue=255,
            adaptiveMethod=adaptive_method,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=block_size,
            C=adapt_c,
        )
        # adaptiveThreshold THRESH_BINARY: dark lines on white background (0=line)
        # For the plotter: invert so line=255
        binary = cv2.bitwise_not(binary)
        logger.debug(
            "StyliseAdaptiveStep: method=%s  block=%d  C=%.1f  blur=%d",
            method, block_size, adapt_c, blur,
        )
        return binary

