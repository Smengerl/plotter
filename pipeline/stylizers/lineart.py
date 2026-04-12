"""
pipeline/stylizers/lineart.py — Lineart-Kantenerkennung (ControlNet v1.1)

Verwendet den ``LineartDetector`` aus ``controlnet_aux``, wie er für das
ControlNet-Lineart-Modell entwickelt und eingesetzt wird:

    lllyasviel/control_v11p_sd15_lineart  (ControlNet-Conditioning-Modell)
    lllyasviel/Annotators                  (Preprocessor-Gewichte, sk_model.pth)

Der Detektor erzeugt sehr saubere, dünne Linien auf weißem Grund.
Im Gegensatz zu ``DexiNedStylizer`` (gleicher Detektor, andere Defaults)
bietet dieser Stylizer zusätzliche Steuerung der internen Auflösung
(``detect_resolution``, ``image_resolution``).

Zwei Modi:
  coarse=False (Standard) — feine, präzise Linien  (sk_model.pth)
  coarse=True             — grobe, dickere Linien   (sk_model2.pth)

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


class LineartStylizer(NNBaseStylizer):
    """
    ControlNet-v1.1-Lineart-Preprocessor.

    Erzeugt präzise Strichzeichnungen im Stil des ControlNet-Lineart-
    Preprocessors (``lllyasviel/control_v11p_sd15_lineart``).

    Parameters
    ----------
    model_path       : Pfad zum Modell-Verzeichnis (``sk_model.pth`` +
                       ``sk_model2.pth`` müssen darin liegen) oder ``None``
                       für Auto-Download von ``lllyasviel/Annotators``.
    device           : PyTorch-Gerät. ``None`` / ``"auto"`` → cuda > mps > cpu
    threshold        : Binarisierungsschwelle (0–255). Standard: 128.
    coarse           : ``False`` (Standard) = feine Linien (sk_model.pth),
                       ``True`` = grobe Linien (sk_model2.pth).
    detect_resolution: Interne Auflösung für die Modell-Inferenz in Pixeln.
                       Höhere Werte → mehr Details, aber langsamer.
                       Standard: 512.
    image_resolution : Ausgabeauflösung des Detektors vor Binarisierung.
                       Wird danach noch auf die Originalgröße skaliert.
                       Standard: 512.
    """

    name = "lineart"

    #: Modell-Gewichte liegen im Annotators-Repo, nicht im ControlNet-Repo
    HF_REPO: str = "lllyasviel/Annotators"

    def __init__(
        self,
        model_path: Path | None = None,
        device: str | None = None,
        threshold: int = 128,
        coarse: bool = False,
        detect_resolution: int = 512,
        image_resolution: int = 512,
    ) -> None:
        super().__init__(model_path=model_path, device=device, threshold=threshold)
        self.coarse = coarse
        self.detect_resolution = detect_resolution
        self.image_resolution = image_resolution

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import LineartDetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        det = LineartDetector.from_pretrained(self.model_source)
        det.to(self.device)
        return det

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(  # type: ignore[misc]
            rgb_pil,
            coarse=self.coarse,
            detect_resolution=self.detect_resolution,
            image_resolution=self.image_resolution,
        )
