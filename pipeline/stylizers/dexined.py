"""
pipeline/stylizers/dexined.py — DexiNed / Lineart Edge Detection

Dense Extreme Inception Network for Edge Detection. Liefert sehr
saubere, dünne Linien und eignet sich besonders für Strichzeichnungen
aus Fotos.

Referenz: Poma et al. 2020,
          "Dense Extreme Inception Network for Edge Detection"
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


class DexiNedStylizer(NNBaseStylizer):
    """
    DexiNed / Lineart-Kantenerkennung.

    Parameters
    ----------
    model_path : Pfad zum Modell-Verzeichnis oder ``None`` für Auto-Download
    device     : PyTorch-Gerät. ``None`` / ``"auto"`` → cuda > mps > cpu
    threshold  : Binarisierungsschwelle (0–255) auf dem Modell-Output
    coarse     : ``True`` = grobe Linien, ``False`` = feine/anime Linien
    """

    name = "dexined"

    def __init__(
        self,
        model_path: Path | None = None,
        device: str | None = None,
        threshold: int = 128,
        coarse: bool = True,
    ) -> None:
        super().__init__(model_path=model_path, device=device, threshold=threshold)
        self.coarse = coarse

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import LineartDetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        return LineartDetector.from_pretrained(self.model_source)

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(rgb_pil, coarse=self.coarse)  # type: ignore[misc]
