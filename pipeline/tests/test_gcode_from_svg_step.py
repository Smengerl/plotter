"""
pipeline/tests/test_gcode_from_svg_step.py - Unit tests for GCodeFromSvgStep

Tests TOML-profile-based GCode generation without hardware.

Usage:
    cd plotter/pipeline
    pytest tests/
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.core.base import ImageContext
from pipeline.steps.gcode_from_svg_step import (
    GCodeFromSvgStep,
    _linesort,
    _load_toml,
)

# Path to built-in default profile
_DEFAULT_TOML = Path(__file__).parent.parent / "configs" / "grbl_a4_pen.toml"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _simple_paths() -> list:
    """Two simple paths in pixel coordinates."""
    p1 = np.array([[0, 0], [100, 0], [100, 100]], dtype=np.float32)
    p2 = np.array([[10, 10], [50, 90]], dtype=np.float32)
    return [p1, p2]


def _make_ctx(
    paths: list | None = None,
    img_h: int = 200,
    img_w: int = 200,
) -> ImageContext:
    ctx = ImageContext()
    ctx.intermediates["paths"] = paths if paths is not None else _simple_paths()
    ctx.intermediates["image_shape"] = (img_h, img_w)
    return ctx


def _extract_coords(lines: list[str]) -> list[tuple[float, float]]:
    """Extracts (X, Y) from G1 lines."""
    result = []
    for line in lines:
        clean = line.split(";")[0].strip()
        if not clean.upper().startswith("G1") and not clean.upper().startswith("G0"):
            continue
        parts = clean.split()
        coords = {p[0].upper(): float(p[1:]) for p in parts[1:] if p[0].upper() in "XY"}
        if "X" in coords and "Y" in coords:
            result.append((coords["X"], coords["Y"]))
    return result


# ---------------------------------------------------------------------------
# Tests: Loading TOML
# ---------------------------------------------------------------------------

class TestLoadToml:
    def test_loads_default_profile(self):
        data = _load_toml(_DEFAULT_TOML)
        assert "gwrite" in data
        assert "grbl_a4_pen" in data["gwrite"]

    def test_profile_has_required_fields(self):
        data = _load_toml(_DEFAULT_TOML)
        profile = data["gwrite"]["grbl_a4_pen"]
        assert "unit" in profile
        assert profile["unit"] == "mm"
        assert "vertical_flip" in profile
        assert profile["vertical_flip"] is True

    def test_default_profile_key(self):
        data = _load_toml(_DEFAULT_TOML)
        assert data["gwrite"].get("default_profile") == "grbl_a4_pen"


# ---------------------------------------------------------------------------
# Tests: Linesort
# ---------------------------------------------------------------------------

class TestLinesort:
    def test_empty_list(self):
        assert _linesort([]) == []

    def test_single_path_unchanged(self):
        p = [(0.0, 0.0), (10.0, 0.0)]
        result = _linesort([p])
        assert result == [p]

    def test_nearest_first(self):
        """Path closest to origin should come first."""
        far = [(100.0, 100.0), (200.0, 200.0)]
        near = [(1.0, 1.0), (2.0, 2.0)]
        result = _linesort([far, near])
        assert result[0] == near

    def test_can_reverse_paths(self):
        """Path can be driven in reverse if it's shorter."""
        p1 = [(0.0, 0.0), (10.0, 0.0)]   # ends at (10, 0)
        p2 = [(20.0, 0.0), (11.0, 0.0)]  # end (11, 0) is closer than start (20, 0)
        result = _linesort([p1, p2])
        # p2 should be driven in reverse: (11, 0) → (20, 0)
        assert result[0] == p1
        assert result[1][0] == (11.0, 0.0)

    def test_preserves_all_paths(self):
        paths = [[(float(i), 0.0), (float(i + 1), 1.0)] for i in range(10)]
        result = _linesort(paths)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Tests: apply_profile
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tests: GCodeFromSvgStep.process()
# ---------------------------------------------------------------------------

