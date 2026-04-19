"""
pipeline/steps/stylise_img2img_step.py — Image-to-Image style transfer

Uses Stable Diffusion v1.5 (community mirror) for img2img style transfer
without ControlNet conditioning. Faster than ControlNet, lower VRAM requirements.

Key features:
- SD v1.5 model (stable-diffusion-v1-5/stable-diffusion-v1-5)
- Configurable prompt for style control
- Adjustable strength parameter (0.0–1.0) for modification intensity
- Optional model CPU offloading (reduce VRAM usage)
- Automatic device detection (cuda > mps > cpu)

Requires:
    pip install diffusers transformers safetensors torch accelerate

Data transport via ImageContext
--------------------------------
Reads   ctx.image                              - PIL RGB image set by LoadImageStep
Writes  ctx.intermediates["binary"]            - uint8 array (H, W), 255=line
        ctx.intermediates["stylized_diffusion"] - PIL RGB result before binarization
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pipeline.steps.base.diffusion_stylizer_base import (
    DiffusionStylizerStep,
    _DIFFUSERS_INSTALL_HINT,
)

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


class StyliseImg2ImgStep(DiffusionStylizerStep):
    """
    Image-to-Image style transfer using Stable Diffusion v1.5.

    Applies artistic style via text-prompt guided img2img diffusion.
    Inherits HF token loading, lazy model initialization, and binarization
    from ``DiffusionStylizerStep``.

    Config keys        Default                                   Meaning
    -----------------------------------------------------------------------
    prompt             "artistic style, beautiful"               Style guidance
    negative_prompt    "blurry, low quality, distorted"          What to avoid
    strength           0.7                                       0.0–1.0 modification
    num_inference_steps 20                                       Quality vs speed
    guidance_scale     7.5                                       Prompt adherence
    model_id           "stable-diffusion-v1-5/stable-diffusion-v1-5"  HF model ID
    hf_token_path      None                                      Path to HF token file
    enable_model_cpu_offload  False                              Reduce VRAM
    device             "auto"                                    cuda / mps / cpu
    binary_threshold   128                                       Binarization threshold
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        c = self.config
        self.prompt: str = c.get("prompt", "artistic style, beautiful")
        self.negative_prompt: str = c.get(
            "negative_prompt", "blurry, low quality, distorted"
        )
        self.strength: float = max(0.0, min(1.0, float(c.get("strength", 0.7))))
        self.num_inference_steps: int = int(c.get("num_inference_steps", 20))
        self.guidance_scale: float = float(c.get("guidance_scale", 7.5))
        self.model_id: str = c.get("model_id", "stable-diffusion-v1-5/stable-diffusion-v1-5")

        # Backward-compat: expose hf_token_path as public attribute (tests read it)
        self.hf_token_path: str | None = self._hf_token_path
        self.enable_model_cpu_offload: bool = self._enable_cpu_offload

        self._pipe = None

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
        """Lazy-load the SD 2.1 img2img pipeline."""
        if self._pipe is not None:
            return

        ok, msg = _check_dependencies()
        if not ok:
            raise ImportError(f"{_DIFFUSERS_INSTALL_HINT}\n\n{msg}")

        try:
            from diffusers import StableDiffusionImg2ImgPipeline  # type: ignore[import]
            import torch  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(f"{_DIFFUSERS_INSTALL_HINT}\n\nMissing dependency: {exc}") from exc

        logger.debug("[img2img] Loading model: %s on device: %s", self.model_id, self._device)
        hf_token = self._load_hf_token()

        try:
            # Pass hf token only when the class method accepts it to avoid
            # warnings with newer diffusers versions.
            from inspect import signature

            from_pretrained = StableDiffusionImg2ImgPipeline.from_pretrained
            fp_sig = signature(from_pretrained)
            extra: dict = {}
            if hf_token is not None:
                if "use_auth_token" in fp_sig.parameters:
                    extra["use_auth_token"] = hf_token
                elif "token" in fp_sig.parameters:
                    extra["token"] = hf_token

            self._pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                **extra,
            )
            self._pipe = self._pipe.to(self._device)
        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "not found" in error_msg:
                raise RuntimeError(
                    f"❌ Model not found: {self.model_id}\n\n"
                    f"Check the model ID: https://huggingface.co/{self.model_id}\n"
                    f"If gated, add hf_token_path to config."
                ) from exc
            if "401" in error_msg or "unauthorized" in error_msg or "token" in error_msg:
                raise RuntimeError(
                    f"❌ Authentication failed for model: {self.model_id}\n\n"
                    f"Provide a valid HF token via hf_token_path in config."
                ) from exc
            raise RuntimeError(
                f"❌ Failed to load model: {self.model_id}\n\nError: {exc}"
            ) from exc

        if self._enable_cpu_offload:
            logger.debug("[img2img] Enabling model CPU offload")
            self._pipe.enable_attention_slicing()
            try:
                self._pipe.enable_model_cpu_offload()
            except AttributeError:
                logger.warning("[img2img] Model CPU offload not supported by this version")

    def _run_diffusion(self, image: "PILImage.Image") -> "PILImage.Image":
        """Run SD 2.1 img2img on the given PIL RGB image."""
        from PIL import Image

        # Resize to a manageable dimension
        max_dim = min(768, max(image.width, image.height))
        if max(image.width, image.height) > max_dim:
            ratio = max_dim / max(image.width, image.height)
            image = image.resize(
                (int(image.width * ratio), int(image.height * ratio)),
                Image.Resampling.LANCZOS,
            )

        logger.debug(
            "[img2img] Input %dx%d px, strength=%.2f", image.width, image.height, self.strength
        )

        result = self._pipe(
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            image=image,
            strength=self.strength,
            num_inference_steps=self.num_inference_steps,
            guidance_scale=self.guidance_scale,
        )
        stylized: PILImage.Image = result.images[0]
        logger.debug("[img2img] Output: %dx%d px", stylized.width, stylized.height)
        return stylized


