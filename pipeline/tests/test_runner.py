"""
pipeline/tests/test_runner.py - Unit tests for PipelineRunner and MissingContextError

Tests:
  - MissingContextError: attributes, message, type
  - PipelineRunner: requires() validation, step sequencing, unknown step name,
    enabled=false skip, deterministic execution
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

from pipeline.core.base import ImageContext, MissingContextError, PipelineStep
from pipeline.core.runner import PipelineRunner
from pipeline.steps.save_gcode_step import SaveGCodeStep


# ---------------------------------------------------------------------------
# Minimal test steps
# ---------------------------------------------------------------------------

class _RequiresBinaryStep(PipelineStep):
    def requires(self) -> list[str]:
        return ["intermediates.binary"]

    def process(self, ctx: ImageContext) -> ImageContext:
        return ctx


class _RequiresImageStep(PipelineStep):
    def requires(self) -> list[str]:
        return ["image"]

    def process(self, ctx: ImageContext) -> ImageContext:
        return ctx


class _RequiresSourcePath(PipelineStep):
    def requires(self) -> list[str]:
        return ["metadata.source_path"]

    def process(self, ctx: ImageContext) -> ImageContext:
        return ctx


class _NoOpStep(PipelineStep):
    def process(self, ctx: ImageContext) -> ImageContext:
        return ctx


# ---------------------------------------------------------------------------
# Tests: MissingContextError
# ---------------------------------------------------------------------------

class TestMissingContextError:

    def test_attributes(self):
        err = MissingContextError("FooStep", "metadata.source_path")
        assert err.step_name == "FooStep"
        assert err.missing_key == "metadata.source_path"

    def test_message_contains_step_and_key(self):
        err = MissingContextError("SomeStep", "intermediates.binary")
        assert "SomeStep" in str(err)
        assert "intermediates.binary" in str(err)

    def test_is_runtime_error(self):
        assert isinstance(MissingContextError("S", "k"), RuntimeError)


# ---------------------------------------------------------------------------
# Tests: Runner precondition checks
# ---------------------------------------------------------------------------

class TestRunnerPreconditions:

    def test_missing_intermediate_raises(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_RequiresBinaryStep()]
        with pytest.raises(MissingContextError) as exc_info:
            runner.run(ImageContext())
        assert "intermediates.binary" in str(exc_info.value)
        assert "_RequiresBinaryStep" in str(exc_info.value)

    def test_missing_image_raises(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_RequiresImageStep()]
        with pytest.raises(MissingContextError) as exc_info:
            runner.run(ImageContext())
        assert "image" in str(exc_info.value)

    def test_missing_metadata_raises(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_RequiresSourcePath()]
        with pytest.raises(MissingContextError) as exc_info:
            runner.run(ImageContext())
        assert "metadata.source_path" in str(exc_info.value)

    def test_present_intermediate_passes(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_RequiresBinaryStep()]
        ctx = ImageContext()
        ctx.intermediates["binary"] = np.zeros((10, 10), dtype=np.uint8)
        assert runner.run(ctx) is ctx

    def test_present_image_passes(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_RequiresImageStep()]
        ctx = ImageContext(image=Image.new("RGB", (10, 10)))
        assert runner.run(ctx) is ctx

    def test_no_requirements_always_passes(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_NoOpStep()]
        assert runner.run(ImageContext()) is not None


# ---------------------------------------------------------------------------
# Tests: PipelineRunner construction
# ---------------------------------------------------------------------------

class TestPipelineRunnerConstruction:

    def test_unknown_step_raises_key_error(self):
        with pytest.raises(KeyError, match="nonexistent_step"):
            PipelineRunner([{"step": "nonexistent_step", "config": {}}])

    def test_enabled_false_skips_step(self):
        """A step with enabled=false is silently skipped."""
        runner = PipelineRunner([
            {"step": "load_image", "config": {}, "enabled": False},
        ])
        assert len(runner._steps) == 0

    def test_steps_executed_in_order(self):
        """Steps run in declaration order; each sees the previous step's output."""
        execution_order: list[int] = []

        class _OrderStep(PipelineStep):
            def __init__(self, n: int) -> None:
                super().__init__()
                self._n = n

            def process(self, ctx: ImageContext) -> ImageContext:
                execution_order.append(self._n)
                return ctx

        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_OrderStep(1), _OrderStep(2), _OrderStep(3)]
        runner.run(ImageContext())
        assert execution_order == [1, 2, 3]

    def test_run_returns_same_ctx_object(self):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner._steps = [_NoOpStep()]
        ctx = ImageContext()
        assert runner.run(ctx) is ctx


# ---------------------------------------------------------------------------
# Tests: SaveGCodeStep output_path convention
# ---------------------------------------------------------------------------

class TestSaveGCodeStepOutputPath:

    def _ctx_with_gcode(self) -> ImageContext:
        ctx = ImageContext()
        ctx.intermediates["gcode_lines"] = ["G21", "G90", "M5"]
        return ctx

    def test_metadata_takes_priority_over_config(self, tmp_path):
        meta_path = tmp_path / "from_meta.gcode"
        cfg_path = tmp_path / "from_cfg.gcode"
        ctx = self._ctx_with_gcode()
        ctx.metadata["output_path"] = str(meta_path)

        SaveGCodeStep({"output_path": str(cfg_path)}).process(ctx)

        assert meta_path.exists()
        assert not cfg_path.exists()

    def test_config_used_when_no_metadata(self, tmp_path):
        cfg_path = tmp_path / "from_cfg.gcode"
        SaveGCodeStep({"output_path": str(cfg_path)}).process(self._ctx_with_gcode())
        assert cfg_path.exists()

    def test_raises_when_no_path_set(self):
        with pytest.raises(ValueError, match="output_path"):
            SaveGCodeStep().process(self._ctx_with_gcode())

    def test_written_file_contains_gcode(self, tmp_path):
        out = tmp_path / "out.gcode"
        ctx = self._ctx_with_gcode()
        ctx.metadata["output_path"] = str(out)
        SaveGCodeStep().process(ctx)
        assert "G21" in out.read_text()

    def test_requires_gcode_lines(self):
        assert "intermediates.gcode_lines" in SaveGCodeStep().requires()
