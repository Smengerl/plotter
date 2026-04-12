"""
pipeline/vectorise.py — Schritt 2: Binärbild → Pfad-Liste

Extrahiert zusammenhängende Konturen aus dem Binärbild und gibt sie als
Liste von (N×2)-Arrays zurück, wobei jede Spalte (x, y) in Pixel-Koordinaten
enthält.

Pfade werden:
  - nach Mindestlänge gefiltert (--min-path-px)
  - mit dem Ramer-Douglas-Peucker-Algorithmus vereinfacht (--simplify-eps)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


# Typ-Alias: Liste von (N, 2)-Arrays mit float-Koordinaten
PathList = list["npt.NDArray[np.float32]"]


def paths_to_svg(
    paths: "PathList",
    image_shape: tuple[int, int],
    output_path: Path,
) -> None:
    """
    Schreibt die extrahierten Pixel-Pfade als SVG-Datei.

    Parameters
    ----------
    paths        : Pfade aus ``vectorise()``
    image_shape  : (H, W) des Quellbildes — wird als SVG-Viewport genutzt
    output_path  : Zieldatei (.svg)
    """
    h, w = image_shape
    lines: list[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                 f'viewBox="0 0 {w} {h}">')
    lines.append(f'  <rect width="{w}" height="{h}" fill="white"/>')

    for path in paths:
        if len(path) < 2:
            continue
        coords = " ".join(f"{pt[0]:.1f},{pt[1]:.1f}" for pt in path)
        lines.append(f'  <polyline points="{coords}" '
                     f'fill="none" stroke="black" stroke-width="1"/>')

    lines.append("</svg>")

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.debug("SVG gespeichert: %s  (%d Pfade)", output_path, len(paths))


def vectorise(
    binary: "npt.NDArray[np.uint8]",
    min_path_px: int = 10,
    simplify_eps: float = 1.5,
) -> PathList:
    """
    Konvertiert ein Binärbild (255=Linie) in eine geordnete Liste von Pfaden.

    Parameters
    ----------
    binary       : uint8-Array (H, W),  255 = Linie,  0 = Hintergrund
    min_path_px  : Pfade kürzer als dieser Wert (in Pixeln Bogenmaß) werden verworfen
    simplify_eps : Toleranz in Pixeln für Ramer-Douglas-Peucker-Vereinfachung

    Returns
    -------
    paths : Liste von (N, 2)-float32-Arrays  [(x0,y0), (x1,y1), …]
    """
    # Konturen finden (externe + interne Konturen)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    logger.debug("cv2.findContours: %d Rohrpfade gefunden", len(contours))

    paths: PathList = []

    for contour in contours:
        # contour hat Shape (N, 1, 2) → auf (N, 2) reduzieren
        pts = contour.reshape(-1, 2).astype(np.float32)

        # Bogenmaßlänge berechnen (Summe der Segmentlängen)
        arc_len = float(cv2.arcLength(contour, closed=False))
        if arc_len < min_path_px:
            continue

        # Ramer-Douglas-Peucker Vereinfachung
        if simplify_eps > 0:
            epsilon = simplify_eps
            simplified = cv2.approxPolyDP(
                contour,
                epsilon=epsilon,
                closed=False,
            )
            pts = simplified.reshape(-1, 2).astype(np.float32)

        # Mindestens 2 Punkte benötigt
        if len(pts) < 2:
            continue

        paths.append(pts)

    logger.debug(
        "Nach Filter (min_px=%d) und Vereinfachung (eps=%.1f): %d Pfade",
        min_path_px,
        simplify_eps,
        len(paths),
    )
    return paths
