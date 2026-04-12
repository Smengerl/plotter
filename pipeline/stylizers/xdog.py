"""
pipeline/stylizers/xdog.py — eXtended Difference-of-Gaussians

Erzeugt einen Pencil-Sketch-ähnlichen Linienstil durch Differenz zweier
Gauß-Filter kombiniert mit einer weichen Sigmoid-Schwelle.

Referenz: Winnemöller et al. 2012,
          "XDoG: An eXtended difference-of-Gaussians compendium
           including advanced image stylization"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np

from pipeline.stylizers.base import BaseStylizer

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class XDoGStylizer(BaseStylizer):
    """
    eXtended Difference-of-Gaussians Stilisierer.

    Parameters
    ----------
    sigma     : Standardabweichung der kleineren Gauss-Funktion
    k_sigma   : Verhältnis σ_groß / σ_klein
    epsilon   : Schwellenwert für die weiche Binarisierung (-1 … 1; 0 = Median)
    phi       : Steilheit der Sigmoid-Funktion
    threshold : Finaler Schwellenwert (0–255) für die harte Binarisierung
    """

    name = "xdog"

    def __init__(
        self,
    sigma: float = 0.8,
        k_sigma: float = 1.6,
        epsilon: float = 0.0,
        phi: float = 5.0,
        threshold: float = 0.0,
    ) -> None:
        self.sigma = sigma
        self.k_sigma = k_sigma
        self.epsilon = epsilon
        self.phi = phi
        self.threshold = threshold

    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        img = gray.astype(np.float32) / 255.0

        g1 = cv2.GaussianBlur(img, (0, 0), self.sigma)
        g2 = cv2.GaussianBlur(img, (0, 0), self.sigma * self.k_sigma)

        dog = g1 - g2

        # Adaptive Epsilon: falls der Benutzer epsilon==0 (Default),
        # wählen wir ein hohes Perzentil aus dem dog‑Bild als Schwellwert.
        # Das macht XDoG robust gegenüber unterschiedlich kontrastreichen Bildern.
        if float(self.epsilon) == 0.0:
            eps = float(np.percentile(dog, 90))
            if eps <= 0.0:
                eps = float(np.percentile(dog, 75))
            if eps <= 0.0:
                eps = 0.01
        else:
            eps = float(self.epsilon)

        # Weiche Thresholdfunktion (Winnemöller) mit adaptivem eps
        xdog = np.where(
            dog >= eps,
            1.0,
            1.0 + np.tanh(self.phi * (dog - eps)),
        ).astype(np.float32)

        xdog_uint8 = (xdog * 255).clip(0, 255).astype(np.uint8)

        # Finales Binarisieren: falls threshold <= 0 angegeben wurde,
        # verwenden wir Otsu als automatischen Fallback; sonst festen Wert.
        if float(self.threshold) <= 0.0:
            _, binary = cv2.threshold(xdog_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            used_thresh = 'otsu'
        else:
            _, binary = cv2.threshold(xdog_uint8, int(self.threshold), 255, cv2.THRESH_BINARY)
            used_thresh = int(self.threshold)

        # XDoG liefert helle Flächen als Linie → invertieren damit Linie=255
        binary = cv2.bitwise_not(binary)

        logger.debug(
            "XDoG: σ=%.2f k=%.2f eps=%.4f phi=%.1f thr=%s",
            self.sigma, self.k_sigma, eps, self.phi, used_thresh,
        )
        return binary.astype(np.uint8)
