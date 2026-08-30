"""
pipeline/steps/vectorize_step.py - Native implementation of vectorization step

Implements the same logic as pipeline.vectorise.vectorise directly
as a PipelineStep - without the legacy wrapper detour.

Config interface is identical to VectoriseStep in legacy_steps.py:

    config keys       Default  Meaning
    -----------------------------------------------
    min_path_px       10       Minimum path length in pixels (arc length);
                               shorter contours are discarded
    simplify_eps      1.5      Tolerance for Ramer-Douglas-Peucker in pixels;
                               0 = no simplification
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from pipeline.core.base import ImageContext, PipelineStep

logger = logging.getLogger(__name__)

# Type alias - identical to pipeline.vectorise.PathList
PathList = list[npt.NDArray[np.float32]]


class VectorizeStep(PipelineStep):
    """
    Native vectorization step.

    Extracts connected contours from an image and writes the resulting
    path list to ``ctx.intermediates["paths"]``.

    Input image resolution (in order of priority):
    1. ``ctx.intermediates["binary"]`` — uint8 (H, W) array written by a
       preceding stylizer (255 = line, 0 = background).
    2. ``ctx.image``                   — PIL image; converted to a binary
       array automatically (grayscale threshold 128).  This allows
       ``VectorizeStep`` to be used directly after ``LoadImageStep``
       without any stylizer in between.

    Algorithm
    ---------
    1. ``cv2.findContours`` - external + internal contours (RETR_LIST)
    2. Arc length filter     - contours shorter than ``min_path_px`` are discarded
    3. RDP simplification    - ``cv2.approxPolyDP`` with tolerance ``simplify_eps``
    4. Minimum points filter - paths with < 2 points are discarded

    config keys       Default  Corresponds to CLI flag
    ------------------------------------------------
    min_path_px       10       --min-path-px
    simplify_eps      1.5      --simplify-eps
    binary_threshold  128      Grayscale threshold when binarizing ctx.image
                               (only used when no intermediates["binary"] present)
    """

    name = "Vectorize"

    def requires(self) -> list[str]:
        return ["image"]

    def process(self, ctx: ImageContext) -> ImageContext:
        min_path_px = self.config.get("min_path_px", 10)
        simplify_eps = self.config.get("simplify_eps", 1.5)
        logger.info("VectorizeStep — min_path_px=%s, simplify_eps=%s",
                     min_path_px, simplify_eps)

        # --- Resolve binary input ---
        binary: npt.NDArray[np.uint8] | None = ctx.intermediates.get("binary")
        if binary is None:
            # No stylizer in the pipeline — binarize ctx.image directly.
            if not ctx.has_image:
                raise ValueError(
                    "VectorizeStep: ctx.image is None and no intermediates['binary'] set. "
                    "Add LoadImageStep (or a stylizer) before VectorizeStep."
                )
            threshold: int = int(self.config.get("binary_threshold", 128))
            gray = np.array(ctx.image.convert("L"))
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            binary = binary.astype(np.uint8)
            logger.debug(
                "VectorizeStep: no intermediates['binary'] — binarized ctx.image "
                "(threshold=%d, shape=%dx%d)",
                threshold, binary.shape[1], binary.shape[0],
            )

        min_path_px: int = int(self.config.get("min_path_px", 10))
        simplify_eps: float = float(self.config.get("simplify_eps", 1.5))

        # Step 1: Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        logger.debug("cv2.findContours: %d raw contours found", len(contours))

        paths: PathList = []

        for contour in contours:
            # Calculate arc length - contour has shape (N, 1, 2)
            arc_len = float(cv2.arcLength(contour, closed=False))

            # Step 2: Length filter
            if arc_len < min_path_px:
                continue

            # Step 3: Ramer-Douglas-Peucker simplification
            if simplify_eps > 0:
                simplified = cv2.approxPolyDP(contour, epsilon=simplify_eps, closed=False)
                pts = simplified.reshape(-1, 2).astype(np.float32)
            else:
                pts = contour.reshape(-1, 2).astype(np.float32)

            # Step 4: At least 2 points required
            if len(pts) < 2:
                continue

            paths.append(pts)

        logger.debug(
            "VectorizeStep: %d paths (min_px=%d, eps=%.1f)",
            len(paths), min_path_px, simplify_eps,
        )

        ctx.intermediates["paths"] = paths
        return ctx


# ---------------------------------------------------------------------------
# Helper function (formerly pipeline.vectorise.paths_to_svg)
# ---------------------------------------------------------------------------

def paths_to_svg(
    paths: "PathList",
    image_shape: tuple[int, int],
    output_path: Path,
) -> None:
    """Writes the extracted pixel paths as SVG file.

    Args:
        paths: Paths from ``VectorizeStep`` (list of (N, 2) arrays)
        image_shape: ``(H, W)`` of source image - used as SVG viewport
        output_path: Target file (``.svg``)
    """
    h, w = image_shape
    svg_lines: list[str] = []
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                     f'viewBox="0 0 {w} {h}">')
    svg_lines.append(f'  <rect width="{w}" height="{h}" fill="white"/>')

    for path in paths:
        if len(path) < 2:
            continue
        coords = " ".join(f"{pt[0]:.1f},{pt[1]:.1f}" for pt in path)
        svg_lines.append(f'  <polyline points="{coords}" '
                         f'fill="none" stroke="black" stroke-width="1"/>')

    svg_lines.append("</svg>")
    Path(output_path).write_text("\n".join(svg_lines), encoding="utf-8")
