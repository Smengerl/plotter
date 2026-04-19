"""
pipeline/steps/gcode_from_svg_step.py - GCode generation via vpype-gcode-compatible TOML profiles

This step replaces ``GCodeGenStep`` and generates GCode from vectorized paths
using a TOML-based profile system fully compatible with vpype-gcode format.

Concept
-------
1.  Pixel paths from ``ctx.intermediates["paths"]`` are converted to a
    ``vpype.Document``.
2.  The document is transformed to GCode using ``vpype_cli.execute()`` with
    a TOML profile (vpype + vpype-gcode pipeline).
3.  Generated GCode lines are written to ``ctx.intermediates["gcode_lines"]``.

Requirements
------------
vpype 1.15.x, vpype-gcode 0.13.x, Python 3.11-3.13

Data Transport via ImageContext
--------------------------------
Reads  ctx.intermediates["paths"]        - PathList (N x 2 float32-arrays)
       ctx.intermediates["binary"]       - uint8-array (H, W); provides page_size
       ctx.intermediates["image_shape"]  - (H, W) fallback if "binary" missing
Writes ctx.intermediates["gcode_lines"] - List of GCode lines (str)

Config Keys
-----------
profile         str     Profile name from TOML file  (default: "grbl_a4_pen")
toml_path       str     Path to TOML profile file.
                        If None -> internal default profile is used.
target_width_mm float   Drawing width in mm  (default: 190.0 = A4 - 2x5mm margins)
target_height_mm float  Drawing height in mm    (default: 277.0 = A4 - 2x10mm margins)
keep_aspect     bool    Maintain aspect ratio  (default: True)
linesort        bool    Optimize path order by travel distance  (default: True)
"""

from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.steps.vectorize_step import paths_to_svg

logger = logging.getLogger(__name__)

# Path to built-in default profile (located in configs/ subdirectory)
_DEFAULT_TOML = Path(__file__).parent.parent / "configs" / "grbl_a4_pen.toml"

# CSS pixels per unit (as vpype internally calculates: 1 px = 1/96 inch)
_PX_PER_MM = 96.0 / 25.4   # approximately 3.7795 px/mm
_MM_PER_PX = 25.4 / 96.0   # approximately 0.26458 mm/px

# ---------------------------------------------------------------------------
# TOML Loader (stdlib tomllib, Python 3.11+)
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file using Python 3.11+ ``tomllib``."""
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Linesort - Simple nearest-neighbor optimization for path ordering
# ---------------------------------------------------------------------------

def _linesort(
    paths: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Sort paths using nearest-neighbor heuristic.

    Minimizes the sum of travel distances between paths. Each path can be
    traversed forwards or backwards (bidirectional search).
    """
    if len(paths) <= 1:
        return paths

    remaining = list(paths)
    result: list[list[tuple[float, float]]] = []
    current_pos = (0.0, 0.0)

    while remaining:
        best_idx = 0
        best_dist = math.inf
        best_reversed = False

        for i, path in enumerate(remaining):
            d_fwd = math.dist(current_pos, path[0])
            d_bwd = math.dist(current_pos, path[-1])

            if d_fwd < best_dist:
                best_dist = d_fwd
                best_idx = i
                best_reversed = False
            if d_bwd < best_dist:
                best_dist = d_bwd
                best_idx = i
                best_reversed = True

        chosen = remaining.pop(best_idx)
        if best_reversed:
            chosen = list(reversed(chosen))
        result.append(chosen)
        current_pos = chosen[-1]

    return result


# ---------------------------------------------------------------------------
# GCode Generation via vpype + vpype-gcode
# ---------------------------------------------------------------------------

def _generate_gcode_vpype(
    paths: list[list[tuple[float, float]]],
    page_size_px: tuple[float, float],
    toml_path: Path,
    profile_name: str,
) -> str:
    """Generate GCode using vpype + vpype-gcode pipeline.

    Args:
        paths:         Scaled paths as (x, y) pixel coordinate lists
        page_size_px:  (W, H) of drawing area in CSS pixels
        toml_path:     Path to TOML profile file
        profile_name:  Name of profile in TOML file

    Returns:
        GCode as string
    """
    import vpype as vp
    import vpype_cli

    # Load TOML profile into vpype's ConfigManager
    vp.config_manager.load_config_file(str(toml_path))

    # vpype Document aufbauen
    doc = vp.Document()
    doc.page_size = page_size_px

    if paths:
        lc = vp.LineCollection()
        for path in paths:
            # Coordinates as Python complex numbers: x + y*j
            line = [pt[0] + pt[1] * 1j for pt in path]
            lc.append(line)
        doc.add(lc, layer_id=1)

    # Write GCode to temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".gcode", delete=False, encoding="utf-8"
    ) as f:
        tmp_path = Path(f.name)

    try:
        vpype_cli.execute(
            f"gwrite -p {profile_name} {tmp_path}",
            document=doc,
        )
        return tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# PipelineStep
# ---------------------------------------------------------------------------