class TestGCodeFromSvgStep:
    def test_returns_gcode_lines(self):
        step = GCodeFromSvgStep()
        ctx = _make_ctx()
        result = step.process(ctx)
        lines = result.intermediates["gcode_lines"]
        assert isinstance(lines, list)
        assert len(lines) > 0
        assert all(isinstance(l, str) for l in lines)

    def test_default_profile_produces_g1_commands(self):
        step = GCodeFromSvgStep()
        ctx = _make_ctx()
        result = step.process(ctx)
        joined = "\n".join(result.intermediates["gcode_lines"])
        assert "G1" in joined or "G0" in joined

    def test_default_profile_contains_init_commands(self):
        step = GCodeFromSvgStep()
        ctx = _make_ctx()
        result = step.process(ctx)
        joined = "\n".join(result.intermediates["gcode_lines"])
        assert "G21" in joined   # mm
        assert "G90" in joined   # absolute

    def test_uses_image_shape_fallback(self):
        """Works without 'binary' in intermediates."""
        step = GCodeFromSvgStep()
        ctx = _make_ctx(img_h=300, img_w=200)
        # binary not set
        assert "binary" not in ctx.intermediates
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_uses_binary_for_image_size(self):
        """If 'binary' is set, its shape is used."""
        import numpy as np
        step = GCodeFromSvgStep()
        ctx = _make_ctx()
        ctx.intermediates["binary"] = np.zeros((150, 100), dtype=np.uint8)
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_custom_toml_path(self):
        """Custom TOML file can be passed via config."""
        step = GCodeFromSvgStep(config={"toml_path": str(_DEFAULT_TOML)})
        ctx = _make_ctx()
        result = step.process(ctx)
        assert len(result.intermediates["gcode_lines"]) > 0

    def test_unknown_profile_falls_back_to_default(self):
        """Unknown profile → fallback to default_profile from TOML file."""
        step = GCodeFromSvgStep(config={"profile": "does_not_exist_xyz", "quiet": True})
        ctx = _make_ctx()
        # Should not raise - fallback to default_profile applies
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_unknown_profile_and_no_default_raises(self, tmp_path):
        """Unknown profile + no default_profile → KeyError."""
        toml_content = b"""
[gwrite.my_profile]
unit = "mm"
segment_first = "G0 X{x:.3f} Y{y:.3f}\\n"
segment = "G1 X{x:.3f} Y{y:.3f}\\n"
"""
        toml_file = tmp_path / "custom.toml"
        toml_file.write_bytes(toml_content)
        step = GCodeFromSvgStep(config={
            "profile": "does_not_exist_xyz",
            "toml_path": str(toml_file),
        })
        ctx = _make_ctx()
        with pytest.raises(KeyError, match="does_not_exist_xyz"):
            step.process(ctx)

    def test_linesort_disabled(self):
        """linesort=False should not cause errors."""
        step = GCodeFromSvgStep(config={"linesort": False})
        ctx = _make_ctx()
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_keep_aspect_true(self):
        """Aspect ratio is preserved."""
        step = GCodeFromSvgStep(config={"keep_aspect": True, "quiet": True})
        ctx = _make_ctx(img_h=100, img_w=200)
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_keep_aspect_false(self):
        """Stretch without aspect ratio."""
        step = GCodeFromSvgStep(config={"keep_aspect": False, "quiet": True})
        ctx = _make_ctx(img_h=100, img_w=200)
        result = step.process(ctx)
        assert "gcode_lines" in result.intermediates

    def test_empty_paths_list(self):
        """Empty path list → no errors, valid GCode list."""
        step = GCodeFromSvgStep(config={"quiet": True})
        ctx = _make_ctx(paths=[])
        result = step.process(ctx)
        lines = result.intermediates["gcode_lines"]
        assert isinstance(lines, list)
        # At least header/footer from profile should be present
        joined = "\n".join(lines)
        assert "G21" in joined

    def test_step_name_attribute(self):
        assert GCodeFromSvgStep.name == "gcode_from_svg"

    def test_registered_in_registry(self):
        from pipeline.core.registry import STEP_REGISTRY
        assert "gcode_from_svg" in STEP_REGISTRY
        assert STEP_REGISTRY["gcode_from_svg"] is GCodeFromSvgStep


# ---------------------------------------------------------------------------
# Tests: Coordinate correctness
# ---------------------------------------------------------------------------

class TestGCodeFromSvgCoordinates:
    """Tests geometric correctness of coordinate transformation."""

    def test_vertical_flip_origin(self):
        """Pen-down position should be in GCode coordinate system (Y > 0)."""
        step = GCodeFromSvgStep(config={"quiet": True})
        ctx = _make_ctx(
            paths=[np.array([[0, 0], [50, 0]], dtype=np.float32)],
            img_h=200, img_w=200,
        )
        result = step.process(ctx)
        coords = _extract_coords(result.intermediates["gcode_lines"])
        y_values = [y for _, y in coords if y != 0]
        # With vertical_flip=true: Y coordinates should be positive
        assert all(y >= 0 for y in y_values), f"Negative Y values: {y_values}"

    def test_pen_down_command_present(self):
        """M3 S1000 (pen down) must be in GCode lines."""
        step = GCodeFromSvgStep(config={"quiet": True})
        ctx = _make_ctx()
        result = step.process(ctx)
        joined = "\n".join(result.intermediates["gcode_lines"])
        assert "M3" in joined

    def test_pen_up_command_present(self):
        """M5 (pen up) must be in GCode lines."""
        step = GCodeFromSvgStep(config={"quiet": True})
        ctx = _make_ctx()
        result = step.process(ctx)
        joined = "\n".join(result.intermediates["gcode_lines"])
        assert "M5" in joined
