"""
pipeline/core/runner.py - PipelineRunner: orchestrates a sequence of steps

The runner accepts step configuration, instantiates the associated classes
from the registry, and guides an ImageContext sequentially through all steps.

Configuration Format
--------------------
A pipeline is described as a list of dicts::

    steps_config = [
        {"step": "stylise_canny",  "config": {"style_res": 1024, "canny_low": 50}},
        {"step": "vectorise",      "config": {"min_path_px": 10, "simplify_eps": 1.5}},
        {"step": "gcode_gen",      "config": {"target_width_mm": 180.0}},
    ]

    runner = PipelineRunner(steps_config)
    ctx_out = runner.run(ctx_in)

Each entry must contain:
    ``"step"``   - Step name (must exist in STEP_REGISTRY)
    ``"config"`` - Dict with parameters for this step (can be empty: ``{}``)
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.core.base import ImageContext, PipelineStep
from pipeline.core.registry import STEP_REGISTRY

logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Executes a configured sequence of PipelineSteps sequentially.

    Parameters
    ----------
    steps_config : list[dict]
        Ordered list of step definitions. Each dict must contain
        keys ``"step"`` (str) and ``"config"`` (dict).

    Raises
    ------
    KeyError
        If a step name is not found in ``STEP_REGISTRY`` - fail-fast
        at instantiation, not at execution.

    Example::

        runner = PipelineRunner([
            {"step": "stylise_xdog", "config": {"sigma": 0.4}},
            {"step": "vectorise",    "config": {}},
            {"step": "gcode_gen",    "config": {"target_width_mm": 150.0}},
        ])
        ctx = runner.run(initial_ctx)
    """

    def __init__(self, steps_config: list[dict[str, Any]]) -> None:
        self._steps: list[PipelineStep] = self._build_steps(steps_config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, ctx: ImageContext) -> ImageContext:
        """
        Guide ``ctx`` sequentially through all configured steps.

        Each step receives the context, mutates it, and returns it.
        The return value of the last step is the result of the pipeline.

        Parameters
        ----------
        ctx : ImageContext
            Start context (typically with populated ``image`` and
            ``metadata``; ``intermediates`` is initially empty).

        Returns
        -------
        ctx : ImageContext
            Context after all steps have executed.
        """
        logger.info("Pipeline started (%d steps)", len(self._steps))

        for i, step in enumerate(self._steps, start=1):
            step_name = type(step).__name__
            logger.info("Step %d/%d: %s", i, len(self._steps), step_name)
            ctx = step.process(ctx)
            logger.debug("Step %d/%d completed: %s", i, len(self._steps), step_name)

        logger.info("Pipeline completed.")
        return ctx

    # ------------------------------------------------------------------
    # Internal Helper Methods
    # ------------------------------------------------------------------

    def _build_steps(self, steps_config: list[dict[str, Any]]) -> list[PipelineStep]:
        """
        Instantiate all steps from configuration.

        Fails immediately with ``KeyError`` if a step name is unknown -
        ensures configuration errors are reported early and clearly.
        """
        steps: list[PipelineStep] = []

        for entry in steps_config:
            name: str = entry["step"]
            config: dict[str, Any] = entry.get("config", {})

            # YAML convention: enabled: false skips the step
            if not entry.get("enabled", True):
                logger.debug("Step skipped (enabled: false): %s", name)
                continue

            cls = STEP_REGISTRY.get(name)
            if cls is None:
                available = ", ".join(sorted(STEP_REGISTRY)) or "(none registered)"
                raise KeyError(
                    f"Unknown step: {name!r}. "
                    f"Available steps: {available}"
                )

            steps.append(cls(config))
            logger.debug("Step registered: %s -> %s", name, cls.__name__)

        return steps

    def __repr__(self) -> str:
        names = [type(s).__name__ for s in self._steps]
        return f"PipelineRunner(steps={names!r})"