class GCodeFromSvgStep(PipelineStep):
    """GCode generation via vpype-gcode-compatible TOML profiles.

    This step is the successor to ``GCodeGenStep`` and uses a flexible,
    TOML-based profile system instead of hardcoded parameters.

    Uses native vpype + vpype-gcode pipeline.

    Input
    -----
    ctx.intermediates["paths"]        PathList from VectorizeStep
    ctx.intermediates["binary"]       uint8-array - provides image size (optional)
    ctx.intermediates["image_shape"]  (H, W) fallback if "binary" missing (optional)
    ctx.image                         PIL image - final fallback for image size

    Output
    ------
    ctx.intermediates["gcode_lines"]  list[str] - GCode lines

    Config Keys    Type    Default             Meaning
    ------------------------------------------------------------------
    profile        str     "grbl_a4_pen"       Profile name in TOML file
    toml_path      str     None -> internal    Path to TOML profile file
                           default profile
    target_width_mm float  190.0               Drawing width in mm
    target_height_mm float 277.0               Drawing height in mm
    keep_aspect    bool    True                Maintain aspect ratio
    linesort       bool    True                Optimize path order
    """

    name = "gcode_from_svg"

    def requires(self) -> list[str]:
        return ["intermediates.paths"]

    def process(self, ctx: ImageContext) -> ImageContext:
        c = self.config
        paths: list[npt.NDArray[np.float32]] = ctx.intermediates["paths"]

        # --- Determine image size ---
        # Priority: intermediates["binary"] > intermediates["image_shape"] > ctx.image
        binary = ctx.intermediates.get("binary")
        if binary is not None:
            img_h, img_w = binary.shape[:2]
        elif "image_shape" in ctx.intermediates:
            img_h, img_w = ctx.intermediates["image_shape"]
        elif ctx.has_image:
            img_w, img_h = ctx.image.size
        else:
            raise ValueError(
                "GCodeFromSvgStep: cannot determine image size. "
                "Ensure LoadImageStep runs before this step."
            )

        # --- Resolve TOML profile ---
        toml_path_cfg: str | None = c.get("toml_path", None)
        toml_path = Path(toml_path_cfg) if toml_path_cfg is not None else _DEFAULT_TOML
        profile_name: str = str(c.get("profile", "grbl_a4_pen"))

        # Check profile existence upfront
        toml_data = _load_toml(toml_path)
        gwrite_section = toml_data.get("gwrite", {})

        if profile_name not in gwrite_section:
            default_in_toml = gwrite_section.get("default_profile")
            if default_in_toml and default_in_toml in gwrite_section:
                logger.warning(
                    "Profile '%s' not found -- using default_profile '%s'",
                    profile_name, default_in_toml,
                )
                profile_name = default_in_toml
            else:
                available = [k for k in gwrite_section if k != "default_profile"]
                raise KeyError(
                    f"GCode profile '{profile_name}' not found in '{toml_path}'.  "
                    f"Available: {available}"
                )

        # --- Calculate target size and scaling ---
        target_width_mm: float = float(c.get("target_width_mm", 190.0))
        target_height_mm: float = float(c.get("target_height_mm", 277.0))
        keep_aspect: bool = bool(c.get("keep_aspect", True))

        if keep_aspect:
            scale = min(target_width_mm / img_w, target_height_mm / img_h)
            actual_w_mm = img_w * scale
            actual_h_mm = img_h * scale
        else:
            actual_w_mm = target_width_mm
            actual_h_mm = target_height_mm

        # Pfade skalieren: px-Koordinaten → CSS-Pixel (96dpi-Basis)
        # sodass 1 CSS-px = 1/96 Zoll = 0.2646 mm
        scale_to_css_x = actual_w_mm * _PX_PER_MM / img_w if img_w > 0 else 1.0
        scale_to_css_y = actual_h_mm * _PX_PER_MM / img_h if img_h > 0 else 1.0
        if keep_aspect:
            scale_to_css_x = scale_to_css_y = min(scale_to_css_x, scale_to_css_y)

        scaled_paths: list[list[tuple[float, float]]] = [
            [(float(pt[0]) * scale_to_css_x, float(pt[1]) * scale_to_css_y) for pt in path]
            for path in paths
            if len(path) >= 2
        ]

        svg_w_px = img_w * scale_to_css_x
        svg_h_px = img_h * scale_to_css_y

        # --- Optional linesort ---
        do_linesort: bool = bool(c.get("linesort", True))
        if do_linesort and scaled_paths:
            scaled_paths = _linesort(scaled_paths)
            logger.debug("GCodeFromSvgStep: linesort -> %d paths", len(scaled_paths))

        quiet: bool = bool(c.get("quiet", False))

        # --- Generate GCode ---
        gcode_str = _generate_gcode_vpype(
            paths=scaled_paths,
            page_size_px=(svg_w_px, svg_h_px),
            toml_path=toml_path,
            profile_name=profile_name,
        )

        gcode_lines = gcode_str.splitlines(keepends=False)

        logger.debug(
            "GCodeFromSvgStep: profile '%s', %d paths -> %d GCode lines",
            profile_name, len(scaled_paths), len(gcode_lines),
        )

        ctx.intermediates["gcode_lines"] = gcode_lines
        return ctx

