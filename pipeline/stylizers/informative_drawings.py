"""
pipeline/stylizers/informative_drawings.py — Informative Drawings (Line Art)

Konvertiert Fotos in saubere, informative Strichzeichnungen.
Basiert auf dem Modell von Caroline Chan et al. (CVPR 2022).

Zwei Backends werden unterstützt (in dieser Reihenfolge versucht):

  1. **ONNX** (bevorzugt) — leichtgewichtig, keine GPU-Treiber nötig.
     Modell: ``model.onnx`` (~17 MB) von
     https://huggingface.co/rocca/informative-drawings-line-art-onnx
     Benötigt: pip install onnxruntime pillow numpy

  2. **PyTorch** (Fallback) — direkte Inferenz mit dem Original-Generator.
     Modell: ``model.pth`` oder ``model2.pth`` von
     https://huggingface.co/spaces/carolineec/informativedrawings/tree/main
     Benötigt: pip install torch torchvision pillow

Referenz:
    Chan et al. 2022, "Learning to generate line drawings that convey
    geometry and semantics", CVPR 2022
    https://arxiv.org/abs/2203.12691
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from pipeline.stylizers.base import BaseStylizer
from pipeline.stylizers.nn_base import _resolve_device

logger = logging.getLogger(__name__)

_ONNX_INSTALL_HINT = (
    "onnxruntime ist nicht installiert. "
    "Installiere es mit:  pip install onnxruntime pillow numpy\n"
    "Alternativ für GPU: pip install onnxruntime-gpu pillow numpy"
)
_TORCH_INSTALL_HINT = (
    "Weder onnxruntime noch torch sind installiert.\n"
    "Installiere eines von:\n"
    "  pip install onnxruntime pillow numpy          # ONNX (empfohlen)\n"
    "  pip install torch torchvision pillow           # PyTorch-Fallback"
)
_HF_ONNX_REPO = "rocca/informative-drawings-line-art-onnx"
_HF_TORCH_SPACE = "carolineec/informativedrawings"


class InformativeDrawingsStylizer(BaseStylizer):
    """
    Informative-Drawings Stilisierer.

    Erzeugt klare, geometriebewusste Strichzeichnungen aus Fotos.

    Das Modell gibt Werte in [0, 1] aus, wobei **niedrige Werte dunklen
    Linien** entsprechen (invertiert zum Canny-Format). Die Klasse
    invertiert das Ergebnis automatisch, sodass Linien = 255 gilt.

    Parameters
    ----------
    model_path : Pfad zu ``model.onnx`` (ONNX) oder ``model.pth`` (PyTorch).
                 Wenn ``None``, wird das ONNX-Modell von Hugging Face
                 heruntergeladen (erfordert ``huggingface_hub``).
    device     : Gerät für PyTorch-Backend. ``None``/``"auto"`` →
                 cuda > mps > cpu. Wird beim ONNX-Backend ignoriert
                 (ONNX verwendet intern den besten verfügbaren Provider).
    threshold  : Binarisierungsschwelle (0–255) auf dem invertierten Output.
                 Niedrigere Werte = mehr Linien. Standard: 128.
    style      : ``1`` (Style 1, schärfere Linien) oder ``2`` (Style 2,
                 weichere Linien). Nur relevant wenn ``model_path`` ein
                 Verzeichnis mit ``model.pth`` und ``model2.pth`` enthält
                 oder beim PyTorch-Download-Fallback.
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
        self.device: str = _resolve_device(device)
        self.threshold = threshold
        self.style = style
        self._session: Any = None   # onnxruntime.InferenceSession (lazy)
        self._torch_model: Any = None  # torch.nn.Module (lazy)
        self._backend: str | None = None  # "onnx" or "torch" nach dem Laden

    # ------------------------------------------------------------------
    # Lazy-Loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lädt ONNX- oder PyTorch-Modell beim ersten Aufruf."""
        if self._session is not None or self._torch_model is not None:
            return

        # Versuche ONNX zuerst
        if self._try_load_onnx():
            return

        # Fallback auf PyTorch
        self._load_torch()

    def _onnx_model_path(self) -> Path:
        """Gibt den Pfad zur ONNX-Modelldatei zurück, lädt ggf. herunter."""
        if self.model_path is not None:
            p = self.model_path
            # Verzeichnis? → model.onnx darin suchen
            if p.is_dir():
                return p / "model.onnx"
            return p  # direkter Dateipfad

        # Auto-Download via huggingface_hub
        try:
            from huggingface_hub import hf_hub_download  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "huggingface_hub ist nicht installiert. "
                "Installiere es mit: pip install huggingface_hub\n"
                "Oder gib den Pfad zur model.onnx direkt mit --model-path an."
            )
        logger.debug("[informative] Lade model.onnx von HF: %s …", _HF_ONNX_REPO)
        return Path(
            hf_hub_download(repo_id=_HF_ONNX_REPO, filename="model.onnx")
        )

    def _try_load_onnx(self) -> bool:
        """Versucht ONNX-Session zu laden. Gibt True bei Erfolg zurück."""
        try:
            import onnxruntime as ort  # type: ignore[import]
        except ImportError:
            logger.debug("[informative] onnxruntime nicht verfügbar, versuche PyTorch …")
            return False

        try:
            onnx_path = self._onnx_model_path()
        except (ImportError, FileNotFoundError) as exc:
            logger.debug("[informative] ONNX-Modell nicht auffindbar: %s", exc)
            return False

        if not onnx_path.exists():
            logger.debug("[informative] ONNX-Modell nicht gefunden: %s", onnx_path)
            return False

        providers = ort.get_available_providers()
        logger.debug("[informative] ONNX laden: %s  Providers: %s", onnx_path, providers)
        self._session = ort.InferenceSession(str(onnx_path), providers=providers)
        self._backend = "onnx"
        logger.debug("[informative] ONNX-Backend aktiv.")
        return True

    def _torch_model_path(self) -> Path:
        """Gibt den Pfad zur PyTorch-Modelldatei zurück, lädt ggf. herunter."""
        if self.model_path is not None:
            p = self.model_path
            if p.is_dir():
                fname = "model2.pth" if self.style == 2 else "model.pth"
                return p / fname
            return p

        # Auto-Download via huggingface_hub
        try:
            from huggingface_hub import hf_hub_download  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "huggingface_hub ist nicht installiert. "
                "Installiere es mit: pip install huggingface_hub"
            )
        fname = "model2.pth" if self.style == 2 else "model.pth"
        logger.debug("[informative] Lade %s von HF Space: %s …", fname, _HF_TORCH_SPACE)
        return Path(
            hf_hub_download(repo_id=_HF_TORCH_SPACE, filename=fname, repo_type="space")
        )

    def _load_torch(self) -> None:
        """Lädt PyTorch-Modell (Fallback wenn ONNX nicht verfügbar)."""
        try:
            import torch  # type: ignore[import]
            import torch.nn as nn  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_TORCH_INSTALL_HINT) from exc

        norm_layer = nn.InstanceNorm2d

        class ResidualBlock(nn.Module):
            def __init__(self, in_features: int) -> None:
                super().__init__()
                self.conv_block = nn.Sequential(
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(in_features, in_features, 3),
                    norm_layer(in_features),
                    nn.ReLU(inplace=True),
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(in_features, in_features, 3),
                    norm_layer(in_features),
                )

            def forward(self, x: Any) -> Any:
                return x + self.conv_block(x)

        class Generator(nn.Module):
            def __init__(self, input_nc: int, output_nc: int, n_residual_blocks: int = 9) -> None:
                super().__init__()
                self.model0 = nn.Sequential(
                    nn.ReflectionPad2d(3),
                    nn.Conv2d(input_nc, 64, 7),
                    norm_layer(64),
                    nn.ReLU(inplace=True),
                )
                model1: list[nn.Module] = []
                in_f, out_f = 64, 128
                for _ in range(2):
                    model1 += [nn.Conv2d(in_f, out_f, 3, stride=2, padding=1), norm_layer(out_f), nn.ReLU(inplace=True)]
                    in_f, out_f = out_f, out_f * 2
                self.model1 = nn.Sequential(*model1)
                self.model2 = nn.Sequential(*[ResidualBlock(in_f) for _ in range(n_residual_blocks)])
                model3: list[nn.Module] = []
                out_f = in_f // 2
                for _ in range(2):
                    model3 += [nn.ConvTranspose2d(in_f, out_f, 3, stride=2, padding=1, output_padding=1), norm_layer(out_f), nn.ReLU(inplace=True)]
                    in_f, out_f = out_f, out_f // 2
                self.model3 = nn.Sequential(*model3)
                self.model4 = nn.Sequential(nn.ReflectionPad2d(3), nn.Conv2d(64, output_nc, 7), nn.Sigmoid())

            def forward(self, x: Any) -> Any:  # type: ignore[override]
                return self.model4(self.model3(self.model2(self.model1(self.model0(x)))))

        torch_path = self._torch_model_path()
        logger.debug("[informative] PyTorch laden: %s  device=%s …", torch_path, self.device)
        model = Generator(3, 1, 3)
        model.load_state_dict(torch.load(str(torch_path), map_location=torch.device(self.device)))
        model.eval()
        model.to(self.device)
        self._torch_model = model
        self._backend = "torch"
        logger.debug("[informative] PyTorch-Backend aktiv (device=%s).", self.device)

    # ------------------------------------------------------------------
    # Inferenz
    # ------------------------------------------------------------------

    def _run_onnx(self, rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        """Führt ONNX-Inferenz durch. Erwartet uint8 RGB (H,W,3)."""
        # Normalisierung: [0,255] → [0,1], Layout: (1, 3, H, W)
        x = rgb.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]  # (1,3,H,W)
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: x})
        # Output: (1, 1, H, W) mit Werten in [0,1]
        return outputs[0][0, 0]  # (H, W)

    def _run_torch(self, rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        """Führt PyTorch-Inferenz durch. Erwartet uint8 RGB (H,W,3)."""
        import torch  # type: ignore[import]

        x = torch.from_numpy(rgb.astype(np.float32) / 255.0)
        x = x.permute(2, 0, 1).unsqueeze(0).to(self.device)  # (1,3,H,W)
        with torch.no_grad():
            out = self._torch_model(x)  # (1,1,H,W)
        return out[0, 0].cpu().numpy()  # (H,W)

    def apply(self, gray: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        self._load_model()

        # Grau → RGB für das Modell
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        if self._backend == "onnx":
            output = self._run_onnx(rgb)
        else:
            output = self._run_torch(rgb)

        # Output in [0,1]: niedrig = dunkle Linie → invertieren
        # sodass Linie = 255 (wie alle anderen Stilisierer)
        inverted = ((1.0 - output) * 255.0).clip(0, 255).astype(np.uint8)

        _, binary = cv2.threshold(inverted, self.threshold, 255, cv2.THRESH_BINARY)
        logger.debug(
            "[informative] Ausgabe %dx%d (backend=%s)",
            binary.shape[1], binary.shape[0], self._backend,
        )
        return binary
