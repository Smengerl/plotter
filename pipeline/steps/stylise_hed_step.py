"""
pipeline/steps/stylise_hed_step.py - HED edge detection as PipelineStep

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


class StyliseHEDStep(NNStylizerStep):
    """
    Stylization step using Holistically-nested Edge Detection (HED).

    Requires ``LoadImageStep`` to run first so that ``ctx.image`` is set.

    Requires: pip install controlnet-aux torch torchvision pillow

    config keys    Default  Corresponds to CLI flag
    -----------------------------------------------
    style_res      1024     --style-res  (handled by LoadImageStep)
    model_path     None     --model-path
    device         "auto"   --device
    threshold      128      binarization threshold (0–255)
    """

    name = "HED edge detection"

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import HEDdetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        return HEDdetector.from_pretrained(self.model_source)

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(rgb_pil)  # type: ignore[misc]

