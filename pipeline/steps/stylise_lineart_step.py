"""
pipeline/steps/stylise_lineart_step.py - Lineart edge detection as PipelineStep

Data transport via ImageContext
--------------------------------
Reads   ctx.image                    - PIL RGB image set by LoadImageStep
Writes  ctx.intermediates["binary"]  - uint8 array (H, W), 255=line
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pipeline.steps.base.nn_stylizer_base import NNStylizerStep, _CONTROLNET_AUX_INSTALL_HINT

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class StyliseLineartStep(NNStylizerStep):
    """
    Stylization step with ControlNet-v1.1-Lineart-Preprocessor.

    Requires ``LoadImageStep`` to run first so that ``ctx.image`` is set.

    Requires: pip install controlnet-aux torch torchvision pillow

    config-key                Default  Corresponds to CLI flag
    --------------------------------------------------------
    style_res                 1024     --style-res  (handled by LoadImageStep)
    model_path                None     --model-path
    device                    "auto"   --device
    threshold                 128      binarization threshold (0–255)
    lineart_coarse            False    --lineart-coarse
    lineart_detect_res        512      --lineart-detect-res
    lineart_image_res         512      --lineart-image-res
    """

    name = "lineart"
    HF_REPO: str = "lllyasviel/Annotators"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        c = self.config
        self._coarse: bool = bool(c.get("lineart_coarse", False))
        self._detect_resolution: int = int(c.get("lineart_detect_res", 512))
        self._image_resolution: int = int(c.get("lineart_image_res", 512))

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import LineartDetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        det = LineartDetector.from_pretrained(self.model_source)
        det.to(self._device)
        return det

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(  # type: ignore[misc]
            rgb_pil,
            coarse=self._coarse,
            detect_resolution=self._detect_resolution,
            image_resolution=self._image_resolution,
        )
