"""
pipeline/tests/test_legacy_compat.py - Integration tests of native pipeline steps

Checks that native steps (StyliseCannyStep → VectorizeStep → GCodeGenStep)
produce correct outputs for a real test image:

    binary      - Binary image after stylization    (numpy array, correct format)
    paths       - Path list after vectorization     (count and coordinates)
    gcode_lines - GCode lines                       (drawing content, no comments)

No mocking - real step calls, real test image.

Usage:
    cd plotter
    pytest pipeline/tests/test_legacy_compat.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

# pipeline/tests/ → pipeline/ → repo-root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner
from pipeline.steps.send_gcode_step import _filter_gcode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TESTIMAGE = _REPO_ROOT / "pipeline" / "tests" / "testimage.png"

# Canny defaults - identical to legacy_compat.yaml
_STYLE_CONFIG: dict = dict(
    style="canny",
    style_res=1024,
    canny_low=50,
    canny_high=150,
    canny_blur=3,
)
_VECTORISE_CONFIG: dict = dict(min_path_px=10, simplify_eps=1.5)
_GCODE_CONFIG: dict = dict(
    target_width_mm=180.0,
    target_height_mm=250.0,
    origin_x=5.0,
    origin_y=5.0,
    keep_aspect=True,
    feedrate_draw=1500,
    feedrate_travel=3000,
    pen_down_cmd="M3 S1000",
    pen_up_cmd="M5",
    pen_delay_ms=100,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def testimage_path() -> Path:
    if not _TESTIMAGE.exists():
        pytest.skip(f"Testbild nicht gefunden: {_TESTIMAGE}")
    return _TESTIMAGE


@pytest.fixture(scope="module")
def pipeline_outputs(testimage_path: Path) -> dict:
    """Executes the native steps via PipelineRunner and collects outputs."""
    steps_config = [
        {"step": "stylise_canny", "config": {**_STYLE_CONFIG, "source_path": testimage_path}},
        {"step": "vectorise",     "config": _VECTORISE_CONFIG},
        {"step": "gcode_gen",     "config": _GCODE_CONFIG},
    ]
    runner = PipelineRunner(steps_config)

    ctx = ImageContext(
        image=Image.open(testimage_path).convert("RGB"),
        metadata={"source_path": testimage_path},
    )
    ctx = runner.run(ctx)

    return {
        "binary":      ctx.intermediates["binary"],
        "paths":       ctx.intermediates["paths"],
        "gcode_lines": ctx.intermediates["gcode_lines"],
    }


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _executable_lines(gcode_lines: list[str]) -> list[str]:
    """Returns only executable GCode lines (no blank lines, no comments)."""
    return list(_filter_gcode(gcode_lines))


# ---------------------------------------------------------------------------
# Tests: Stylization
# ---------------------------------------------------------------------------

class TestStyliseStep:

    def test_binary_is_numpy_array(self, pipeline_outputs: dict) -> None:
        """Stylization produces a numpy array."""
        binary = pipeline_outputs["binary"]
        assert isinstance(binary, np.ndarray)

    def test_binary_is_2d(self, pipeline_outputs: dict) -> None:
        """Binary image is 2-dimensional (grayscale)."""
        binary = pipeline_outputs["binary"]
        assert binary.ndim == 2, f"Expected 2D, got: {binary.shape}"

    def test_binary_dtype_uint8(self, pipeline_outputs: dict) -> None:
        """Binary image has dtype uint8."""
        binary = pipeline_outputs["binary"]
        assert binary.dtype == np.uint8

    def test_binary_has_nonzero_pixels(self, pipeline_outputs: dict) -> None:
        """Binary image contains white pixels (edges were detected)."""
        binary = pipeline_outputs["binary"]
        assert np.any(binary > 0), "Binary image is completely black — no edges detected"

    def test_binary_has_background_pixels(self, pipeline_outputs: dict) -> None:
        """Binary image contains black pixels (not completely white)."""
        binary = pipeline_outputs["binary"]
        assert np.any(binary == 0), "Binary image is completely white"


# ---------------------------------------------------------------------------
# Tests: Vectorization
# ---------------------------------------------------------------------------

class TestVectoriseStep:

    def test_paths_is_list(self, pipeline_outputs: dict) -> None:
        """Vectorization produces a list."""
        assert isinstance(pipeline_outputs["paths"], list)

    def test_paths_not_empty(self, pipeline_outputs: dict) -> None:
        """At least one path was extracted."""
        assert len(pipeline_outputs["paths"]) > 0, "No paths — vectorization failed"

    def test_each_path_is_numpy_array(self, pipeline_outputs: dict) -> None:
        """Each path is a numpy array."""
        for i, path in enumerate(pipeline_outputs["paths"]):
            assert isinstance(path, np.ndarray), f"Path {i} is not a numpy array"

    def test_each_path_has_min_2_points(self, pipeline_outputs: dict) -> None:
        """Each path has at least 2 points."""
        for i, path in enumerate(pipeline_outputs["paths"]):
            assert len(path) >= 2, f"Path {i} has fewer than 2 points: {len(path)}"

    def test_each_path_is_2d_coordinates(self, pipeline_outputs: dict) -> None:
        """Each path has shape (N, 2) — X/Y coordinates."""
        for i, path in enumerate(pipeline_outputs["paths"]):
            assert path.ndim == 2 and path.shape[1] == 2, (
                f"Path {i} has incorrect shape: {path.shape}"
            )


# ---------------------------------------------------------------------------
# Tests: GCode Generation
# ---------------------------------------------------------------------------

class TestGCodeGenStep:

    def test_gcode_lines_is_list(self, pipeline_outputs: dict) -> None:
        """GCode output is a list."""
        assert isinstance(pipeline_outputs["gcode_lines"], list)

    def test_gcode_not_empty(self, pipeline_outputs: dict) -> None:
        """GCode output contains lines."""
        assert len(pipeline_outputs["gcode_lines"]) > 0

    def test_gcode_contains_g21(self, pipeline_outputs: dict) -> None:
        """GCode contains G21 (unit mm)."""
        joined = "\n".join(pipeline_outputs["gcode_lines"])
        assert "G21" in joined

    def test_gcode_contains_g90(self, pipeline_outputs: dict) -> None:
        """GCode contains G90 (absolute coordinates)."""
        joined = "\n".join(pipeline_outputs["gcode_lines"])
        assert "G90" in joined

    def test_gcode_contains_pen_down(self, pipeline_outputs: dict) -> None:
        """GCode contains the pen-down command."""
        joined = "\n".join(pipeline_outputs["gcode_lines"])
        assert _GCODE_CONFIG["pen_down_cmd"] in joined

    def test_gcode_contains_pen_up(self, pipeline_outputs: dict) -> None:
        """GCode contains the pen-up command."""
        joined = "\n".join(pipeline_outputs["gcode_lines"])
        assert _GCODE_CONFIG["pen_up_cmd"] in joined

    def test_executable_lines_present(self, pipeline_outputs: dict) -> None:
        """After filtering, there are executable GCode lines."""
        exec_lines = _executable_lines(pipeline_outputs["gcode_lines"])
        assert len(exec_lines) > 0


# ---------------------------------------------------------------------------
# Tests: Pipeline via PipelineRunner (End-to-End)
# ---------------------------------------------------------------------------

class TestPipelineRunner:

    def test_runner_produces_all_intermediates(self, pipeline_outputs: dict) -> None:
        """PipelineRunner produces all expected intermediate values."""
        assert "binary"      in pipeline_outputs
        assert "paths"       in pipeline_outputs
        assert "gcode_lines" in pipeline_outputs

    def test_pipeline_is_deterministic(self, testimage_path: Path) -> None:
        """Running the pipeline twice produces identical results."""
        steps_config = [
            {"step": "stylise_canny", "config": {**_STYLE_CONFIG, "source_path": testimage_path}},
            {"step": "vectorise",     "config": _VECTORISE_CONFIG},
            {"step": "gcode_gen",     "config": _GCODE_CONFIG},
        ]

        def _run() -> dict:
            runner = PipelineRunner(steps_config)
            ctx = ImageContext(
                image=Image.open(testimage_path).convert("RGB"),
                metadata={"source_path": testimage_path},
            )
            ctx = runner.run(ctx)
            return {
                "binary":      ctx.intermediates["binary"],
                "paths":       ctx.intermediates["paths"],
                "gcode_lines": ctx.intermediates["gcode_lines"],
            }

        out1 = _run()
        out2 = _run()

        np.testing.assert_array_equal(
            out1["binary"], out2["binary"],
            err_msg="Binary image is not deterministic",
        )
        assert len(out1["paths"]) == len(out2["paths"]), "Path count is not deterministic"
        assert out1["gcode_lines"] == out2["gcode_lines"], "GCode is not deterministic"
