"""
pipeline/stylizers/canny.py — Canny-Kantendetektor

Klassischer, schneller Kantendetektor aus OpenCV.
Kein Modell nötig, keine zusätzlichen Abhängigkeiten.

Referenz: Canny 1986, "A Computational Approach to Edge Detection"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2

from pipeline.stylizers.base import BaseStylizer

if TYPE_CHECKING:
    import numpy.typing as npt
    import numpy as np

logger = logging.getLogger(__name__)


class CannyStylizer(BaseStylizer):
    """
    Canny-Kantendetektor.

    Parameters
    ----------
    low       : Untere Hysterese-Schwelle (0–255)
    high      : Obere Hysterese-Schwelle (0–255)
    blur      : Gauss-Blur-Kernelgröße in Pixeln (wird auf ungerade aufgerundet)
    """

    name = "canny"

    def __init__(self, low: int = 50, high: int = 150, blur: int = 3) -> None:
        self.low = low
        self.high = high
        self.blur = blur

    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        blur = self._ensure_odd(self.blur)
        blurred = cv2.GaussianBlur(gray, (blur, blur), 0)
        edges = cv2.Canny(blurred, self.low, self.high)
        logger.debug("Canny: low=%d  high=%d  blur=%d", self.low, self.high, blur)
        return edges  # cv2.Canny liefert bereits 0/255
