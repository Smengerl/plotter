"""
pipeline/stylizers/adaptive_threshold.py — Adaptive-Threshold Stilisierer

Binarisiert das Bild mit OpenCV's adaptivem Schwellenwert-Algorithmus.
Im Gegensatz zu einem globalen Schwellenwert berechnet der adaptive Ansatz
für jede Region des Bildes lokal einen eigenen Schwellenwert. Dadurch
werden auch bei ungleichmäßiger Beleuchtung oder Helligkeitsgradienten
feine Strukturen und Texturen erhalten.

Zwei Berechnungsmethoden stehen zur Wahl:
  mean    — Schwellenwert = Mittelwert der Nachbarschaft
  gaussian — Schwellenwert = Gauss-gewichteter Mittelwert (glattere Kanten)

Typische Anwendung: Handzeichnungen, Dokumente, Skizzen, Texturen.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

import cv2
import numpy as np

from pipeline.stylizers.base import BaseStylizer

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)

AdaptiveMethod = Literal["mean", "gaussian"]


class AdaptiveThresholdStylizer(BaseStylizer):
    """
    Adaptiver Schwellenwert-Stilisierer.

    Parameters
    ----------
    block_size : Größe der lokalen Nachbarschaft in Pixeln (muss ungerade und ≥ 3 sein).
                 Kleinere Werte → feinere Details; größere Werte → großflächigere Regionen.
    c          : Konstante, die vom berechneten Schwellenwert subtrahiert wird.
                 Positive Werte unterdrücken schwaches Rauschen (heller Hintergrund bleibt weiß).
                 Negative Werte betonen schwache Kanten stärker.
    method     : ``"gaussian"`` (Standard, glattere Kanten) oder ``"mean"``
    blur       : Gauss-Blur-Kernelgröße vor der Schwellenwert-Berechnung
                 (0 = kein Blur, muss ungerade sein).
    invert     : ``True`` → helle Linien auf dunklem Hintergrund (Standard für Plotter:
                 Linie = 255); ``False`` → dunkle Linien auf hellem Hintergrund.
    """

    name = "adaptive"

    def __init__(
        self,
        block_size: int = 11,
        c: float = 2.0,
        method: AdaptiveMethod = "gaussian",
        blur: int = 0,
        invert: bool = True,
    ) -> None:
        self.block_size = self._ensure_odd(max(3, block_size))
        self.c = c
        self.method: AdaptiveMethod = method
        self.blur = blur
        self.invert = invert

    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        img = gray.copy()

        # Optionaler Rauschunterdrückungs-Blur
        if self.blur > 0:
            k = self._ensure_odd(self.blur)
            img = cv2.GaussianBlur(img, (k, k), 0)

        adaptive_method = (
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C
            if self.method == "gaussian"
            else cv2.ADAPTIVE_THRESH_MEAN_C
        )

        binary = cv2.adaptiveThreshold(
            img,
            maxValue=255,
            adaptiveMethod=adaptive_method,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=self.block_size,
            C=self.c,
        )

        # adaptiveThreshold mit THRESH_BINARY: dunkle Linien auf weißem Grund (0=Linie)
        # Für den Plotter: invertieren, damit Linie=255
        if self.invert:
            binary = cv2.bitwise_not(binary)

        logger.debug(
            "AdaptiveThreshold: method=%s  block=%d  C=%.1f  blur=%d  invert=%s",
            self.method, self.block_size, self.c, self.blur, self.invert,
        )
        return binary.astype(np.uint8)
