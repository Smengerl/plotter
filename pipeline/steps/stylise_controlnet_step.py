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

Example config:
    config:
      prompt: "oil painting, Van Gogh style, vibrant colors"
      negative_prompt: "blurry, low quality"
      controlnet_type: "canny"  # or lineart, softedge, scribble, etc.
      num_inference_steps: 20
      guidance_scale: 7.5
      strength: 0.8
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
        global _TORCH_AVAILABLE, _DIFFUSERS_AVAILABLE
        _TORCH_AVAILABLE = True
        _DIFFUSERS_AVAILABLE = True
        return True, ""
    except ImportError as e:
        return False, f"Missing dependency: {e}"


_INSTALL_HINT = """
ControlNet + Stable Diffusion 1.5 style transfer requires:
    pip install diffusers transformers safetensors torch accelerate

For GPU support (recommended):
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
"""


class StyliseControlNetStep(PipelineStep):
    """
    Style transfer using ControlNet + Stable Diffusion 1.5.

    Applies artistic style to an image via text-prompt guided diffusion
    with ControlNet conditioning. Converts the stylized result back to
    binary (black/white) for pen plotting.

    Parameters
    ----------
    prompt : str
        Text prompt describing desired style (e.g., "oil painting, Van Gogh style")
    negative_prompt : str, optional
        Text to avoid in generation (e.g., "blurry, low quality")
    controlnet_type : str
        ControlNet variant: "canny", "lineart", "softedge", "scribble", "pose", etc.
        Default: "lineart"
    num_inference_steps : int
        Denoising steps (more = higher quality, slower). Default: 20
    guidance_scale : float
        Prompt adherence (7.5 = strong, 1.0 = weak). Default: 7.5
    strength : float
        How much to modify image (0.0–1.0, 1.0 = maximum). Default: 0.8
    enable_model_cpu_offload : bool
        Enable CPU offloading to reduce VRAM (slower). Default: false
    device : str
        PyTorch device: "auto", "cpu", "cuda", "mps". Default: "auto"
    model_id : str
        Hugging Face model ID for base diffusion model.
        Default: "runwayml/stable-diffusion-v1-5"
    """

    name = "stylise_controlnet"

    def __init__(
        self,
        prompt: str = "oil painting, masterpiece, detailed",
        negative_prompt: str = "blurry, distorted, low quality",
        controlnet_type: str = "lineart",
        num_inference_steps: int = 20,
        guidance_scale: float = 7.5,
        strength: float = 0.8,
        enable_model_cpu_offload: bool = False,
        device: str = "auto",
        model_id: str = "runwayml/stable-diffusion-v1-5",
        hf_token_path: str | None = None,
    ) -> None:
        super().__init__()
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.controlnet_type = controlnet_type
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.strength = strength
        self.enable_model_cpu_offload = enable_model_cpu_offload
        self.device = device
        self.model_id = model_id
        self.hf_token_path = hf_token_path

        # Lazy-loaded objects
        self._pipe = None
        self._controlnet = None
        self._device = self._resolve_device(device)
        self._hf_token = None

    def _resolve_device(self, device: str) -> str:
        """Resolve device string to actual PyTorch device."""
        if device in ("auto", ""):
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps"
                else:
                    return "cpu"
            except ImportError:
                return "cpu"
        return device
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
                "[controlnet] HF token file not found: %s. "
                "Model loading may fail if it's gated.",
                self.hf_token_path
            )
            return None
        
        try:
            self._hf_token = token_path.read_text().strip()
            logger.debug("[controlnet] Loaded HF token from: %s", self.hf_token_path)
            return self._hf_token
        except Exception as e:
            logger.warning("[controlnet] Failed to read HF token file: %s", e)
            return None

    def _load_models(self) -> None:
        """Lazy-load ControlNet and StableDiffusion pipeline."""
        if self._pipe is not None:
            return  # Already loaded

        ok, msg = _check_dependencies()
        if not ok:
            raise ImportError(f"{_INSTALL_HINT}\n\n{msg}")

        try:
            from diffusers import ControlNetModel, StableDiffusionControlNetPipeline
            import torch

            logger.info(
                f"Loading ControlNet ({self.controlnet_type}) + SD 1.5 on {self._device}..."
            )

            # Load HF token if configured
            hf_token = self._load_hf_token()

            # Map controlnet_type to Hugging Face repo
            # Using control_v11p models (newer, more stable)
            controlnet_repo_map = {
                "canny": "lllyasviel/control_v11p_sd15_canny",
                "lineart": "lllyasviel/control_v11p_sd15_lineart",
                "softedge": "lllyasviel/control_v11p_sd15_softedge",
                "scribble": "lllyasviel/control_v11p_sd15_scribble",
                "pose": "lllyasviel/control_v11p_sd15_openpose",
                "depth": "lllyasviel/control_v11f1p_sd15_depth",
                "normal": "lllyasviel/control_v11p_sd15_normal",
                "seg": "lllyasviel/control_v11p_sd15_seg",
            }

            controlnet_repo = controlnet_repo_map.get(
                self.controlnet_type, controlnet_repo_map["lineart"]
            )

            # Load ControlNet with error handling
            try:
                self._controlnet = ControlNetModel.from_pretrained(
                    controlnet_repo, torch_dtype=torch.float16, use_auth_token=hf_token
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "404" in error_msg or "not found" in error_msg:
                    raise RuntimeError(
                        f"❌ ControlNet model not found: {controlnet_repo}\n\n"
                        f"Solutions:\n"
                        f"1. Check the model ID exists on HuggingFace\n"
                        f"2. If gated, get token: https://huggingface.co/settings/tokens\n"
                        f"3. Save: echo 'hf_xxx...' > .hf_token\n"
                        f"4. Add to config: hf_token_path: '.hf_token'"
                    ) from e
                raise

            # Load base pipeline with error handling
            try:
                self._pipe = StableDiffusionControlNetPipeline.from_pretrained(
                    self.model_id,
                    controlnet=self._controlnet,
                    torch_dtype=torch.float16,
                    use_auth_token=hf_token,
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "404" in error_msg or "not found" in error_msg:
                    raise RuntimeError(
                        f"❌ Base model not found: {self.model_id}\n\n"
                        f"Solutions:\n"
                        f"1. Check the model ID exists on HuggingFace\n"
                        f"2. If gated, get token: https://huggingface.co/settings/tokens\n"
                        f"3. Save: echo 'hf_xxx...' > .hf_token\n"
                        f"4. Add to config: hf_token_path: '.hf_token'"
                    ) from e
                raise

            # Move to device
            self._pipe = self._pipe.to(self._device)

            # Optional CPU offloading
            if self.enable_model_cpu_offload:
                self._pipe.enable_model_cpu_offload()
                logger.info("Model CPU offloading enabled (reduces VRAM)")
            else:
                # Enable memory-efficient attention if available
                try:
                    self._pipe.enable_attention_slicing()
                except Exception:
                    pass

            logger.info(
                f"ControlNet pipeline loaded successfully (device: {self._device})"
            )

        except Exception as e:
            raise RuntimeError(
                f"Failed to load ControlNet pipeline: {e}\n{_INSTALL_HINT}"
            ) from e

    def _prepare_controlnet_input(self, image: Image.Image) -> Image.Image:
        """
        Prepare image for ControlNet conditioning.

        For lineart: use as-is.
        For canny: detect edges.
        For other types: apply appropriate preprocessing.
        """
        if self.controlnet_type == "canny":
            # Apply Canny edge detection
            import cv2

            img_array = np.array(image.convert("L"))
            edges = cv2.Canny(img_array, 100, 200)
            return Image.fromarray(edges)
        elif self.controlnet_type == "softedge":
            # Use PIL edge enhance
            from PIL import ImageFilter

            return image.filter(ImageFilter.EDGE_ENHANCE_MORE)
        else:
            # For lineart, scribble, pose, depth, etc. - use as-is
            # In production, these would need specific preprocessing
            return image.convert("RGB")

    def process(self, ctx: ImageContext) -> ImageContext:
        """
        Apply ControlNet style transfer to the image.

        Steps:
        1. Load models (lazy)
        2. Prepare ControlNet input
        3. Run diffusion pipeline
        4. Binarize result (for plotting)
        5. Update context
        """
        self._load_models()

        rgb_pil = ctx.current_image.convert("RGB")
        logger.info(
            f"Applying ControlNet style transfer ({self.controlnet_type}) with prompt: {self.prompt}"
        )

        # Prepare ControlNet conditioning image
        control_image = self._prepare_controlnet_input(rgb_pil)
        control_image = control_image.resize((rgb_pil.width, rgb_pil.height))

        try:
            # Run diffusion pipeline
            output = self._pipe(
                prompt=self.prompt,
                negative_prompt=self.negative_prompt,
                image=rgb_pil,
                control_image=control_image,
                num_inference_steps=self.num_inference_steps,
                guidance_scale=self.guidance_scale,
                strength=self.strength,
                height=rgb_pil.height,
                width=rgb_pil.width,
            )
            stylized = output.images[0]

        except Exception as e:
            logger.error(f"Style transfer failed: {e}")
            raise

        # Binarize for plotting
        gray = stylized.convert("L")
        threshold = 128
        binary = gray.point(lambda x: 255 if x > threshold else 0, "1")

        logger.info(
            f"Style transfer complete: {binary.size[0]}×{binary.size[1]} px (binary)"
        )

        # Update context
        ctx.current_image = binary
        ctx.add_intermediate("stylized_diffusion", stylized)
        ctx.add_intermediate("controlnet_condition", control_image)

        return ctx
