"""
pipeline/steps/stylise_lineart_step.py - Lineart edge detection as PipelineStep

Data transport via ImageContext
--------------------------------
Reads   ctx.metadata["source_path"]  - Path to input image file
Writes  ctx.intermediates["binary"]  - uint8 array (H, W), 255=line
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.steps.base.nn_stylizer_base import NNBaseStylizer, _CONTROLNET_AUX_INSTALL_HINT

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class _LineartStylizer(NNBaseStylizer):
    """ControlNet-v1.1-Lineart-Preprocessor (lllyasviel/control_v11p_sd15_lineart)."""

    name = "lineart"
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


class StyliseLineartStep(PipelineStep):
    """
    Stylization step with ControlNet-v1.1-Lineart-Preprocessor.

    Requires: pip install controlnet-aux torch torchvision pillow

    config-key                Default  Corresponds to CLI flag
    --------------------------------------------------------
    style_res                 1024     --style-res
    model_path                None     --model-path
    device                    "auto"   --device
    lineart_coarse            False    --lineart-coarse
    lineart_detect_res        512      --lineart-detect-res
    lineart_image_res         512      --lineart-image-res
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._stylizer: Optional[_LineartStylizer] = None

    def _get_stylizer(self) -> _LineartStylizer:
        """Creates the stylizer on first call (lazy initialization)."""
        if self._stylizer is None:
            c = self.config
            model_path_raw = c.get("model_path")
            self._stylizer = _LineartStylizer(
                model_path=Path(model_path_raw) if model_path_raw is not None else None,
                device=str(c.get("device", "auto")),
                coarse=bool(c.get("lineart_coarse", False)),
                detect_resolution=int(c.get("lineart_detect_res", 512)),
                image_resolution=int(c.get("lineart_image_res", 512)),
            )
        return self._stylizer

    def process(self, ctx: ImageContext) -> ImageContext:
        max_side: int = int(self.config.get("style_res", 1024))
        binary = self._get_stylizer().stylise(ctx.metadata["source_path"], max_side)
        logger.debug("StyliseLineartStep: Binary image %dx%d px", binary.shape[1], binary.shape[0])
        ctx.intermediates["binary"] = binary
        return ctx
