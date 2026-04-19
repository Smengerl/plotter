from __future__ import annotations
"""
pipeline/steps/base/stylizer_base.py - Helper functions and base classes for stylizers

Contains:
    - ``load_gray()``        - Load and scale image from disk (module function)
    - ``ensure_odd()``       - Normalize kernel size to odd (module function)
    - ``resolve_device()``   - Determine best available PyTorch device (module function)
    - ``StylizerStep``       - Abstract base class for ALL stylization steps.
                                                         Enforces: requires() = ["image"], updates ctx.image,
                                                         and writes intermediates["binary"] for optional downstream use.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from pipeline.core.base import ImageContext
from pipeline.steps.base.pipeline_step import PipelineStep

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------

def load_gray(path: Path | str, max_side: int) -> "npt.NDArray[np.uint8]":
    """Loads an image as grayscale array and scales to max. ``max_side`` px."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image could not be loaded: {path}")
    h, w = img.shape
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.debug("Scaled to %dx%d px (factor %.2f)", new_w, new_h, scale)
    return img.astype(np.uint8)


def ensure_odd(k: int) -> int:
    """Ensures that ``k`` is odd (for kernel sizes)."""
    return k if k % 2 == 1 else k + 1


def resolve_device(requested: str | None) -> str:
    """
    Returns the best available PyTorch device.

    Priority: cuda > mps > cpu.  If ``requested`` is explicitly specified
    (not ``None`` and not ``"auto"``), it is returned directly.
    """
    if requested is not None and requested not in ("auto", ""):
        return requested

    try:
        import torch  # type: ignore[import]

        if torch.cuda.is_available():
            logger.debug("Device detection: CUDA available → cuda")
            return "cuda"
        if torch.backends.mps.is_available():  # type: ignore[attr-defined]
            logger.debug("Device detection: MPS available → mps")
            return "mps"
    except ImportError:
        logger.debug("Device detection: torch not installed → cpu")

    logger.debug("Device detection: No accelerator found → cpu")
    return "cpu"


# ---------------------------------------------------------------------------
# StylizerStep — abstract base for ALL stylization steps
# ---------------------------------------------------------------------------

class StylizerStep(PipelineStep):
    """
    Abstract base class for **all** stylization steps.

    Enforces the common contract shared by every stylizer in the pipeline:

    * ``requires()`` always returns ``["image"]`` — each stylizer needs
      ``ctx.image`` to be set by a preceding ``LoadImageStep`` (or another
      stylizer, since each stylizer updates ``ctx.image`` on output).
    * ``process()`` converts the binary result back to a grayscale PIL image
      and stores it in ``ctx.image``, so stylizers can be freely chained.
    * ``process()`` also writes the result to ``ctx.intermediates["binary"]``
      as a ``uint8`` ndarray (H, W) where 255 = line, 0 = background.
      ``VectorizeStep`` uses this if present, but falls back to ``ctx.image``
      directly, so a stylizer is not required between ``LoadImageStep`` and
      ``VectorizeStep``.

    Subclasses must implement :meth:`_stylise` which receives the
    ``ImageContext`` and returns the binary ndarray.  The base class
    wraps the call, stores the result, updates ``ctx.image`` and logs
    shape info.

    Example::

        class MyStep(StylizerStep):
            def _stylise(self, ctx: ImageContext) -> npt.NDArray[np.uint8]:
                gray = ctx.gray
                # ... custom processing ...
                return binary
    """

    def requires(self) -> list[str]:
        return ["image"]

    @abstractmethod
    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        """Perform the actual stylization and return the binary ndarray.

        Args:
            ctx: ImageContext with ``ctx.image`` set (PIL RGB or grayscale).
        Returns:
            binary: uint8 ndarray (H, W) where 255 = line, 0 = background.
        """

    def _pil_to_binary(self, pil: "PIL.Image.Image", threshold: int) -> "npt.NDArray[np.uint8]":
        """Helper to convert a PIL image to a binary uint8 ndarray.

        This is provided on the step base class for backward-compatibility
        with older implementations that called ``self._pil_to_binary(...)``
        from within ``_stylise()`` implementations.

        Args:
            pil: PIL image (any mode).
            threshold: Integer threshold in [0,255]; pixels > threshold -> 255.

        Returns:
            2-D uint8 ndarray where line = 255 and background = 0.
        """
        import cv2  # type: ignore[import]
        import numpy as _np

        gray = _np.array(pil.convert("L"))
        _, binary = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY)
        return binary.astype(_np.uint8)


    def process(self, ctx: ImageContext) -> ImageContext:
        binary = self._stylise(ctx)
        ctx.set_stylize_result(binary)
        logger.debug(
            "%s: binary %dx%d px → ctx.image updated",
            type(self).__name__,
            binary.shape[1],
            binary.shape[0],
        )
        return ctx


# Backward-compatible aliases for legacy code (must be after StylizerStep definition)
CVBaseStep = StylizerStep
CVStylizerStep = StylizerStep



