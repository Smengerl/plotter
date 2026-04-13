"""
pipeline/steps/stylise_dexined_step.py - DexiNed edge detection as PipelineStep

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


class _DexiNedStylizer(NNBaseStylizer):
    """DexiNed via controlnet_aux LineartDetector (coarse=True)."""

    name = "dexined"

    def _import_detector(self) -> Any:
        try:
            from controlnet_aux import LineartDetector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
        return LineartDetector.from_pretrained(self.model_source)

    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        return self._detector(rgb_pil, coarse=True)  # type: ignore[misc]


class StyliseDexiNedStep(PipelineStep):
    """
    Stylization step with DexiNed / Lineart edge detection (coarse).

    Requires: pip install controlnet-aux torch torchvision pillow

    config-key        Default  Corresponds to CLI flag
    --------------------------------------------------
    style_res         1024     --style-res
    model_path        None     --model-path
    device            "auto"   --device
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._stylizer: Optional[_DexiNedStylizer] = None

    def _get_stylizer(self) -> _DexiNedStylizer:
        """Creates the stylizer on first call (lazy initialization)."""
        if self._stylizer is None:
            c = self.config
            model_path_raw = c.get("model_path")
            self._stylizer = _DexiNedStylizer(
                model_path=Path(model_path_raw) if model_path_raw is not None else None,
                device=str(c.get("device", "auto")),
            )
        return self._stylizer

    def process(self, ctx: ImageContext) -> ImageContext:
        max_side: int = int(self.config.get("style_res", 1024))
        binary = self._get_stylizer().stylise(ctx.metadata["source_path"], max_side)
        logger.debug("StyliseDexiNedStep: Binary image %dx%d px", binary.shape[1], binary.shape[0])
        ctx.intermediates["binary"] = binary
        return ctx
