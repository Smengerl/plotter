"""
pipeline/steps/base/nn_stylizer_base.py - Base class for NN-based stylization steps

Provides ``NNStylizerStep``: a concrete PipelineStep base class that combines
the pipeline plumbing (requires / process / binary output) with the full NN
inference protocol:

  - Automatic device detection (cuda > mps > cpu)
  - Lazy model loading on first ``process()`` call
  - Grayscale ndarray → RGB-PIL conversion for model input via ``ctx.gray_to_rgb_pil``
  - PIL output → binary conversion via ``ctx.pil_to_binary``
  - Writing results into context via ``ctx.set_stylize_result``

Subclasses must implement:
  - ``name``               - unique registry name (str, class attribute)
  - ``_import_detector()`` - imports and instantiates the detector object
  - ``_run_detector()``    - calls the detector with an RGB-PIL, returns a PIL image
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pipeline.core.base import ImageContext
from pipeline.steps.base.stylizer_base import StylizerStep, resolve_device

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


# ---------------------------------------------------------------------------
# NNStylizerStep — PipelineStep base for NN-based stylizers
# ---------------------------------------------------------------------------

class NNStylizerStep(StylizerStep):
    """
    Abstract PipelineStep base class for NN-based stylization steps.

    Combines the ``StylizerStep`` contract (reads ``ctx.image``, writes
    ``intermediates["binary"]``) with the full NN inference protocol:
    lazy model loading, device management, and PIL <-> ndarray conversion.

    Subclasses must implement:

    * ``name``               - unique registry name (class attribute, str)
    * ``_import_detector()`` - import and instantiate the detector; called once.
    * ``_run_detector()``    - run inference on an RGB PIL image; return PIL image.

    Config keys shared by all NN stylizers:

    ============  =======  =========================================
    Key           Default  Meaning
    ============  =======  =========================================
    model_path    None     Local model directory / file.
                           ``None`` -> auto-download from HuggingFace.
    device        "auto"   PyTorch device: auto / cuda / mps / cpu.
    threshold     128      Binarization threshold (0-255).
    ============  =======  =========================================
    """

    #: Standard Hugging Face repository for model downloads
    HF_REPO: str = "lllyasviel/Annotators"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        c = self.config
        model_path_raw = c.get("model_path")
        self._model_path: Path | None = (
            Path(model_path_raw) if model_path_raw is not None else None
        )
        self._device: str = resolve_device(c.get("device", "auto"))
        self._threshold: int = int(c.get("threshold", 128))
        self._detector: Any = None  # lazy-loaded on first _stylise() call

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _import_detector(self) -> Any:
        """Import and return the instantiated detector.

        Called exactly once (lazy, on first inference).  The return value
        is stored in ``self._detector`` and reused for all subsequent calls.
        """

    @abstractmethod
    def _run_detector(self, rgb_pil: "PILImage.Image") -> "PILImage.Image":
        """Run the detector on an RGB PIL image and return a PIL result."""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model_source(self) -> str:
        """Return the local model path or the HuggingFace repo name."""
        return str(self._model_path) if self._model_path is not None else self.HF_REPO

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _load_detector(self) -> None:
        """Load the detector on first call (lazy initialization)."""
        if self._detector is not None:
            return
        logger.debug(
            "[%s] Loading model: source=%s  device=%s ...",
            type(self).__name__, self.model_source, self._device,
        )

        # Mediapipe compatibility patch - activated per-subclass via class attribute.
        if getattr(self, "_needs_mediapipe_patch", False):
            try:
                from pipeline.compat import mediapipe_compat  # lazy import
                import controlnet_aux.mediapipe_face.mediapipe_face_common as _cn_mpc  # type: ignore[import]
                _cn_mpc.generate_annotation = mediapipe_compat.generate_annotation
                logger.debug("Patched controlnet_aux mediapipe helper.")
            except Exception as _err:
                logger.debug("Failed to patch controlnet_aux mediapipe helper: %s", _err)

        self._detector = self._import_detector()
        logger.debug("[%s] Model loaded.", type(self).__name__)

    # ------------------------------------------------------------------
    # StylizerStep contract
    # ------------------------------------------------------------------

    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        """Run NN inference and return the binary result.

        Loads the detector lazily on first call, then uses
        ``ctx.gray_as_rgb_pil`` to obtain the model input and
        thresholds the output to produce a binary ndarray.

        Subclasses with a different inference signature (e.g. extra detector
        arguments) should override ``_run_detector()`` rather than this method.
        """
        self._load_detector()
        result_pil = self._run_detector(ctx.image_as_grayscale_pil)
        binary = self._pil_to_binary(result_pil, self._threshold)
        return binary
