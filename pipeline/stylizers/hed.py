"""
pipeline/stylizers/hed.py — Holistically-nested Edge Detection

Neuronales Netz für Kantenerkennung. Liefert weichere, organischere
Linien als Canny und eignet sich gut für Fotos mit komplexen Texturen.

Referenz: Xie & Tu 2015, "Holistically-nested Edge Detection"
Checkpoint: https://huggingface.co/lllyasviel/Annotators (ControlNet)

Benötigt: pip install controlnet-aux torch torchvision pillow
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pipeline.stylizers.nn_base import NNBaseStylizer, _CONTROLNET_AUX_INSTALL_HINT

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class HEDStylizer(NNBaseStylizer):
    """
    HED-Kantenerkennung (Holistically-nested Edge Detection).

    Parameters
    ----------
    model_path : Pfad zum Modell-Verzeichnis oder ``None`` für Auto-Download
    device     : PyTorch-Gerät. ``None`` / ``"auto"`` → cuda > mps > cpu
    threshold  : Binarisierungsschwelle (0–255) auf dem Modell-Output
    """

    name = "hed"

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import HEDdetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        return HEDdetector.from_pretrained(self.model_source)

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(rgb_pil)  # type: ignore[misc]
