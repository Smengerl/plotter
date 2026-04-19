"""
pipeline/steps/stylise_canny_step.py - Canny edge detection as PipelineStep

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


class StyliseCannyStep(StylizerStep):
    """
    Stylization step with Canny edge detector.

    Requires ``LoadImageStep`` to run first so that ``ctx.image`` is set.
    Converts ``ctx.image`` to grayscale via ``ctx.gray``.

    Config key     Default  Corresponds to CLI flag
    ------------------------------------------------
    style_res         1024     --style-res  (handled by LoadImageStep)
    canny_low         50       --canny-low
    canny_high        150      --canny-high
    canny_blur        3        --canny-blur
    """

    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        c = self.config
        low: int = int(c.get("canny_low", 50))
        high: int = int(c.get("canny_high", 150))
        blur: int = ensure_odd(int(c.get("canny_blur", 3)))

        gray: npt.NDArray[np.uint8] = ctx.image_as_gray
        logger.debug("[canny] Image: %dx%d px", gray.shape[1], gray.shape[0])

        blurred = cv2.GaussianBlur(gray, (blur, blur), 0)
        binary = cv2.Canny(blurred, low, high).astype("uint8")
        logger.debug(
            "StyliseCannyStep: low=%d  high=%d  blur=%d",
            low, high, blur,
        )
        return binary

