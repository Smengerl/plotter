"""
pipeline/steps/stylise_controlnet_step.py — Style transfer using ControlNet + Stable Diffusion 1.5

Uses the Hugging Face `diffusers` library to apply style transfer to images
via ControlNet conditioning + Stable Diffusion 1.5 text-to-image pipeline.

Key features:
- Configurable prompt for style control
- Multiple ControlNet types (canny, lineart, softedge, etc.)
- Optional model CPU offloading (reduce VRAM usage)
- Automatic device detection (cuda > mps > cpu)

Requires:
    pip install diffusers transformers safetensors torch accelerate

Data transport via ImageContext
--------------------------------
Reads   ctx.image                              - PIL RGB image set by LoadImageStep
Writes  ctx.intermediates["binary"]            - uint8 array (H, W), 255=line
        ctx.intermediates["stylized_diffusion"] - PIL RGB result before binarization
        ctx.intermediates["controlnet_condition"] - PIL conditioning image
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pipeline.steps.base.diffusion_stylizer_base import (
    DiffusionStylizerStep,
    _DIFFUSERS_INSTALL_HINT,
)
from pipeline.steps.base.nn_stylizer_base import _CONTROLNET_AUX_INSTALL_HINT

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


def _check_dependencies() -> tuple[bool, str]:
    """Check whether diffusers and torch are importable.

    Returns:
        Tuple of (ok: bool, error_message: str).
        If ok is True, error_message is an empty string.
    """
    import importlib.util
    missing = [
        pkg for pkg in ("diffusers", "torch")
        if importlib.util.find_spec(pkg) is None
    ]
    if missing:
        return False, f"{', '.join(missing)} not found"
    return True, ""


# Map from controlnet_type config value to HuggingFace model repo
_CONTROLNET_REPO_MAP: dict[str, str] = {
    "canny":    "lllyasviel/control_v11p_sd15_canny",
    "lineart":  "lllyasviel/control_v11p_sd15_lineart",
    "softedge": "lllyasviel/control_v11p_sd15_softedge",
    "scribble": "lllyasviel/control_v11p_sd15_scribble",
    "pose":     "lllyasviel/control_v11p_sd15_openpose",
    "depth":    "lllyasviel/control_v11f1p_sd15_depth",
    "normal":   "lllyasviel/control_v11p_sd15_normal",
    "seg":      "lllyasviel/control_v11p_sd15_seg",
}


class StyliseControlNetStep(DiffusionStylizerStep):
    """
    Style transfer using ControlNet + Stable Diffusion 1.5.

    Applies artistic style to an image via text-prompt guided diffusion
    with ControlNet conditioning. Inherits HF token loading, lazy model
    initialization, and binarization from ``DiffusionStylizerStep``.

    Config keys                 Default                                          Meaning
    -----------------------------------------------------------------------
    prompt                      "oil painting, masterpiece, detailed"             Style guidance
    negative_prompt             "blurry, distorted, low quality"                  What to avoid
    controlnet_type             "lineart"                                         ControlNet variant (used for repo lookup)
    controlnet_model            "lllyasviel/control_v11p_sd15_lineart"            HF ControlNet repo (overrides controlnet_type lookup)
    base_model                  "runwayml/stable-diffusion-v1-5"                  HF base SD model ID
    num_inference_steps         20                                                Quality vs speed
    guidance_scale              7.5                                               Prompt adherence
    hf_token_path               None                                              Path to HF token
    enable_model_cpu_offload    False                                             Reduce VRAM
    device                      "auto"                                            cuda / mps / cpu
    binary_threshold            128                                               Binarization thr.
    """

    name = "ControlNet style transfer"

    _DEFAULT_BASE_MODEL = "runwayml/stable-diffusion-v1-5"
    _DEFAULT_CONTROLNET_MODEL = "lllyasviel/control_v11p_sd15_lineart"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        c = self.config
        self.prompt: str = c.get("prompt", "oil painting, masterpiece, detailed")
        self.negative_prompt: str = c.get("negative_prompt", "blurry, distorted, low quality")
        self.controlnet_type: str = c.get("controlnet_type", "lineart")
        self.num_inference_steps: int = int(c.get("num_inference_steps", 20))
        self.guidance_scale: float = float(c.get("guidance_scale", 7.5))
        self.base_model: str = c.get("base_model", self._DEFAULT_BASE_MODEL)
        self.controlnet_model: str = c.get(
            "controlnet_model",
            _CONTROLNET_REPO_MAP.get(self.controlnet_type, self._DEFAULT_CONTROLNET_MODEL),
        )

        # Backward-compat: expose as public attributes (tests read them)
        self.hf_token_path: str | None = self._hf_token_path
        self.enable_model_cpu_offload: bool = self._enable_cpu_offload

        self._pipe = None
        self._controlnet = None

    # ------------------------------------------------------------------
    # Backward-compatible helpers (referenced by existing tests)
    # ------------------------------------------------------------------

    def _resolve_device(self, device: str | None = None) -> str:
        """Resolve device string.

        Deprecated: use ``resolve_device()`` from ``stylizer_base`` directly.
        Kept for backward compatibility with existing tests.
        """
        from pipeline.steps.base.stylizer_base import resolve_device
        return resolve_device(device if device is not None else self.config.get("device", "auto"))

    # ------------------------------------------------------------------
    # DiffusionStylizerStep contract
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        """Lazy-load ControlNet model and SD 1.5 pipeline."""
        if self._pipe is not None:
            return

        ok, msg = _check_dependencies()
        if not ok:
            raise ImportError(f"{_DIFFUSERS_INSTALL_HINT}\n\n{msg}")

        try:
            from diffusers import ControlNetModel, StableDiffusionControlNetPipeline  # type: ignore[import]
            import torch  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(f"{_DIFFUSERS_INSTALL_HINT}\n\n{exc}") from exc

        logger.info(
            "Loading ControlNet (%s) + SD 1.5 on %s …",
            self.controlnet_model, self._device,
        )
        hf_token = self._load_hf_token()
        controlnet_repo = self.controlnet_model

        # float16 causes NaN outputs on MPS (Apple Silicon) → use float32 there
        torch_dtype = torch.float16 if self._device == "cuda" else torch.float32

        try:
            from inspect import signature

            extra_cn: dict = {}
            if hf_token is not None:
                fp = signature(ControlNetModel.from_pretrained)
                if "use_auth_token" in fp.parameters:
                    extra_cn["use_auth_token"] = hf_token
                elif "token" in fp.parameters:
                    extra_cn["token"] = hf_token

            self._controlnet = ControlNetModel.from_pretrained(
                controlnet_repo,
                torch_dtype=torch_dtype,
                **extra_cn,
            )
        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "not found" in error_msg:
                raise RuntimeError(
                    f"❌ ControlNet model not found: {controlnet_repo}\n"
                    "If gated, add hf_token_path to config."
                ) from exc
            raise

        try:
            from inspect import signature

            extra_pipe: dict = {}
            if hf_token is not None:
                fp_pipe = signature(StableDiffusionControlNetPipeline.from_pretrained)
                if "use_auth_token" in fp_pipe.parameters:
                    extra_pipe["use_auth_token"] = hf_token
                elif "token" in fp_pipe.parameters:
                    extra_pipe["token"] = hf_token

            self._pipe = StableDiffusionControlNetPipeline.from_pretrained(
                self.base_model,
                controlnet=self._controlnet,
                torch_dtype=torch_dtype,
                safety_checker=None,
                requires_safety_checker=False,
                **extra_pipe,
            )
        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "not found" in error_msg:
                raise RuntimeError(
                    f"❌ Base model not found: {self.base_model}\n"
                    "If gated, add hf_token_path to config."
                ) from exc
            raise

        self._pipe = self._pipe.to(self._device)

        if self._enable_cpu_offload:
            self._pipe.enable_model_cpu_offload()
            logger.info("Model CPU offloading enabled (reduces VRAM)")
        else:
            try:
                self._pipe.enable_attention_slicing()
            except Exception:
                pass

        logger.info("ControlNet pipeline loaded (device: %s)", self._device)

    def _prepare_control_image(self, image: "PILImage.Image") -> "PILImage.Image":
        """Prepare the ControlNet conditioning image from the input.

        Uses the appropriate ``controlnet_aux`` detector for the selected
        ``controlnet_type`` so the conditioning image matches what the
        ControlNet model was trained on.

        Args:
            image: Input PIL RGB image.

        Returns:
            Conditioning PIL image appropriate for the selected controlnet_type.
        """
        if self.controlnet_type == "lineart":
            try:
                from controlnet_aux import LineartDetector  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
            detector = LineartDetector.from_pretrained("lllyasviel/Annotators")
            detector.to(self._device)
            return detector(image, detect_resolution=512, image_resolution=image.width)

        if self.controlnet_type == "softedge":
            try:
                from controlnet_aux import HEDdetector  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
            detector = HEDdetector.from_pretrained("lllyasviel/Annotators")
            detector.to(self._device)
            return detector(image, detect_resolution=512, image_resolution=image.width)

        if self.controlnet_type == "canny":
            try:
                from controlnet_aux import CannyDetector  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
            detector = CannyDetector()
            return detector(image, low_threshold=100, high_threshold=200)

        if self.controlnet_type == "scribble":
            try:
                from controlnet_aux import HEDdetector  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(_CONTROLNET_AUX_INSTALL_HINT) from exc
            detector = HEDdetector.from_pretrained("lllyasviel/Annotators")
            detector.to(self._device)
            return detector(image, scribble=True, detect_resolution=512, image_resolution=image.width)

        # pose, depth, normal, seg — pass through as-is (require separate specialist detectors)
        logger.warning(
            "No dedicated detector implemented for controlnet_type=%r — "
            "passing input image as-is. Results may be poor.",
            self.controlnet_type,
        )
        return image.convert("RGB")

    def _run_diffusion(self, image: "PILImage.Image") -> "PILImage.Image":
        """Run ControlNet + SD 1.5 on the given PIL RGB image."""
        control_image = self._prepare_control_image(image)
        control_image = control_image.resize((image.width, image.height))

        # Store conditioning image for debugging
        # (written into ctx via StylizerStep.process → _stylise → here;
        #  we smuggle it out via a side channel since _stylise only returns binary)
        self._last_control_image = control_image

        logger.info(
            "Applying ControlNet (%s) — prompt: %s", self.controlnet_type, self.prompt
        )

        output = self._pipe(
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            image=control_image,
            num_inference_steps=self.num_inference_steps,
            guidance_scale=self.guidance_scale,
            height=image.height,
            width=image.width,
        )
        stylized: PILImage.Image = output.images[0]
        logger.info(
            "Style transfer complete: %d×%d px", stylized.width, stylized.height
        )
        return stylized

    def _stylise(self, ctx: "object") -> "npt.NDArray[np.uint8]":  # type: ignore[override]
        """Override to also store the controlnet conditioning image."""
        from pipeline.core.base import ImageContext
        assert isinstance(ctx, ImageContext)

        self._last_control_image = None
        binary = super()._stylise(ctx)

        # Store conditioning image produced during _run_diffusion
        if self._last_control_image is not None:
            ctx.intermediates["controlnet_condition"] = self._last_control_image
        return binary


