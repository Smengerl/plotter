"""
pipeline/steps/stylise_informative_step.py - Informative Drawings as PipelineStep

Converts photos into clean, informative line drawings.
Based on the model by Caroline Chan et al. (CVPR 2022).

Two backends (tried in this order):
  1. ONNX (preferred) - pip install onnxruntime pillow numpy
  2. PyTorch (fallback) - pip install torch torchvision pillow

Data transport via ImageContext
--------------------------------
Reads   ctx.metadata["source_path"]  - Path to input image file
Writes  ctx.intermediates["binary"]  - uint8 array (H, W), 255=line
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import cv2
import numpy as np
import numpy.typing as npt

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.steps.base.stylizer_base import BaseStylizer, resolve_device

if TYPE_CHECKING:
    import torch.nn as nn  # type: ignore[import]

logger = logging.getLogger(__name__)

_ONNX_INSTALL_HINT = (
    "onnxruntime is not installed. "
    "Install it with:  pip install onnxruntime pillow numpy\n"
    "Or for GPU: pip install onnxruntime-gpu pillow numpy"
)
_TORCH_INSTALL_HINT = (
    "Neither onnxruntime nor torch are installed.\n"
    "Install one of:\n"
    "  pip install onnxruntime pillow numpy          # ONNX (recommended)\n"
    "  pip install torch torchvision pillow           # PyTorch fallback"
)

# ---------------------------------------------------------------------------
# PyTorch Model Architecture (Chan et al. CVPR 2022)
# Defined at module level so it's importable and separately testable.
# norm_layer is passed at instantiation (InstanceNorm2d for inference).
# ---------------------------------------------------------------------------

def _make_residual_block(norm_layer: "type[nn.Module]") -> "type[nn.Module]":
    """Factory for ResidualBlock with configurable norm_layer."""
    import torch.nn as _nn  # type: ignore[import]

    class ResidualBlock(_nn.Module):
        def __init__(self, in_features: int) -> None:
            super().__init__()
            self.conv_block = _nn.Sequential(
                _nn.ReflectionPad2d(1),
                _nn.Conv2d(in_features, in_features, 3),
                norm_layer(in_features),
                _nn.ReLU(inplace=True),
                _nn.ReflectionPad2d(1),
                _nn.Conv2d(in_features, in_features, 3),
                norm_layer(in_features),
            )

        def forward(self, x: Any) -> Any:
            return x + self.conv_block(x)

    return ResidualBlock


def _make_generator(norm_layer: "type[nn.Module]") -> "type[nn.Module]":
    """Factory for Generator with configurable norm_layer."""
    import torch.nn as _nn  # type: ignore[import]
    ResidualBlock = _make_residual_block(norm_layer)

    class Generator(_nn.Module):
        def __init__(self, input_nc: int, output_nc: int, n_residual_blocks: int = 9) -> None:
            super().__init__()
            self.model0 = _nn.Sequential(
                _nn.ReflectionPad2d(3),
                _nn.Conv2d(input_nc, 64, 7),
                norm_layer(64),
                _nn.ReLU(inplace=True),
            )
            model1: list[_nn.Module] = []
            in_f, out_f = 64, 128
            for _ in range(2):
                model1 += [_nn.Conv2d(in_f, out_f, 3, stride=2, padding=1), norm_layer(out_f), _nn.ReLU(inplace=True)]
                in_f, out_f = out_f, out_f * 2
            self.model1 = _nn.Sequential(*model1)
            self.model2 = _nn.Sequential(*[ResidualBlock(in_f) for _ in range(n_residual_blocks)])
            model3: list[_nn.Module] = []
            out_f = in_f // 2
            for _ in range(2):
                model3 += [_nn.ConvTranspose2d(in_f, out_f, 3, stride=2, padding=1, output_padding=1), norm_layer(out_f), _nn.ReLU(inplace=True)]
                in_f, out_f = out_f, out_f // 2
            self.model3 = _nn.Sequential(*model3)
            self.model4 = _nn.Sequential(_nn.ReflectionPad2d(3), _nn.Conv2d(64, output_nc, 7), _nn.Sigmoid())

        def forward(self, x: Any) -> Any:  # type: ignore[override]
            return self.model4(self.model3(self.model2(self.model1(self.model0(x)))))

    return Generator

_HF_ONNX_REPO = "rocca/informative-drawings-line-art-onnx"
_HF_TORCH_SPACE = "carolineec/informativedrawings"


class _InformativeDrawingsStylizer(BaseStylizer):
    """
    Informative Drawings stylizer (Chan et al. CVPR 2022).

    Low model output values = dark lines → automatically inverted,
    so that line = 255.
    """

    name = "informative"

    def __init__(
        self,
        model_path: Path | str | None = None,
        device: str | None = None,
        threshold: int = 128,
        style: int = 1,
    ) -> None:
        self.model_path = Path(model_path) if model_path is not None else None
        self.device: str = resolve_device(device)
        self.threshold = threshold
        self.style = style
        self._session: Any = None
        self._torch_model: Any = None
        self._backend: str | None = None

    def _load_model(self) -> None:
        if self._session is not None or self._torch_model is not None:
            return
        if self._try_load_onnx():
            return
        self._load_torch()

    def _onnx_model_path(self) -> Path:
        if self.model_path is not None:
            p = self.model_path
            return p / "model.onnx" if p.is_dir() else p
        try:
            from huggingface_hub import hf_hub_download  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "huggingface_hub is not installed. "
                "Install it with: pip install huggingface_hub\n"
                "Or provide the path to model.onnx directly with --model-path."
            )
        logger.debug("[informative] Loading model.onnx from HF: %s …", _HF_ONNX_REPO)
        return Path(hf_hub_download(repo_id=_HF_ONNX_REPO, filename="model.onnx"))

    def _try_load_onnx(self) -> bool:
        try:
            import onnxruntime as ort  # type: ignore[import]
        except ImportError:
            logger.debug("[informative] onnxruntime not available, trying PyTorch …")
            return False
        try:
            onnx_path = self._onnx_model_path()
        except (ImportError, FileNotFoundError) as exc:
            logger.debug("[informative] ONNX model not found: %s", exc)
            return False
        if not onnx_path.exists():
            logger.debug("[informative] ONNX model file not found: %s", onnx_path)
            return False
        providers = ort.get_available_providers()
        logger.debug("[informative] Loading ONNX: %s  Providers: %s", onnx_path, providers)
        self._session = ort.InferenceSession(str(onnx_path), providers=providers)
        self._backend = "onnx"
        logger.debug("[informative] ONNX backend active.")
        return True

    def _torch_model_path(self) -> Path:
        if self.model_path is not None:
            p = self.model_path
            if p.is_dir():
                fname = "model2.pth" if self.style == 2 else "model.pth"
                return p / fname
            return p
        try:
            from huggingface_hub import hf_hub_download  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "huggingface_hub is not installed. "
                "Install it with: pip install huggingface_hub"
            )
        fname = "model2.pth" if self.style == 2 else "model.pth"
        logger.debug("[informative] Loading %s from HF Space: %s …", fname, _HF_TORCH_SPACE)
        return Path(
            hf_hub_download(repo_id=_HF_TORCH_SPACE, filename=fname, repo_type="space")
        )

    def _load_torch(self) -> None:
        try:
            import torch  # type: ignore[import]
            import torch.nn as nn  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_TORCH_INSTALL_HINT) from exc

        norm_layer = nn.InstanceNorm2d
        Generator = _make_generator(norm_layer)

        torch_path = self._torch_model_path()
        logger.debug("[informative] Loading PyTorch: %s  device=%s …", torch_path, self.device)
        model = Generator(3, 1, 3)
        model.load_state_dict(torch.load(str(torch_path), map_location=torch.device(self.device)))
        model.eval()
        model.to(self.device)
        self._torch_model = model
        self._backend = "torch"
        logger.debug("[informative] PyTorch backend active (device=%s).", self.device)

    def _run_onnx(self, rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        x = rgb.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: x})
        return outputs[0][0, 0]  # type: ignore[no-any-return]

    def _run_torch(self, rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        import torch  # type: ignore[import]
        x = torch.from_numpy(rgb.astype(np.float32) / 255.0)
        x = x.permute(2, 0, 1).unsqueeze(0).to(self.device)
        with torch.no_grad():
            out = self._torch_model(x)
        return out[0, 0].cpu().numpy()  # type: ignore[no-any-return]

    def apply(self, gray: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        self._load_model()
        rgb: npt.NDArray[np.uint8] = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB).astype(np.uint8)
        if self._backend == "onnx":
            output = self._run_onnx(rgb)
        else:
            output = self._run_torch(rgb)
        # Output in [0,1]: low = dark line → invert, line=255
        inverted = ((1.0 - output) * 255.0).clip(0, 255).astype(np.uint8)
        _, binary = cv2.threshold(inverted, self.threshold, 255, cv2.THRESH_BINARY)
        logger.debug(
            "[informative] Output %dx%d (backend=%s)",
            binary.shape[1], binary.shape[0], self._backend,
        )
        return binary.astype(np.uint8)


class StyliseInformativeStep(PipelineStep):
    """
    Stylization step using Informative Drawings (Chan et al. CVPR 2022).

    Requires: pip install onnxruntime pillow numpy
    (or: pip install torch torchvision pillow)

    config keys      Default  Corresponds to CLI flag
    -----------------------------------------------
    style_res        1024     --style-res
    model_path       None     --model-path
    device           "auto"   --device
    inform_style     1        --inform-style
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._stylizer: Optional[_InformativeDrawingsStylizer] = None

    def _get_stylizer(self) -> _InformativeDrawingsStylizer:
        """Creates the stylizer on first call (lazy initialization)."""
        if self._stylizer is None:
            c = self.config
            model_path_raw = c.get("model_path")
            self._stylizer = _InformativeDrawingsStylizer(
                model_path=Path(model_path_raw) if model_path_raw is not None else None,
                device=str(c.get("device", "auto")),
                style=int(c.get("inform_style", 1)),
            )
        return self._stylizer

    def process(self, ctx: ImageContext) -> ImageContext:
        max_side: int = int(self.config.get("style_res", 1024))
        binary = self._get_stylizer().stylise(ctx.metadata["source_path"], max_side)
        logger.debug("StyliseInformativeStep: Binary image %dx%d px", binary.shape[1], binary.shape[0])
        ctx.intermediates["binary"] = binary
        return ctx
