"""
pipeline/steps/stylise_img2img_step.py — Image-to-Image style transfer

Uses Stable Diffusion 2.1 (small, lightweight model) for img2img style transfer
without ControlNet conditioning. Faster than ControlNet, lower VRAM requirements.

Key features:
- Lightweight SD 2.1 model (smaller than SD 1.5)
- Configurable prompt for style control
- Adjustable strength parameter (0.0–1.0) for modification intensity
- Optional model CPU offloading (reduce VRAM usage)
- Automatic device detection (cuda > mps > cpu)

Requires:
    pip install diffusers transformers safetensors torch accelerate

Example config:
    config:
      prompt: "watercolor painting, soft colors"
      negative_prompt: "blurry, low quality"
      strength: 0.7  # 0.0–1.0: how much to modify (higher = more change)
      num_inference_steps: 20
      guidance_scale: 7.5
      enable_model_cpu_offload: false
      device: auto
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from pipeline.core.base import ImageContext, PipelineStep

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import flags
_DIFFUSERS_AVAILABLE = False
_TORCH_AVAILABLE = False


def _check_dependencies() -> tuple[bool, str]:
    """Check if required libraries are available."""
    try:
        import torch  # noqa: F401
        import diffusers  # noqa: F401
        global _DIFFUSERS_AVAILABLE, _TORCH_AVAILABLE
        _DIFFUSERS_AVAILABLE = True
        _TORCH_AVAILABLE = True
        return True, ""
    except ImportError as e:
        return False, str(e)


_INSTALL_HINT = """
Image-to-Image style transfer requires:
    pip install diffusers transformers safetensors torch accelerate

