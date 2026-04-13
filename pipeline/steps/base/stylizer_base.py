"""
pipeline/steps/base/stylizer_base.py - Helper functions and base class for NN stylizers

Contains:
  - ``load_gray()``      - Load and scale image (module function)
  - ``ensure_odd()``     - Normalize kernel size to odd (module function)
  - ``resolve_device()`` - Determine best available PyTorch device (module function)
  - ``BaseStylizer``     - ABC for NN-based stylizers with lazy loading
"""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


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


class BaseStylizer(ABC):
    """
    Abstract base class for NN-based stylizers.

    Subclasses must implement ``name`` and ``apply()``.  The method receives
    a preloaded grayscale array and returns a binary image (uint8, 0/255)
    where 255 represents a line and 0 represents the background.

    The object is created once in the associated PipelineStep and reused
    across multiple ``process()`` calls (lazy loading).
    """

    #: Unique name of the method (required field - subclasses must override)
    name: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Check only on concrete (non-abstract) classes.
        # inspect.isabstract() checks via ABCMeta whether abstractmethods are still open -
        # more robust than manually checking method names.
        if "name" not in cls.__dict__ and not inspect.isabstract(cls):
            raise TypeError(f"{cls.__name__} must define the class attribute 'name'")

    def stylise(self, image_path: Path | str, max_side: int) -> "npt.NDArray[np.uint8]":
        """
        Loads ``image_path`` as grayscale array, scales to ``max_side``
        (longest side), and calls :meth:`apply`.
        """
        gray = load_gray(image_path, max_side)
        logger.debug(
            "[%s] Image loaded: %s → %dx%d px",
            self.name, image_path, gray.shape[1], gray.shape[0],
        )
        return self.apply(gray)

    @abstractmethod
    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        """Converts a grayscale array into a binary image."""
