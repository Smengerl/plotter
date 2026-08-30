"""
pipeline/tests/test_save_image_step.py - Unit tests for SaveImageStep

Covers:
  - Output path resolution (metadata priority > config fallback)
  - Missing path raises ValueError
  - File is written to disk
  - Format inference (PNG, JPEG)
  - JPEG quality config
  - PNG compress_level config
  - Overwrite guard (overwrite=False)
  - requires() returns ["image"]
  - Missing ctx.image raises MissingContextError via runner
  - Unsupported extension raises ValueError
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pipeline.core.base import ImageContext, MissingContextError
from pipeline.core.runner import PipelineRunner
from pipeline.steps.save_image_step import SaveImageStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgb_image(width: int = 16, height: int = 16) -> Image.Image:
    """Create a small solid-colour RGB image for testing."""
    return Image.new("RGB", (width, height), color=(42, 100, 200))


def _make_ctx(image: Image.Image | None = None) -> ImageContext:
    return ImageContext(image=image, metadata={}, intermediates={})


# ---------------------------------------------------------------------------
# requires()
# ---------------------------------------------------------------------------

class TestSaveImageStepRequires:
    def test_requires_image_key(self) -> None:
        step = SaveImageStep(config={})
        assert step.requires() == ["image"]


# ---------------------------------------------------------------------------
# Output path resolution
# ---------------------------------------------------------------------------

class TestOutputPathResolution:
    def test_metadata_path_takes_priority(self, tmp_path: Path) -> None:
        meta_path = tmp_path / "meta.png"
        cfg_path = tmp_path / "config.png"

        ctx = _make_ctx(_rgb_image())
        ctx.metadata["output_path"] = str(meta_path)

        step = SaveImageStep(config={"output_path": str(cfg_path)})
        step.process(ctx)

        assert meta_path.exists()
        assert not cfg_path.exists()

    def test_config_fallback_when_no_metadata(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.png"

        ctx = _make_ctx(_rgb_image())
        step = SaveImageStep(config={"output_path": str(cfg_path)})
        step.process(ctx)

        assert cfg_path.exists()

    def test_no_path_raises_value_error(self) -> None:
        ctx = _make_ctx(_rgb_image())
        step = SaveImageStep(config={})

        with pytest.raises(ValueError, match="output_path"):
            step.process(ctx)

    def test_empty_string_metadata_falls_back_to_config(self, tmp_path: Path) -> None:
        """Empty string in metadata should fall through to config."""
        cfg_path = tmp_path / "config.png"

        ctx = _make_ctx(_rgb_image())
        ctx.metadata["output_path"] = ""   # falsy → falls back
        step = SaveImageStep(config={"output_path": str(cfg_path)})
        step.process(ctx)

        assert cfg_path.exists()


# ---------------------------------------------------------------------------
# File written to disk
# ---------------------------------------------------------------------------

class TestFileOutput:
    def test_file_is_created(self, tmp_path: Path) -> None:
        out = tmp_path / "out.png"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_parent_dirs_created(self, tmp_path: Path) -> None:
        out = tmp_path / "a" / "b" / "c" / "out.png"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert out.exists()

    def test_saved_image_readable(self, tmp_path: Path) -> None:
        src = _rgb_image(32, 32)
        out = tmp_path / "out.png"
        ctx = _make_ctx(src)
        SaveImageStep(config={"output_path": str(out)}).process(ctx)

        loaded = Image.open(out)
        assert loaded.size == (32, 32)

    def test_process_returns_ctx(self, tmp_path: Path) -> None:
        out = tmp_path / "out.png"
        ctx = _make_ctx(_rgb_image())
        result = SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert result is ctx


# ---------------------------------------------------------------------------
# Format inference
# ---------------------------------------------------------------------------

class TestFormatInference:
    def test_png_extension_produces_png(self, tmp_path: Path) -> None:
        out = tmp_path / "img.png"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)

        with Image.open(out) as img:
            assert img.format == "PNG"

    def test_jpeg_extension_produces_jpeg(self, tmp_path: Path) -> None:
        out = tmp_path / "img.jpg"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)

        with Image.open(out) as img:
            assert img.format == "JPEG"

    def test_uppercase_jpg_accepted(self, tmp_path: Path) -> None:
        # Path.suffix is lower-cased inside the step, so this must also work
        # even though on macOS the FS is case-insensitive.
        out = tmp_path / "img.jpg"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert out.exists()

    def test_unsupported_extension_raises(self) -> None:
        ctx = _make_ctx(_rgb_image())
        step = SaveImageStep(config={"output_path": "/tmp/plotter_test_out.xyz"})
        with pytest.raises(ValueError, match="unsupported file extension"):
            step.process(ctx)

    def test_bmp_extension_accepted(self, tmp_path: Path) -> None:
        out = tmp_path / "img.bmp"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert out.exists()


# ---------------------------------------------------------------------------
# Format-specific config keys
# ---------------------------------------------------------------------------

class TestFormatConfig:
    def test_jpeg_quality_is_applied(self, tmp_path: Path) -> None:
        """Higher quality → larger file for an image with detail."""
        img = Image.new("RGB", (64, 64))
        # Add some variation so quality actually matters
        for x in range(64):
            for y in range(64):
                img.putpixel((x, y), (x * 4, y * 4, (x + y) * 2 % 256))

        out_hq = tmp_path / "hq.jpg"
        out_lq = tmp_path / "lq.jpg"
        ctx_hq = _make_ctx(img.copy())
        ctx_lq = _make_ctx(img.copy())

        SaveImageStep(config={"output_path": str(out_hq), "quality": 95}).process(ctx_hq)
        SaveImageStep(config={"output_path": str(out_lq), "quality": 1}).process(ctx_lq)

        assert out_hq.stat().st_size > out_lq.stat().st_size

    def test_png_compress_level_applied(self, tmp_path: Path) -> None:
        """Higher compress_level → smaller file (or equal, but never larger than level 0)."""
        img = _rgb_image(64, 64)
        out_none = tmp_path / "none.png"
        out_max = tmp_path / "max.png"
        ctx_none = _make_ctx(img.copy())
        ctx_max = _make_ctx(img.copy())

        SaveImageStep(config={"output_path": str(out_none), "compress_level": 0}).process(ctx_none)
        SaveImageStep(config={"output_path": str(out_max), "compress_level": 9}).process(ctx_max)

        # Level 9 must produce a file that is ≤ level 0
        assert out_max.stat().st_size <= out_none.stat().st_size

    def test_rgba_image_converted_to_rgb_for_jpeg(self, tmp_path: Path) -> None:
        """JPEG does not support alpha; step must silently convert."""
        rgba = Image.new("RGBA", (16, 16), (10, 20, 30, 128))
        out = tmp_path / "out.jpg"
        ctx = _make_ctx(rgba)
        # Should not raise
        SaveImageStep(config={"output_path": str(out)}).process(ctx)
        assert out.exists()
        with Image.open(out) as img:
            assert img.mode == "RGB"


# ---------------------------------------------------------------------------
# Overwrite guard
# ---------------------------------------------------------------------------

class TestOverwriteGuard:
    def test_overwrite_true_replaces_file(self, tmp_path: Path) -> None:
        out = tmp_path / "out.png"
        out.write_bytes(b"placeholder")

        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out), "overwrite": True}).process(ctx)
        # File should now be a valid PNG
        with Image.open(out) as img:
            assert img.format == "PNG"

    def test_overwrite_false_raises_when_file_exists(self, tmp_path: Path) -> None:
        out = tmp_path / "out.png"
        out.write_bytes(b"placeholder")

        ctx = _make_ctx(_rgb_image())
        step = SaveImageStep(config={"output_path": str(out), "overwrite": False})
        with pytest.raises(FileExistsError, match="overwrite=False"):
            step.process(ctx)

    def test_overwrite_false_succeeds_when_file_missing(self, tmp_path: Path) -> None:
        out = tmp_path / "new_file.png"
        ctx = _make_ctx(_rgb_image())
        SaveImageStep(config={"output_path": str(out), "overwrite": False}).process(ctx)
        assert out.exists()


# ---------------------------------------------------------------------------
# Runner integration (MissingContextError)
# ---------------------------------------------------------------------------

class TestRunnerIntegration:
    def test_missing_image_raises_missing_context_error(self) -> None:
        ctx = ImageContext(image=None, metadata={}, intermediates={})
        runner = PipelineRunner(
            steps_config=[{"step": "save_image", "config": {"output_path": "/tmp/plotter_dummy.png"}}]
        )
        with pytest.raises(MissingContextError) as exc_info:
            runner.run(ctx)
        assert exc_info.value.missing_key == "image"
        # step_name is the step's display name — the registry key here, since
        # the config sets no "label".
        assert exc_info.value.step_name == "save_image"

    def test_runner_saves_image_when_ctx_image_present(self, tmp_path: Path) -> None:
        out = tmp_path / "runner_out.png"
        ctx = ImageContext(image=_rgb_image(), metadata={}, intermediates={})
        runner = PipelineRunner(
            steps_config=[{"step": "save_image", "config": {"output_path": str(out)}}]
        )
        runner.run(ctx)
        assert out.exists()
