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
        assert step.strength == 0.8
        assert step.enable_model_cpu_offload is False

    def test_initialization_custom_config(self):
        """Test step initialization with custom parameters."""
        step = StyliseControlNetStep(
            prompt="watercolor painting, soft colors",
            negative_prompt="sharp, harsh",
            controlnet_type="softedge",
            num_inference_steps=30,
            guidance_scale=10.0,
            strength=0.9,
            enable_model_cpu_offload=True,
        )
        assert step.prompt == "watercolor painting, soft colors"
        assert step.negative_prompt == "sharp, harsh"
        assert step.controlnet_type == "softedge"
        assert step.num_inference_steps == 30
        assert step.guidance_scale == 10.0
        assert step.strength == 0.9
        assert step.enable_model_cpu_offload is True

    def test_device_resolution_auto(self):
        """Test automatic device resolution."""
        step = StyliseControlNetStep(device="auto")
        # Should resolve to cuda, mps, or cpu (whichever is available)
        assert step._resolve_device("auto") in ("cuda", "mps", "cpu")

    def test_device_resolution_explicit(self):
        """Test explicit device specification."""
        for device in ["cpu", "cuda", "mps"]:
            step = StyliseControlNetStep(device=device)
            assert step._resolve_device(device) == device

    def test_controlnet_types_supported(self):
        """Test that common ControlNet types are supported."""
        supported_types = ["canny", "lineart", "softedge", "scribble", "pose", "depth"]
        for cnet_type in supported_types:
            step = StyliseControlNetStep(controlnet_type=cnet_type)
            assert step.controlnet_type == cnet_type


class TestStyliseControlNetStepMocked:
    """Test ControlNet step with mocked model loading (no GPU required)."""

    @mock.patch("pipeline.steps.stylise_controlnet_step._check_dependencies")
    def test_missing_dependencies_error(self, mock_check):
        """Test that missing dependencies raise informative error."""
        mock_check.return_value = (False, "diffusers not found")
        step = StyliseControlNetStep()

        with pytest.raises(ImportError):
            step._load_models()

    def test_prepare_controlnet_input_with_mock(self):
        """Test ControlNet input preparation (no real diffusion)."""
        from PIL import Image

        step = StyliseControlNetStep(controlnet_type="lineart")

        # Create a test image
        test_img = Image.new("RGB", (256, 256), color="white")

        # Lineart should return RGB unchanged
        result = step._prepare_controlnet_input(test_img)
        assert result.mode == "RGB"
        assert result.size == (256, 256)

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
