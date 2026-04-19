"""
pipeline/core/runner.py - PipelineRunner: orchestrates a sequence of steps

The runner accepts step configuration, instantiates the associated classes
from the registry, and guides an ImageContext sequentially through all steps.

Before executing each step the runner calls ``step.requires()`` and raises
``MissingContextError`` if any declared key is absent from the context.

Configuration Format
--------------------
A pipeline is described as a list of dicts::

    steps_config = [
        {"step": "load_image",     "config": {}},
        {"step": "stylise_canny",  "config": {"style_res": 1024, "canny_low": 50}},
        {"step": "vectorise",      "config": {"min_path_px": 10, "simplify_eps": 1.5}},
        {"step": "gcode_from_svg", "config": {"target_width_mm": 180.0}},
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

from pipeline.core.base import ImageContext, MissingContextError, PipelineStep
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

        Before each step ``step.requires()`` is checked against the current
        context.  A ``MissingContextError`` is raised immediately when a
        required key is absent, giving a clear diagnosis instead of a
        cryptic ``KeyError`` deep inside the step.

        Parameters
        ----------
        ctx : ImageContext
            Start context (typically with populated ``metadata["source_path"]``;
            ``intermediates`` is initially empty).

        Returns
        -------
        ctx : ImageContext
            Context after all steps have executed.

        Raises
        ------
        MissingContextError
            When a step's ``requires()`` list names a key that is not yet
            present in the context.
        """
        logger.info("Pipeline started (%d steps)", len(self._steps))

        for i, step in enumerate(self._steps, start=1):
            step_name = type(step).__name__
            logger.info("Step %d/%d: %s", i, len(self._steps), step_name)
            self._check_requires(step, ctx)
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

    @staticmethod
    def _check_requires(step: PipelineStep, ctx: ImageContext) -> None:
        """
        Verify all keys declared by ``step.requires()`` exist in ``ctx``.

        Supports dot-notation:
            ``"image"``                  → ctx.image is not None
            ``"metadata.source_path"``   → ctx.metadata["source_path"] exists
            ``"intermediates.binary"``   → ctx.intermediates["binary"] exists

        Raises
        ------
        MissingContextError
            On the first missing key found.
        """
        step_name = type(step).__name__
        for key in step.requires():
            parts = key.split(".", maxsplit=1)
            section = parts[0]
            sub_key = parts[1] if len(parts) == 2 else None

            if section == "image":
                if not ctx.has_image:
                    raise MissingContextError(step_name, key)
            elif section == "metadata":
                if sub_key is None or sub_key not in ctx.metadata:
                    raise MissingContextError(step_name, key)
            elif section == "intermediates":
                if sub_key is None or sub_key not in ctx.intermediates:
                    raise MissingContextError(step_name, key)
            else:
                # Unknown top-level section — warn but don't crash
                logger.warning(
                    "Step %s declared unknown requires() key: %r (ignored)",
                    step_name, key,
                )

    def __repr__(self) -> str:
        names = [type(s).__name__ for s in self._steps]
        return f"PipelineRunner(steps={names!r})"

