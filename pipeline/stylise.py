"""
pipeline/stylise.py — Schritt 1: Bild → vereinfachter Linienstil

Diese Datei ist die öffentliche Schnittstelle des Stylisierungs-Schritts.
Die konkreten Implementierungen liegen in ``pipeline/stylizers/``.

Unterstützte Methoden:
  canny   — klassischer OpenCV Canny-Kantendetektor
  xdog    — eXtended Difference-of-Gaussians (Pencil-Sketch-Effekt)
  hed     — Holistically-nested Edge Detection (PyTorch-Modell)
  dexined — Dense Extreme Inception Network for Edge Detection (PyTorch)

Alle Methoden geben ein uint8-Binärbild zurück (255 = Linie, 0 = Hintergrund).
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from pipeline.stylizers import STYLE_CHOICES, get_stylizer

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

# Re-export damit bestehende Imports (``from pipeline.stylise import STYLE_CHOICES``) weiterhin funktionieren
__all__ = ["stylise_image", "STYLE_CHOICES"]

logger = logging.getLogger(__name__)


def stylise_image(args: argparse.Namespace) -> "npt.NDArray[np.uint8]":
    """
    Liest das Eingabebild, skaliert es auf ``args.style_res`` (längste Seite)
    und wandelt es mit der gewählten Methode in ein Binärbild um.

    Der konkrete Stilisierer wird anhand von ``args.style`` aus der Registry
    in ``pipeline.stylizers`` ausgewählt.

    Parameters
    ----------
    args : Namespace aus ``img2gcode.build_parser()``

    Returns
    -------
    binary : np.ndarray, dtype=uint8, shape (H, W)
        Weiße Pixel (255) = Linie, schwarze Pixel (0) = Hintergrund.
    """
    stylizer = get_stylizer(
        args.style,
        **_kwargs_for_style(args),
    )
    logger.debug("Stilisierer: %s (%s)", stylizer.name, type(stylizer).__name__)
    return stylizer.stylise(args.image, max_side=args.style_res)


# ---------------------------------------------------------------------------
# Interne Hilfsfunktion: CLI-Args → Konstruktor-Kwargs
# ---------------------------------------------------------------------------

def _kwargs_for_style(args: argparse.Namespace) -> dict[str, object]:
    """Extrahiert die relevanten Konstruktor-Parameter aus dem CLI-Namespace."""
    if args.style == "canny":
        return {
            "low":  args.canny_low,
            "high": args.canny_high,
            "blur": args.canny_blur,
        }
    if args.style == "xdog":
        return {
            "sigma":     args.sigma,
            "k_sigma":   args.k_sigma,
            "epsilon":   args.epsilon,
            "phi":       args.phi,
            "threshold": args.threshold,
        }
    if args.style in ("hed", "dexined"):
        return {
            "model_path": args.model_path,
            "device":     args.device,
        }
    if args.style == "adaptive":
        return {
            "block_size": args.block_size,
            "c":          args.adapt_c,
            "method":     args.adapt_method,
            "blur":       args.adapt_blur,
        }
    if args.style == "informative":
        return {
            "model_path": args.model_path,
            "device":     args.device,
            "threshold":  args.threshold,
            "style":      args.inform_style,
        }
    if args.style == "lineart":
        return {
            "model_path":        args.model_path,
            "device":            args.device,
            "threshold":         args.threshold,
            "coarse":            args.lineart_coarse,
            "detect_resolution": args.lineart_detect_res,
            "image_resolution":  args.lineart_image_res,
        }
    return {}
