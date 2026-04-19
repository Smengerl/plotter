"""
pipeline/tests/test_load_image_step.py - Unit tests for LoadImageStep

Tests:
  - requires() declares metadata.source_path
  - ctx.image is populated as PIL RGB after process()
  - ctx.metadata["source_shape"] is set correctly
  - gray is NOT pre-computed into intermediates
  - style_res scales the image
  - Missing file raises FileNotFoundError
  - Stylizers can be chained via ctx.image (integration smoke test)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.core.base import ImageContext
from pipeline.steps.load_image_step import LoadImageStep

_TESTIMAGE = _REPO_ROOT / "pipeline" / "tests" / "testimage.png"


def _ctx_with_source(path: Path) -> ImageContext:
    return ImageContext(metadata={"source_path": path})


# ---------------------------------------------------------------------------
# Tests: LoadImageStep
# ---------------------------------------------------------------------------

class TestLoadImageStep:

    def test_requires_source_path(self):
        # source_path can come from metadata (runtime) or config (static YAML),
        # so requires() is empty — the step validates the path itself at runtime.
        assert LoadImageStep().requires() == []

    def test_populates_ctx_image_as_rgb(self, tmp_path):
        img = Image.new("RGB", (64, 48), color=(200, 100, 50))
        p = tmp_path / "test.png"
        img.save(p)

        ctx = LoadImageStep({"style_res": 0}).process(_ctx_with_source(p))

        assert ctx.image is not None
        assert ctx.image.mode == "RGB"

    def test_does_not_store_gray_intermediate(self, tmp_path):
        """LoadImageStep must not pre-compute gray — stylizers do this themselves."""
        p = tmp_path / "test.png"
        Image.new("RGB", (64, 48)).save(p)

        ctx = LoadImageStep({"style_res": 0}).process(_ctx_with_source(p))

        assert "gray" not in ctx.intermediates

    def test_populates_source_shape(self, tmp_path):
        p = tmp_path / "test.png"
        Image.new("RGB", (80, 60)).save(p)

        ctx = LoadImageStep({"style_res": 0}).process(_ctx_with_source(p))

        h, w = ctx.metadata["source_shape"]
        assert (w, h) == (80, 60)

    def test_scales_to_style_res(self, tmp_path):
        p = tmp_path / "large.png"
        Image.new("RGB", (2000, 1000)).save(p)

        ctx = LoadImageStep({"style_res": 512}).process(_ctx_with_source(p))

        h, w = ctx.metadata["source_shape"]
        assert max(h, w) <= 512

    def test_raises_on_missing_file(self, tmp_path):
        step = LoadImageStep()
        ctx = ImageContext(metadata={"source_path": tmp_path / "nonexistent.png"})
        with pytest.raises(FileNotFoundError):
            step.process(ctx)

    @pytest.mark.skipif(not _TESTIMAGE.exists(), reason="testimage.png not found")
    def test_real_testimage(self):
        ctx = LoadImageStep({"style_res": 512}).process(_ctx_with_source(_TESTIMAGE))
        assert ctx.image is not None
        assert ctx.image.mode == "RGB"
        assert "gray" not in ctx.intermediates
        h, w = ctx.metadata["source_shape"]
        assert max(h, w) <= 512


# ---------------------------------------------------------------------------
# Integration: stylizers update ctx.image so they can be chained
# ---------------------------------------------------------------------------

class TestStylizerChaining:

    @pytest.mark.skipif(not _TESTIMAGE.exists(), reason="testimage.png not found")
    def test_canny_updates_ctx_image(self):
        """After StyliseCannyStep, ctx.image holds the stylized result."""
        from pipeline.steps.stylise_canny_step import StyliseCannyStep

        ctx = _ctx_with_source(_TESTIMAGE)
        ctx = LoadImageStep({"style_res": 256}).process(ctx)
        original_image = ctx.image

        ctx = StyliseCannyStep().process(ctx)

        assert ctx.image is not None
        assert ctx.image is not original_image
        assert "gray" not in ctx.intermediates

    @pytest.mark.skipif(not _TESTIMAGE.exists(), reason="testimage.png not found")
    def test_two_stylizers_in_sequence(self):
        """Two stylizers can be chained: output of first feeds into second."""
        from pipeline.steps.stylise_canny_step import StyliseCannyStep
        from pipeline.steps.stylise_adaptive_step import StyliseAdaptiveStep

        ctx = _ctx_with_source(_TESTIMAGE)
        ctx = LoadImageStep({"style_res": 256}).process(ctx)
        ctx = StyliseCannyStep().process(ctx)
        ctx = StyliseAdaptiveStep().process(ctx)

        assert ctx.image is not None
        assert "binary" in ctx.intermediates

    @pytest.mark.skipif(not _TESTIMAGE.exists(), reason="testimage.png not found")
    def test_vectorize_without_stylizer(self):
        """VectorizeStep works directly after LoadImageStep — no stylizer needed."""
        from pipeline.steps.vectorize_step import VectorizeStep

        ctx = _ctx_with_source(_TESTIMAGE)
        ctx = LoadImageStep({"style_res": 256}).process(ctx)
        ctx = VectorizeStep().process(ctx)

        assert "paths" in ctx.intermediates
        assert isinstance(ctx.intermediates["paths"], list)

    @pytest.mark.skipif(not _TESTIMAGE.exists(), reason="testimage.png not found")
    def test_full_cv_pipeline(self):
        """End-to-end: load → stylise_canny → vectorise."""
        from pipeline.steps.stylise_canny_step import StyliseCannyStep
        from pipeline.steps.vectorize_step import VectorizeStep

        ctx = _ctx_with_source(_TESTIMAGE)
        ctx = LoadImageStep({"style_res": 256}).process(ctx)
        ctx = StyliseCannyStep().process(ctx)
        ctx = VectorizeStep().process(ctx)

        assert "paths" in ctx.intermediates
        assert len(ctx.intermediates["paths"]) > 0
