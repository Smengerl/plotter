"""
pipeline/tests/test_stylise_img2img_step.py - Unit tests for Img2Img style transfer step

Tests the StyliseImg2ImgStep with mocked models (no actual downloads/GPU usage).
Verifies:
- Step instantiation with valid configs
- hf_token_path loading and caching
- Error handling for missing token files
- Error handling for missing dependencies
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

# Add repo to path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.steps.stylise_img2img_step import StyliseImg2ImgStep


class TestStyliseImg2ImgStepBasics:
    """Test Img2Img step initialization and configuration."""

    def test_initialization_default_config(self):
        """Test step creates with default configuration."""
        step = StyliseImg2ImgStep()
        assert step.prompt == "artistic style, beautiful"
        assert step.negative_prompt == "blurry, low quality, distorted"
        assert step.strength == 0.7
        assert step.num_inference_steps == 20
        assert step.guidance_scale == 7.5
        assert step.model_id == "stable-diffusion-v1-5/stable-diffusion-v1-5"
        assert step.hf_token_path is None
        assert step.enable_model_cpu_offload is False

    def test_initialization_custom_config(self):
        """Test step initialization with custom config dict."""
        step = StyliseImg2ImgStep(config={
            "prompt": "watercolor painting",
            "strength": 0.5,
            "model_id": "some/model",
            "hf_token_path": ".hf_token",
        })
        assert step.prompt == "watercolor painting"
        assert step.strength == 0.5
        assert step.model_id == "some/model"
        assert step.hf_token_path == ".hf_token"

    def test_strength_clamped_to_valid_range(self):
        """Test that strength is clamped to 0.0–1.0."""
        step_low = StyliseImg2ImgStep(config={"strength": -0.5})
        assert step_low.strength == 0.0

        step_high = StyliseImg2ImgStep(config={"strength": 1.5})
        assert step_high.strength == 1.0

    def test_hf_token_path_default_none(self):
        """Test that hf_token_path defaults to None."""
        step = StyliseImg2ImgStep()
        assert step.hf_token_path is None

    def test_hf_token_path_from_config(self):
        """Test that hf_token_path is set from config."""
        step = StyliseImg2ImgStep(config={"hf_token_path": "/path/to/token"})
        assert step.hf_token_path == "/path/to/token"


class TestStyliseImg2ImgHfToken:
    """Test HuggingFace token loading."""

    def test_load_hf_token_returns_none_when_not_configured(self):
        """Test _load_hf_token returns None when hf_token_path is None."""
        step = StyliseImg2ImgStep()
        assert step._load_hf_token() is None

    def test_load_hf_token_returns_none_when_file_missing(self, tmp_path):
        """Test _load_hf_token returns None gracefully when file does not exist."""
        step = StyliseImg2ImgStep(config={"hf_token_path": str(tmp_path / "missing_token")})
        result = step._load_hf_token()
        assert result is None

    def test_load_hf_token_reads_file(self, tmp_path):
        """Test _load_hf_token reads token content from file."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("hf_testtoken1234\n")
        step = StyliseImg2ImgStep(config={"hf_token_path": str(token_file)})
        token = step._load_hf_token()
        assert token == "hf_testtoken1234"

    def test_load_hf_token_strips_whitespace(self, tmp_path):
        """Test _load_hf_token strips leading/trailing whitespace."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("  hf_testtoken1234  \n")
        step = StyliseImg2ImgStep(config={"hf_token_path": str(token_file)})
        assert step._load_hf_token() == "hf_testtoken1234"

    def test_load_hf_token_cached_after_first_read(self, tmp_path):
        """Test _load_hf_token caches token after first read."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("hf_testtoken1234")
        step = StyliseImg2ImgStep(config={"hf_token_path": str(token_file)})
        token1 = step._load_hf_token()
        token_file.unlink()  # Delete file after first read
        token2 = step._load_hf_token()  # Should return cached value
        assert token1 == token2 == "hf_testtoken1234"


class TestStyliseImg2ImgStepMocked:
    """Test Img2Img step with mocked model loading (no GPU required)."""

    @mock.patch("pipeline.steps.stylise_img2img_step._check_dependencies")
    def test_missing_dependencies_error(self, mock_check):
        """Test that missing dependencies raise informative ImportError."""
        mock_check.return_value = (False, "diffusers not found")
        step = StyliseImg2ImgStep()

        with pytest.raises(ImportError, match="diffusers"):
            step._load_models()

    @mock.patch("pipeline.steps.stylise_img2img_step._check_dependencies")
    def test_model_not_found_raises_helpful_error(self, mock_check):
        """Test that 404 from HF Hub raises a helpful RuntimeError."""
        mock_check.return_value = (True, "")

        step = StyliseImg2ImgStep(config={"model_id": "nonexistent/model"})

        mock_pipeline_cls = mock.MagicMock()
        mock_pipeline_cls.from_pretrained.side_effect = Exception(
            "404 Client Error: Repository Not Found"
        )

        with mock.patch.dict("sys.modules", {
            "diffusers": mock.MagicMock(
                StableDiffusionImg2ImgPipeline=mock_pipeline_cls
            ),
            "torch": mock.MagicMock(float32=1, float16=1),
        }):
            with pytest.raises(RuntimeError, match="hf_token_path"):
                step._load_models()
