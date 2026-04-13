"""
pipeline/steps/base/nn_stylizer_base.py - Common base class for NN-based stylizers

Bundles all functionality shared by all NN-based stylizers
(HED, DexiNed, …):

  - Automatic device detection (cuda > mps > cpu)
  - Lazy-loading protocol for model (_load_detector / _detector)
  - Grayscale → RGB-PIL conversion for model input
  - PIL output → binary uint8 array conversion

Subclasses must implement:
  - ``name``               - unique CLI name (str, class attribute)
  - ``_import_detector()`` - imports and instantiates the detector
  - ``_run_detector()``    - calls the detector and returns a PIL image
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from pipeline.steps.base.stylizer_base import BaseStylizer, resolve_device

if TYPE_CHECKING:
    import numpy.typing as npt
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)

_CONTROLNET_AUX_INSTALL_HINT = (
    "controlnet_aux is not installed. "
    "Install it with: pip install controlnet-aux torch torchvision pillow"
)


def _resolve_device(requested: str | None) -> str:
    """Backward-compatible alias - uses ``resolve_device`` from ``stylizer_base``."""
    return resolve_device(requested)


class NNBaseStylizer(BaseStylizer):
    """
    Abstract intermediate base class for NN-based stylizers.

    Subclasses must implement ``name``, ``_import_detector()`` and
    ``_run_detector()``.

    Parameters
    ----------
    model_path : Path to model directory or ``None`` for auto-download
                 from Hugging Face (``lllyasviel/Annotators``).
    device     : PyTorch device.  ``None`` or ``"auto"`` → automatic
                 detection (cuda > mps > cpu).
    threshold  : Binarization threshold (0–255) on grayscale output.
    """

    #: Standard Hugging Face repository for model downloads
    HF_REPO: str = "lllyasviel/Annotators"

    def __init__(
        self,
        model_path: Path | None = None,
        device: str | None = None,
        threshold: int = 128,
    ) -> None:
        self.model_path = model_path
        self.device: str = resolve_device(device)
        self.threshold = threshold
        self._detector: Any = None  # lazy-loaded in _load_detector()

    @abstractmethod
    def _import_detector(self) -> Any:
        """Imports and returns the instantiated detector (once only)."""

    @abstractmethod
    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        """Runs the detector on an RGB-PIL image."""

    @property
    def model_source(self) -> str:
        """Returns the model path or HF repo name."""
        return str(self.model_path) if self.model_path is not None else self.HF_REPO

    def _load_detector(self) -> None:
        """Loads the detector on first call (lazy loading)."""
        if self._detector is not None:
            return
        logger.debug(
            "[%s] Loading model: source=%s  device=%s …",
            self.name, self.model_source, self.device,
        )

        # Mediapipe patch only for detectors that use mediapipe_face.
        # Subclasses set _needs_mediapipe_patch = True to activate the patch.
        # Lazy import: mediapipe_compat is only loaded if the patch is actually
        # needed - not on every import of an NN step.
        if getattr(self, "_needs_mediapipe_patch", False):
            try:
                from pipeline.compat import mediapipe_compat  # lazy import
                import controlnet_aux.mediapipe_face.mediapipe_face_common as _cn_mpc  # type: ignore[import]
                _cn_mpc.generate_annotation = mediapipe_compat.generate_annotation
                logger.debug(
                    "Patched controlnet_aux.mediapipe_face.generate_annotation "
                    "-> mediapipe_compat.generate_annotation"
                )
            except Exception as _err:
                logger.debug("Failed to patch controlnet_aux mediapipe helper: %s", _err)

        self._detector = self._import_detector()
        logger.debug("[%s] Model loaded.", self.name)

    def _to_rgb_pil(self, gray: "npt.NDArray[np.uint8]") -> "PILImage.Image":
        """Converts a grayscale array into an RGB-PIL image."""
        from PIL import Image  # type: ignore[import]
        return Image.fromarray(cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB))

    def _to_binary(self, result_pil: "PILImage.Image") -> "npt.NDArray[np.uint8]":
        """Converts a PIL result image into a binary uint8 array."""
        result_gray = np.array(result_pil.convert("L"))
        _, binary = cv2.threshold(result_gray, self.threshold, 255, cv2.THRESH_BINARY)
        return binary.astype(np.uint8)

    def apply(self, gray: "npt.NDArray[np.uint8]") -> "npt.NDArray[np.uint8]":
        """Loads model (once), performs inference, binarizes the result."""
        self._load_detector()
        rgb_pil = self._to_rgb_pil(gray)
        result_pil = self._run_detector(rgb_pil)
        binary = self._to_binary(result_pil)
        logger.debug("[%s] Output %dx%d", self.name, binary.shape[1], binary.shape[0])
        return binary
