"""
pipeline/stylizers/base.py — Abstrakte Basisklasse für alle Stilisierungs-Methoden

Jede konkrete Implementierung erbt von ``BaseStylizer`` und implementiert
``apply()``.  Die gemeinsame Lade- und Skalierungslogik liegt hier.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class BaseStylizer(ABC):
    """
    Abstrakte Basisklasse für alle Stilisierer.

    Subklassen müssen ``apply()`` implementieren.  Die Methode erhält ein
    vorgeladenes Graustufen-Array und gibt ein Binärbild (uint8, 0/255) zurück,
    bei dem 255 eine Linie und 0 den Hintergrund repräsentiert.

    Beispiel für eine eigene Implementierung::

        class MyStylizer(BaseStylizer):
            name = "my_style"

            def apply(self, gray):
                # ... beliebige Transformation ...
                return binary_uint8
    """

    #: Eindeutiger CLI-Name der Methode (muss mit dem Eintrag in der Registry übereinstimmen)
    name: str = ""

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def stylise(self, image_path: Path, max_side: int) -> "npt.NDArray[np.uint8]":
        """
        Lädt ``image_path`` als Graustufen-Array, skaliert auf ``max_side``
        (längste Seite) und ruft :meth:`apply` auf.

        Parameters
        ----------
        image_path : Pfad zur Eingabebilddatei
        max_side   : Maximale Länge der längsten Seite in Pixeln

        Returns
        -------
        binary : uint8-Array (H, W),  255 = Linie,  0 = Hintergrund
        """
        gray = self._load_gray(image_path, max_side)
        logger.debug(
            "[%s] Bild geladen: %s → %dx%d px",
            self.name, image_path, gray.shape[1], gray.shape[0],
        )
        return self.apply(gray)

    @abstractmethod
    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        """
        Wandelt ein Graustufen-Array in ein Binärbild um.

        Parameters
        ----------
        gray : uint8-Array (H, W) — vorgeladen und bereits skaliert

        Returns
        -------
        binary : uint8-Array (H, W),  255 = Linie,  0 = Hintergrund
        """

    # ------------------------------------------------------------------
    # Geschützte Hilfsmethoden (für Subklassen nutzbar)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_gray(path: Path, max_side: int) -> "npt.NDArray[np.uint8]":
        """Lädt ein Bild als Graustufen-Array und skaliert auf max. ``max_side`` px."""
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Bild konnte nicht geladen werden: {path}")
        h, w = img.shape
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug("Skaliert auf %dx%d px (Faktor %.2f)", new_w, new_h, scale)
        return img

    @staticmethod
    def _ensure_odd(k: int) -> int:
        """Stellt sicher, dass ``k`` ungerade ist (für Kernel-Größen)."""
        return k if k % 2 == 1 else k + 1
