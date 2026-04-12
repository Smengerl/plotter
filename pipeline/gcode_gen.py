"""
pipeline/gcode_gen.py — Schritt 3: Pfade → GRBL-GCode

Koordinaten-Transformation:
  Bild-Koordinatensystem:  Ursprung oben-links, Y nach unten
  Plotter-Koordinaten:     Ursprung unten-links, Y nach oben (Standard-GCode)

  → Y wird gespiegelt: y_mm = origin_y + scale * (img_height - py)
  → X läuft normal:    x_mm = origin_x + scale * px

Skalierung mit Seitenverhältnis-Erhalt:
  scale = min(target_width / img_width, target_height / img_height)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt
    from pipeline.vectorise import PathList

logger = logging.getLogger(__name__)


def generate_gcode(
    paths: "PathList",
    image_shape: tuple[int, int],          # (height, width) in Pixeln
    target_width_mm: float = 180.0,
    target_height_mm: float = 250.0,
    origin_x: float = 5.0,
    origin_y: float = 5.0,
    keep_aspect: bool = True,
    feedrate_draw: int = 1500,
    feedrate_travel: int = 3000,
    pen_down_cmd: str = "M3 S1000",
    pen_up_cmd: str = "M5",
    pen_delay_ms: int = 100,
) -> list[str]:
    """
    Generiert eine Liste von GCode-Zeilen für alle übergebenen Pfade.

    Parameters
    ----------
    paths            : Liste von (N, 2)-Arrays mit Pixel-Koordinaten (x, y)
    image_shape      : (H, W) des Quellbildes in Pixeln
    target_width_mm  : Maximale Zeichenbreite in mm
    target_height_mm : Maximale Zeichenhöhe in mm
    origin_x/y       : Versatz des Zeichenbereichs in mm (linke untere Ecke)
    keep_aspect      : True → Seitenverhältnis beibehalten
    feedrate_draw    : Vorschub beim Zeichnen (mm/min)
    feedrate_travel  : Vorschub beim Verfahren (mm/min)
    pen_down_cmd     : GRBL-Befehl für Stift-runter
    pen_up_cmd       : GRBL-Befehl für Stift-hoch
    pen_delay_ms     : Wartezeit nach Pen-Down in ms (GCode: G4 Pxxx)

    Returns
    -------
    lines : Liste von GCode-Zeilen (ohne abschließendes \\n)
    """
    img_h, img_w = image_shape

    # Skalierungsfaktor (px → mm)
    if keep_aspect:
        scale_uniform = min(target_width_mm / img_w, target_height_mm / img_h)
        scale_x = scale_uniform
        scale_y = scale_uniform
        actual_w = img_w * scale_uniform
        actual_h = img_h * scale_uniform
    else:
        scale_x = target_width_mm / img_w
        scale_y = target_height_mm / img_h
        actual_w = target_width_mm
        actual_h = target_height_mm

    def px_to_mm(px: float, py: float) -> tuple[float, float]:
        """Pixel-Koordinaten → Plotter-Koordinaten in mm."""
        x_mm = origin_x + px * scale_x
        # Y-Spiegelung: Bild-Ursprung oben-links, Plotter unten-links
        y_mm = origin_y + (img_h - py) * scale_y
        return round(x_mm, 3), round(y_mm, 3)

    logger.debug(
        "GCode: Bild %dx%d px → Zeichenbereich %.1f×%.1f mm  (origin %.1f,%.1f mm)",
        img_w, img_h, actual_w, actual_h, origin_x, origin_y,
    )

    lines: list[str] = []

    # ---------- Kopfzeile / Initialisierung ----------
    lines.append("; GCode generiert von img2gcode")
    lines.append(f"; Bild: {img_w}x{img_h}px  →  {actual_w:.1f}x{actual_h:.1f}mm")
    lines.append(f"; Pfade: {len(paths)}")
    lines.append(f"; Feedrate Zeichnen: {feedrate_draw} mm/min")
    lines.append(f"; Feedrate Verfahren: {feedrate_travel} mm/min")
    lines.append("")
    lines.append("G21         ; Maßeinheit mm")
    lines.append("G90         ; Absolute Koordinaten")
    lines.append(f"G1 F{feedrate_travel}  ; Reisegeschwindigkeit")
    lines.append(pen_up_cmd + "  ; Stift hoch (Initialisierung)")
    lines.append("")

    # ---------- Homing / Startposition ----------
    lines.append(f"G1 X{origin_x:.3f} Y{origin_y:.3f}  ; Startposition")
    lines.append("")

    # ---------- Pfade zeichnen ----------
    total_moves = 0
    for path_idx, path in enumerate(paths):
        if len(path) < 2:
            continue

        # Erste Position anfahren (Stift hoch)
        x0, y0 = px_to_mm(float(path[0][0]), float(path[0][1]))
        lines.append(f"; Pfad {path_idx + 1}/{len(paths)}")
        lines.append(f"G1 X{x0:.3f} Y{y0:.3f} F{feedrate_travel}  ; Verfahren")

        # Stift runter + kurze Wartezeit
        lines.append(pen_down_cmd)
        if pen_delay_ms > 0:
            lines.append(f"G4 P{pen_delay_ms}  ; Warten auf Stift")
        lines.append(f"G1 F{feedrate_draw}")

        # Alle weiteren Punkte des Pfades
        for pt in path[1:]:
            x, y = px_to_mm(float(pt[0]), float(pt[1]))
            lines.append(f"G1 X{x:.3f} Y{y:.3f}")
            total_moves += 1

        # Stift hoch nach Pfad-Ende
        lines.append(pen_up_cmd)
        lines.append("")

    # ---------- Abschluss ----------
    lines.append("; Fertig — Stift hoch und zurück zur Ausgangsposition")
    lines.append(pen_up_cmd)
    lines.append(f"G1 X{origin_x:.3f} Y{origin_y + actual_h:.3f} F{feedrate_travel}  ; Papier vorschub")
    lines.append("")

    logger.debug("GCode: %d Zeilen, %d Zeichenbewegungen", len(lines), total_moves)
    return lines
