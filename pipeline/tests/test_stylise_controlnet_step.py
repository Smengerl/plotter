"""
pipeline/tests/test_stylise_controlnet_step.py - Unit tests for ControlNet style transfer

Tests the StyliseControlNetStep with mocked models (no actual downloads/GPU usage).
Verifies:
- Step instantiation with valid configs
- Device resolution (auto/cuda/mps/cpu)
- Config inheritance and attribute handling
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

from pipeline.core.base import ImageContext
from pipeline.steps.stylise_controlnet_step import StyliseControlNetStep


class TestStyliseControlNetStepBasics:
    """Test ControlNet step initialization and configuration."""

    def test_initialization_default_config(self):
        """Test step creates with default configuration."""
        step = StyliseControlNetStep()
        assert step.name == "stylise_controlnet"
        assert step.prompt == "oil painting, masterpiece, detailed"
        assert step.negative_prompt == "blurry, distorted, low quality"
        assert step.controlnet_type == "lineart"
        assert step.num_inference_steps == 20
        assert step.guidance_scale == 7.5
        assert step.enable_model_cpu_offload is False
        # Default models
        assert step.base_model == "runwayml/stable-diffusion-v1-5"
        assert step.controlnet_model == "lllyasviel/control_v11p_sd15_lineart"

    def test_initialization_custom_config(self):
        """Test step initialization with custom parameters."""
        step = StyliseControlNetStep({
            "prompt": "watercolor painting, soft colors",
            "negative_prompt": "sharp, harsh",
            "controlnet_type": "softedge",
            "num_inference_steps": 30,
            "guidance_scale": 10.0,
            "enable_model_cpu_offload": True,
        })
        assert step.prompt == "watercolor painting, soft colors"
        assert step.negative_prompt == "sharp, harsh"
        assert step.controlnet_type == "softedge"
        assert step.num_inference_steps == 30
        assert step.guidance_scale == 10.0
        assert step.enable_model_cpu_offload is True

    def test_base_model_explicit_override(self):
        """Test that base_model config key overrides the default SD model."""
        step = StyliseControlNetStep({"base_model": "CompVis/stable-diffusion-v1-4"})
        assert step.base_model == "CompVis/stable-diffusion-v1-4"

    def test_controlnet_model_explicit_override(self):
        """Test that controlnet_model config key overrides the controlnet_type lookup."""
        step = StyliseControlNetStep({"controlnet_model": "lllyasviel/control_v11p_sd15_canny"})
        assert step.controlnet_model == "lllyasviel/control_v11p_sd15_canny"

    def test_controlnet_type_sets_controlnet_model(self):
        """Test that controlnet_type drives controlnet_model when not explicitly set."""
        step = StyliseControlNetStep({"controlnet_type": "canny"})
        assert step.controlnet_model == "lllyasviel/control_v11p_sd15_canny"

    def test_controlnet_model_takes_priority_over_type(self):
        """Test that explicit controlnet_model overrides the controlnet_type lookup."""
        step = StyliseControlNetStep({
            "controlnet_type": "canny",
            "controlnet_model": "lllyasviel/control_v11p_sd15_lineart",
        })
        assert step.controlnet_model == "lllyasviel/control_v11p_sd15_lineart"

    def test_device_resolution_auto(self):
        """Test automatic device resolution."""
        step = StyliseControlNetStep({"device": "auto"})
        # Should resolve to cuda, mps, or cpu (whichever is available)
        assert step._resolve_device("auto") in ("cuda", "mps", "cpu")

    def test_device_resolution_explicit(self):
        """Test explicit device specification."""
        for device in ["cpu", "cuda", "mps"]:
            step = StyliseControlNetStep({"device": device})
            assert step._resolve_device(device) == device

    def test_controlnet_types_supported(self):
        """Test that common ControlNet types are supported."""
        supported_types = ["canny", "lineart", "softedge", "scribble", "pose", "depth"]
        for cnet_type in supported_types:
            step = StyliseControlNetStep({"controlnet_type": cnet_type})
            assert step.controlnet_type == cnet_type

    def test_hf_token_path_default_none(self):
        """Test that hf_token_path defaults to None."""
        step = StyliseControlNetStep()
        assert step.hf_token_path is None

    def test_hf_token_path_custom(self):
        """Test that hf_token_path can be set via config."""
        step = StyliseControlNetStep({"hf_token_path": ".hf_token"})
        assert step.hf_token_path == ".hf_token"

    def test_load_hf_token_returns_none_when_not_configured(self):
        """Test _load_hf_token returns None when hf_token_path is None."""
        step = StyliseControlNetStep()
        assert step._load_hf_token() is None

    def test_load_hf_token_warns_when_file_missing(self, tmp_path):
        """Test _load_hf_token returns None gracefully when file does not exist."""
        step = StyliseControlNetStep({"hf_token_path": str(tmp_path / "missing_token")})
        result = step._load_hf_token()
        assert result is None

    def test_load_hf_token_reads_file(self, tmp_path):
        """Test _load_hf_token reads token content from file."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("hf_testtoken1234\n")
        step = StyliseControlNetStep({"hf_token_path": str(token_file)})
        token = step._load_hf_token()
        assert token == "hf_testtoken1234"

    def test_load_hf_token_strips_whitespace(self, tmp_path):
        """Test _load_hf_token strips leading/trailing whitespace."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("  hf_testtoken1234  \n")
        step = StyliseControlNetStep({"hf_token_path": str(token_file)})
        assert step._load_hf_token() == "hf_testtoken1234"

    def test_load_hf_token_cached_after_first_read(self, tmp_path):
        """Test _load_hf_token caches token after first read."""
        token_file = tmp_path / ".hf_token"
        token_file.write_text("hf_testtoken1234")
        step = StyliseControlNetStep({"hf_token_path": str(token_file)})
        token1 = step._load_hf_token()
        token_file.unlink()  # Delete file after first read
        token2 = step._load_hf_token()  # Should return cached value
        assert token1 == token2 == "hf_testtoken1234"


class TestStyliseControlNetStepMocked:
    """Test ControlNet step with mocked model loading (no GPU required)."""

    @mock.patch("pipeline.steps.stylise_controlnet_step._check_dependencies")
    def test_missing_dependencies_error(self, mock_check):
        """Test that missing dependencies raise informative error."""
        mock_check.return_value = (False, "diffusers not found")
        step = StyliseControlNetStep()

        with pytest.raises(ImportError):
            step._load_models()

    def test_prepare_control_image_lineart_uses_detector(self):
        """Test that lineart type runs LineartDetector, not a plain passthrough."""
        from PIL import Image

        step = StyliseControlNetStep({"controlnet_type": "lineart", "device": "cpu"})
        test_img = Image.new("RGB", (256, 256), color="white")
        expected = Image.new("RGB", (256, 256), color="black")

        with mock.patch("controlnet_aux.LineartDetector") as MockDetector:
            instance = MockDetector.from_pretrained.return_value
            instance.return_value = expected
            result = step._prepare_control_image(test_img)

        MockDetector.from_pretrained.assert_called_once_with("lllyasviel/Annotators")
        assert result is expected

    def test_prepare_control_image_canny_uses_detector(self):
        """Test that canny type runs CannyDetector."""
        from PIL import Image

        step = StyliseControlNetStep({"controlnet_type": "canny", "device": "cpu"})
        test_img = Image.new("RGB", (256, 256), color="white")
        expected = Image.new("RGB", (256, 256), color="black")

        with mock.patch("controlnet_aux.CannyDetector") as MockDetector:
            instance = MockDetector.return_value
            instance.return_value = expected
            result = step._prepare_control_image(test_img)

        assert result is expected



    def test_process_requires_models_loaded(self):
        """Test that process() requires models to be loaded first."""
        from PIL import Image

        step = StyliseControlNetStep()
        ctx = ImageContext(Image.new("RGB", (256, 256)))

        # Mock _check_dependencies to fail
        with mock.patch(
            "pipeline.steps.stylise_controlnet_step._check_dependencies",
            return_value=(False, "Test: missing deps"),
        ):
            with pytest.raises(ImportError):
                step.process(ctx)


class TestStyliseControlNetIntegration:
    """Integration tests with actual dependencies (if available)."""

    @pytest.mark.skipif(
        not all(
            __import__("importlib.util").util.find_spec(pkg)
            for pkg in ["diffusers", "torch"]
        ),
        reason="diffusers and torch not installed",
    )
    def test_real_pipeline_creation(self):
        """Test that real pipeline can be created (but don't run it)."""
        step = StyliseControlNetStep()
        # Just verify it can be instantiated - don't call _load_models()
        # to avoid expensive GPU operations in tests
        assert step is not None
        assert step.name == "stylise_controlnet"