For GPU support (recommended):
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
"""


class StyliseImg2ImgStep(PipelineStep):
    """Image-to-Image style transfer using Stable Diffusion 2.1."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Img2Img style transfer step.

        Args:
            config: Dictionary with optional keys:
                - prompt (str): Style guidance text
                - negative_prompt (str): What to avoid in generation
                - strength (float): 0.0–1.0, how much to modify (default: 0.7)
                - num_inference_steps (int): Quality vs speed tradeoff (default: 20)
                - guidance_scale (float): Prompt adherence 0–15 (default: 7.5)
                - model_id (str): Model from HF (default: stabilityai/stable-diffusion-2-1-base)
                - hf_token_path (str): Path to HF token file (optional, for gated models)
                - enable_model_cpu_offload (bool): Reduce VRAM (default: false)
                - device (str): "auto" (cuda > mps > cpu), or explicit device
        """
        super().__init__(config or {})

        # Defaults
        self.prompt = self.config.get("prompt", "artistic style, beautiful")
        self.negative_prompt = self.config.get("negative_prompt", "blurry, low quality, distorted")
        self.strength = float(self.config.get("strength", 0.7))
        self.num_inference_steps = int(self.config.get("num_inference_steps", 20))
        self.guidance_scale = float(self.config.get("guidance_scale", 7.5))
        self.model_id = self.config.get("model_id", "stabilityai/stable-diffusion-2-1-base")
        self.hf_token_path = self.config.get("hf_token_path", None)
        self.enable_model_cpu_offload = bool(self.config.get("enable_model_cpu_offload", False))
        self.device_str = self.config.get("device", "auto")

        # Clamp strength to valid range
        self.strength = max(0.0, min(1.0, self.strength))

        # State
        self.pipe = None
        self.device = None
        self._hf_token = None

    def _resolve_device(self) -> str:
        """Resolve target device: cuda > mps > cpu."""
        if self.device_str != "auto":
            return self.device_str

        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        except Exception:
            return "cpu"

    def _load_hf_token(self) -> str | None:
        """Load HuggingFace token from file if configured.
        
        Returns:
            Token string if file exists, None otherwise
        """
        if self._hf_token is not None:
            return self._hf_token
        
        if self.hf_token_path is None:
            return None
        
        from pathlib import Path
        token_path = Path(self.hf_token_path)
        
        if not token_path.exists():
            logger.warning(
                "[img2img] HF token file not found: %s. "
                "Model loading may fail if it's gated.",
                self.hf_token_path
            )
            return None
        
        try:
            self._hf_token = token_path.read_text().strip()
            logger.debug("[img2img] Loaded HF token from: %s", self.hf_token_path)
            return self._hf_token
        except Exception as e:
            logger.warning("[img2img] Failed to read HF token file: %s", e)
            return None

    def _load_models(self) -> None:
        """Lazy-load pipeline and models."""
        if self.pipe is not None:
            return

        ok, msg = _check_dependencies()
        if not ok:
            raise ImportError(f"{_INSTALL_HINT}\n\nMissing dependency: {msg}")

        try:
            from diffusers import StableDiffusionImg2ImgPipeline
            import torch
        except ImportError as e:
            raise ImportError(f"{_INSTALL_HINT}\n\n{e}") from e

        self.device = self._resolve_device()
        logger.debug("[img2img] Device detection: %s", self.device)

        # Load HF token if configured
        hf_token = self._load_hf_token()

        # Load lightweight SD 2.1 model
        logger.debug("[img2img] Loading model: %s on device: %s", self.model_id, self.device)
        try:
            self.pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                use_auth_token=hf_token,
            )
            self.pipe = self.pipe.to(self.device)
        except Exception as e:
            error_msg = str(e).lower()
            
            # Provide helpful error messages
            if "404" in error_msg or "not found" in error_msg:
                raise RuntimeError(
                    f"❌ Model not found: {self.model_id}\n\n"
                    f"This model may not exist or may be gated (requires authentication).\n\n"
                    f"Solutions:\n"
                    f"1. Check the model ID: https://huggingface.co/{self.model_id}\n"
                    f"2. If the model is gated, you need a HuggingFace token:\n"
                    f"   - Get token: https://huggingface.co/settings/tokens\n"
                    f"   - Save to file: echo 'hf_xxx...' > .hf_token\n"
                    f"   - Add to config: hf_token_path: '.hf_token'\n"
                    f"3. Accept model license at: https://huggingface.co/{self.model_id}"
                ) from e
            
            elif "401" in error_msg or "unauthorized" in error_msg or "token" in error_msg:
                raise RuntimeError(
                    f"❌ Authentication failed for model: {self.model_id}\n\n"
                    f"The HuggingFace token is missing or invalid.\n\n"
                    f"Solutions:\n"
                    f"1. Get a HuggingFace token: https://huggingface.co/settings/tokens\n"
                    f"2. Save it to a file: echo 'hf_xxx...' > .hf_token\n"
                    f"3. Add to pipeline config:\n"
                    f"   stylise_img2img:\n"
                    f"     model_id: '{self.model_id}'\n"
                    f"     hf_token_path: '.hf_token'\n"
                    f"4. Accept the model license: https://huggingface.co/{self.model_id}"
                ) from e
            
            else:
                raise RuntimeError(
                    f"❌ Failed to load model: {self.model_id}\n\n"
                    f"Error: {e}\n\n"
                    f"If the model is gated:\n"
                    f"1. Save HF token: echo 'hf_xxx...' > .hf_token\n"
                    f"2. Add to config: hf_token_path: '.hf_token'"
                ) from e

        if self.enable_model_cpu_offload:
            logger.debug("[img2img] Enabling model CPU offload")
            self.pipe.enable_attention_slicing()
            try:
                self.pipe.enable_model_cpu_offload()
            except AttributeError:
                logger.warning("[img2img] Model CPU offload not supported by this version")

    def process(self, ctx: ImageContext) -> ImageContext:
        """Apply img2img style transfer.

        Args:
            ctx: ImageContext with image

        Returns:
            ImageContext with stylized image
        """
        self._load_models()

        # Get input image
        image = ctx.image
        if image is None:
            raise ValueError("Img2ImgStep: No image in context")

        # Resize to smaller dimension for faster processing
        max_dim = min(768, max(image.width, image.height))
        if max(image.width, image.height) > max_dim:
            ratio = max_dim / max(image.width, image.height)
            new_w = int(image.width * ratio)
            new_h = int(image.height * ratio)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        logger.debug(
            "[img2img] Input image: %dx%d px, strength=%.2f",
            image.width, image.height, self.strength
        )

        try:
            # Run img2img pipeline
            result = self.pipe(
                prompt=self.prompt,
                negative_prompt=self.negative_prompt,
                image=image,
                strength=self.strength,
                num_inference_steps=self.num_inference_steps,
                guidance_scale=self.guidance_scale,
            )
            stylized_image = result.images[0]

            logger.debug("[img2img] Output: %dx%d px", stylized_image.width, stylized_image.height)

            # Binarize to black/white for plotting
            grayscale = stylized_image.convert("L")
            threshold = 128
            binary = grayscale.point(lambda x: 0 if x < threshold else 255, "1")
            binary_array = np.array(binary, dtype=np.uint8) * 255

            ctx.image = binary
            ctx.intermediates["stylized_image"] = stylized_image
            ctx.intermediates["binary"] = binary_array

            return ctx

        except Exception as e:
            logger.error("[img2img] Pipeline failed: %s", str(e))
            raise
