"""
pipeline/steps/base/diffusion_stylizer_base.py - Base class for Diffusion-based stylizers

Provides ``DiffusionStylizerStep``: a PipelineStep base class shared by
``StyliseControlNetStep`` and ``StyliseImg2ImgStep``.

Bundles all shared functionality:
  - HuggingFace token loading (``hf_token_path`` config key)
  - Lazy model loading protocol (``_load_models()`` called on first process())
  - PIL image → binary uint8 ndarray binarization
  - Automatic device detection (cuda > mps > cpu)

Subclasses must implement:
  - ``_load_models()``     - download / initialize the diffusion pipeline
  - ``_run_diffusion()``   - run inference; receives PIL RGB, returns PIL RGB

Config keys shared by all diffusion stylizers:

==========================  =======  =========================================
Key                         Default  Meaning
==========================  =======  =========================================
device                      "auto"   PyTorch device: auto / cuda / mps / cpu
hf_token_path               None     Path to a file containing a HF token.
                                     Required for gated models.
enable_model_cpu_offload    False    Enable CPU offloading to reduce VRAM.
binary_threshold            128      Grayscale threshold for binarization.
==========================  =======  =========================================
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from pipeline.core.base import ImageContext
from pipeline.steps.base.stylizer_base import StylizerStep, resolve_device

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)

_DIFFUSERS_INSTALL_HINT = """
Diffusion-based style transfer requires:
    pip install diffusers transformers safetensors torch accelerate

For GPU support (recommended):
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
"""


class DiffusionStylizerStep(StylizerStep):
    """
    Abstract PipelineStep base class for Diffusion-based stylization steps.

    Combines the ``StylizerStep`` contract (reads ``ctx.image``, writes
    ``intermediates["binary"]``) with shared Stable Diffusion plumbing:
    HF token loading, lazy model initialization, and binarization.

    Note: the raw stylized PIL image is not stored in ``ctx.intermediates``
    by default to avoid unnecessary memory retention during batch runs.

    Subclasses must implement:
        ``_load_models()``    — called once before first inference.
        ``_run_diffusion()``  — runs the model; receives PIL RGB, returns PIL RGB.
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        c = self.config
        self._device: str = resolve_device(c.get("device", "auto"))
        self._hf_token_path: str | None = c.get("hf_token_path", None)
        self._enable_cpu_offload: bool = bool(c.get("enable_model_cpu_offload", False))
        self._binary_threshold: int = int(c.get("binary_threshold", 128))
        self._hf_token: str | None = None  # cached after first load
        self._models_loaded: bool = False

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _load_models(self) -> None:
        """Download and initialize the diffusion pipeline.

        Called exactly once before the first ``process()`` call.
        Implementations should store their pipeline objects as instance
        attributes and must be idempotent (guard with ``if already loaded``).
        """

    @abstractmethod
    def _run_diffusion(self, image: "PILImage.Image") -> "PILImage.Image":
        """Run the diffusion pipeline on a PIL RGB image.

        Args:
            image: Input PIL RGB image.

        Returns:
            Stylized PIL RGB image.
        """

    # ------------------------------------------------------------------
    # HuggingFace token loading
    # ------------------------------------------------------------------

    def _load_hf_token(self) -> str | None:
        """Load the HuggingFace token from file (cached after first load).

        Returns:
            Token string, or None if not configured or file missing.
        """
        if self._hf_token is not None:
            return self._hf_token
        if self._hf_token_path is None:
            return None

        token_path = Path(self._hf_token_path)
        if not token_path.exists():
            logger.warning(
                "[%s] HF token file not found: %s. "
                "Model loading may fail for gated models.",
                type(self).__name__, self._hf_token_path,
            )
            return None

        try:
            self._hf_token = token_path.read_text().strip()
            logger.debug(
                "[%s] Loaded HF token from: %s", type(self).__name__, self._hf_token_path
            )
            return self._hf_token
        except Exception as exc:
            logger.warning(
                "[%s] Failed to read HF token file: %s", type(self).__name__, exc
            )
            return None

    # ------------------------------------------------------------------
    # StylizerStep contract
    # ------------------------------------------------------------------

    def _stylise(self, ctx: ImageContext) -> "npt.NDArray[np.uint8]":
        """Run diffusion pipeline and return the binary result.

        Also stores the raw stylized PIL image in
        ``ctx.intermediates["stylized_diffusion"]`` for downstream inspection.
        """
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

        rgb_pil = ctx.image.convert("RGB")
        stylized = self._run_diffusion(rgb_pil)
        # NOTE: do not persist the raw PIL stylized image in intermediates;
        # downstream steps operate on the binarized ndarray returned below.
        # Convert stylized PIL image to binary ndarray
        binary = self._pil_to_binary(stylized, self._binary_threshold)
        logger.debug(
            "[%s] Output %dx%d px (threshold=%d)",
            type(self).__name__,
            binary.shape[1],
            binary.shape[0],
            self._binary_threshold,
        )
        return binary
