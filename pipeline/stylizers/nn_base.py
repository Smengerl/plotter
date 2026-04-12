"""
pipeline/stylizers/nn_base.py — Gemeinsame Basisklasse für neuronale Netz-Stilisierer

Bündelt alle Funktionalitäten, die von allen NN-basierten Stilisierern
(HED, DexiNed, …) geteilt werden:

  - Automatische Device-Erkennung (cuda > mps > cpu)
  - Lazy-Loading-Protokoll für das Modell (_load_detector / _detector)
  - Graustufen → RGB-PIL Konvertierung für Modell-Input
  - PIL-Output → binäres uint8-Array Konvertierung
  - Import-Fehler mit verständlicher Fehlermeldung

Subklassen müssen implementieren:
  - ``name``              — eindeutiger CLI-Name (str, Klassenattribut)
  - ``_import_detector()`` — importiert und instanziiert den Detektor
  - ``_run_detector()``   — ruft den Detektor auf und gibt ein PIL-Image zurück
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from pipeline.stylizers.base import BaseStylizer
from pipeline.compat import mediapipe_compat

if TYPE_CHECKING:
    import numpy.typing as npt
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)

_CONTROLNET_AUX_INSTALL_HINT = (
    "controlnet_aux ist nicht installiert. "
    "Installiere es mit: pip install controlnet-aux torch torchvision pillow"
)


def _resolve_device(requested: str | None) -> str:
    """
    Gibt das beste verfügbare PyTorch-Gerät zurück.

    Priorität: cuda > mps > cpu

    Wenn ``requested`` explizit angegeben wurde (nicht ``None`` und nicht
    ``"auto"``), wird es direkt zurückgegeben — ohne Verfügbarkeitsprüfung,
    damit der Nutzer ein Gerät erzwingen kann.

    Parameters
    ----------
    requested : Vom Nutzer gewünschtes Gerät (``"cpu"``, ``"cuda"``, ``"mps"``,
                ``"auto"`` oder ``None`` für automatische Erkennung)

    Returns
    -------
    device : Geräte-String, direkt an PyTorch oder controlnet_aux übergeben
    """
    if requested is not None and requested not in ("auto", ""):
        return requested

    try:
        import torch  # type: ignore[import]

        if torch.cuda.is_available():
            logger.debug("Device-Erkennung: CUDA verfügbar → cuda")
            return "cuda"
        if torch.backends.mps.is_available():  # type: ignore[attr-defined]
            logger.debug("Device-Erkennung: MPS verfügbar → mps")
            return "mps"
    except ImportError:
        logger.debug("Device-Erkennung: torch nicht installiert → cpu")

    logger.debug("Device-Erkennung: Kein Accelerator gefunden → cpu")
    return "cpu"


class NNBaseStylizer(BaseStylizer):
    """
    Abstrakte Zwischenbasisklasse für NN-basierte Stilisierer.

    Subklassen müssen ``name``, ``_import_detector()`` und
    ``_run_detector()`` implementieren.  ``apply()`` ist fertig
    implementiert und ruft den Detector-Lifecycle ab.

    Parameters
    ----------
    model_path : Pfad zum Modell-Verzeichnis oder ``None`` für Auto-Download
                 von Hugging Face (``lllyasviel/Annotators``).
    device     : PyTorch-Gerät.  ``None`` oder ``"auto"`` → automatische
                 Erkennung (cuda > mps > cpu).
    threshold  : Binarisierungsschwelle (0–255) auf dem Graustufen-Output.
    """

    #: Standard Hugging Face Repository für Modell-Downloads
    HF_REPO: str = "lllyasviel/Annotators"

    def __init__(
        self,
        model_path: Path | None = None,
        device: str | None = None,
        threshold: int = 128,
    ) -> None:
        self.model_path = model_path
        self.device: str = _resolve_device(device)
        self.threshold = threshold
        self._detector: Any = None  # lazy-loaded in _load_detector()

    # ------------------------------------------------------------------
    # Abstrakte Methoden (von Subklassen zu implementieren)
    # ------------------------------------------------------------------

    @abstractmethod
    def _import_detector(self) -> Any:
        """
        Importiert und gibt den instanziierten Detektor zurück.

        Wird exakt einmal aufgerufen (Lazy Loading).  Soll einen
        ``ImportError`` mit ``_CONTROLNET_AUX_INSTALL_HINT`` auslösen,
        wenn ``controlnet_aux`` fehlt.

        Returns
        -------
        detector : Instanziiertes Detektor-Objekt (typ. aus controlnet_aux)
        """

    @abstractmethod
    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        """
        Führt den Detektor auf einem RGB-PIL-Bild aus und gibt das
        Ergebnis als PIL-Image zurück.

        Parameters
        ----------
        rgb_pil : RGB-PIL-Bild (bereits aus Graustufen konvertiert)

        Returns
        -------
        result : PIL-Image mit Kanteninformation (RGB oder L)
        """

    # ------------------------------------------------------------------
    # Gemeinsame Implementierung
    # ------------------------------------------------------------------

    @property
    def model_source(self) -> str:
        """Gibt den Modell-Pfad oder den HF-Repo-Namen zurück."""
        return str(self.model_path) if self.model_path is not None else self.HF_REPO

    def _load_detector(self) -> None:
        """Lädt den Detektor beim ersten Aufruf (Lazy Loading)."""
        if self._detector is not None:
            return
        logger.debug(
            "[%s] Modell laden: source=%s  device=%s …",
            self.name, self.model_source, self.device,
        )
        # If controlnet_aux provides a mediapipe helper module, patch its
        # generate_annotation implementation to use our compatibility adapter.
        # This avoids hard crashes when the installed mediapipe version
        # exposes a different API surface (mp.solutions vs mediapipe.tasks).
        try:
            # Local import to avoid requiring controlnet_aux at module import time
            import controlnet_aux.mediapipe_face.mediapipe_face_common as _cn_mpc  # type: ignore[import]
        except Exception:
            _cn_mpc = None

        if _cn_mpc is not None:
            try:
                _cn_mpc.generate_annotation = mediapipe_compat.generate_annotation
                logger.debug(
                    "Patched controlnet_aux.mediapipe_face.generate_annotation -> mediapipe_compat.generate_annotation"
                )
            except Exception as _err:
                logger.debug("Failed to patch controlnet_aux mediapipe helper: %s", _err)

        self._detector = self._import_detector()
        logger.debug("[%s] Modell geladen.", self.name)

    def _to_rgb_pil(self, gray: "npt.NDArray[np.uint8]") -> "PILImage.Image":
        """Konvertiert ein Graustufen-Array in ein RGB-PIL-Image."""
        from PIL import Image  # type: ignore[import]
        return Image.fromarray(cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB))

    def _to_binary(self, result_pil: "PILImage.Image") -> "npt.NDArray[np.uint8]":
        """Konvertiert ein PIL-Ergebnis-Image in ein binäres uint8-Array."""
        result_gray = np.array(result_pil.convert("L"))
        _, binary = cv2.threshold(result_gray, self.threshold, 255, cv2.THRESH_BINARY)
        return binary.astype(np.uint8)

    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        """Lädt Modell (einmalig), führt Inferenz durch, binarisiert das Ergebnis."""
        self._load_detector()
        rgb_pil = self._to_rgb_pil(gray)
        result_pil = self._run_detector(rgb_pil)
        binary = self._to_binary(result_pil)
        logger.debug("[%s] Ausgabe %dx%d", self.name, binary.shape[1], binary.shape[0])
        return binary
