"""
pipeline/steps/stylise_xdog_step.py - XDoG stylization as PipelineStep

Data transport via ImageContext
--------------------------------
Reads   ctx.image                    - PIL RGB image set by LoadImageStep
Writes  ctx.intermediates["binary"]  - uint8 array (H, W), 255=line
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np

from pipeline.core.base import ImageContext
from pipeline.steps.base.stylizer_base import StylizerStep

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class StyliseXDoGStep(StylizerStep):
    """
    Stylization step using eXtended Difference-of-Gaussians (XDoG).

    Winnemöller et al. 2012

    Requires ``LoadImageStep`` to run first so that ``ctx.image`` is set.
    Converts ``ctx.image`` to grayscale via ``ctx.gray``.

    config keys    Default  Corresponds to CLI flag
    -----------------------------------------------
    style_res      1024     --style-res  (handled by LoadImageStep)
    sigma          0.4      --sigma
    k_sigma        1.6      --k-sigma
    epsilon        0.0      --epsilon
    phi            10.0     --phi
    threshold      20.0     --threshold
    """

    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        c = self.config
        sigma: float = float(c.get("sigma", 0.4))
        k_sigma: float = float(c.get("k_sigma", 1.6))
        epsilon: float = float(c.get("epsilon", 0.0))
        phi: float = float(c.get("phi", 10.0))
        threshold: float = float(c.get("threshold", 20.0))

        gray: npt.NDArray[np.uint8] = ctx.image_as_gray
        logger.debug("[xdog] Image: %dx%d px", gray.shape[1], gray.shape[0])

        img = gray.astype(np.float32) / 255.0
        g1 = cv2.GaussianBlur(img, (0, 0), sigma)
        g2 = cv2.GaussianBlur(img, (0, 0), sigma * k_sigma)
        dog = g1 - g2

        # Adaptive epsilon: if 0 (default), use high percentile as threshold
        if epsilon == 0.0:
            eps = float(np.percentile(dog, 90))
            if eps <= 0.0:
                eps = float(np.percentile(dog, 75))
            if eps <= 0.0:
                eps = 0.01
        else:
            eps = epsilon

        xdog = np.where(
            dog >= eps,
            1.0,
            1.0 + np.tanh(phi * (dog - eps)),
        ).astype(np.float32)

        xdog_uint8 = (xdog * 255).clip(0, 255).astype(np.uint8)

        if threshold <= 0.0:
            _, binary = cv2.threshold(xdog_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            used_thresh: int | str = "otsu"
        else:
            _, binary = cv2.threshold(xdog_uint8, int(threshold), 255, cv2.THRESH_BINARY)
            used_thresh = int(threshold)

        # XDoG: bright areas = line → invert so line=255
        binary = cv2.bitwise_not(binary)
        logger.debug(
            "StyliseXDoGStep: σ=%.2f k=%.2f eps=%.4f phi=%.1f thr=%s",
            sigma, k_sigma, eps, phi, used_thresh,
        )
        return binary

