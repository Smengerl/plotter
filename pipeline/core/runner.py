"""
pipeline/core/runner.py - PipelineRunner: orchestrates a sequence of steps

The runner accepts step configuration, instantiates the associated classes
from the registry, and guides an ImageContext sequentially through all steps.

Before executing each step the runner calls ``step.requires()`` and raises
``MissingContextError`` if any declared key is absent from the context.

Configuration Format
--------------------
A pipeline is described as a dict with a ``steps`` list (parsed from YAML by
``main.py``) or passed directly as a list for programmatic use::

    # YAML top-level keys (loaded by main.py):
    #   name        - required: human-readable pipeline name (shown on run)
    #   description - optional: longer description (shown below name)
    #   steps       - list of step entries

    steps_config = [
        {"step": "load_image",     "label": "Load Source Image", "config": {}},
        {"step": "stylise_canny",  "config": {"style_res": 1024, "canny_low": 50}},
        {"step": "vectorise",      "label": "Vectorizing",       "config": {"min_path_px": 10}},
        {"step": "gcode_from_svg", "config": {"target_width_mm": 180.0}},
    ]

    runner = PipelineRunner(steps_config, name="My Pipeline", description="Optional.")
    ctx_out = runner.run(ctx_in)

Each step entry must contain:
    ``"step"``   - Step name (must exist in STEP_REGISTRY)
    ``"config"`` - Dict with parameters for this step (can be empty: ``{}``)

Optional step entry keys:
    ``"label"``   - Human-readable display name shown as "Step X/Y: <label>"
    ``"enabled"`` - Set to ``false`` to skip this step (default: ``true``)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipeline.core.base import ImageContext, MissingContextError, PipelineStep
from pipeline.core.registry import STEP_REGISTRY

logger = logging.getLogger(__name__)

# Signature for the optional progress callback passed to PipelineRunner.
# Called after each step (or in dry-run: before each step without execution).
#   step_index   – 1-based index of the current step
#   total_steps  – total number of steps in the pipeline
#   label        – display name of the step (see PipelineStep.display_name)
ProgressCallback = Callable[[int, int, str], None]


class PipelineRunner:
    """
    Executes a configured sequence of PipelineSteps sequentially.

    Parameters
    ----------
    steps_config : list[dict]
        Ordered list of step definitions. Each dict must contain
        keys ``"step"`` (str) and ``"config"`` (dict). An optional
        ``"label"`` (str) key provides a human-readable display name
        for the step shown during execution.
    name : str
        Human-readable name of this pipeline. Displayed when the
        pipeline starts. Defaults to ``"Pipeline"`` for direct
        construction; ``from_yaml`` uses the YAML ``name`` key and
        falls back to the config file's stem.
    description : str | None
        Optional longer description of what the pipeline does.
        Logged below the name when execution starts.
    dry_run : bool
        When ``True``, the plan is printed to stdout but no step is
        executed and the context is returned unchanged.
    on_progress : ProgressCallback | None
        Optional callback invoked after each step (normal mode) or
        before each step entry is printed (dry-run).  Signature::

            def cb(step_index: int, total_steps: int, label: str) -> None: ...

        Intended for GUI progress bars or external monitoring.

    Raises
    ------
    KeyError
        If a step name is not found in ``STEP_REGISTRY`` - fail-fast
        at instantiation, not at execution.

    Example::

        runner = PipelineRunner(
            steps_config=[
                {"step": "stylise_xdog", "label": "XDoG Edge Detection", "config": {"sigma": 0.4}},
                {"step": "vectorise",    "config": {}},
                {"step": "gcode_gen",    "config": {"target_width_mm": 150.0}},
            ],
            name="XDoG Plotter Pipeline",
            description="Stylizes an image with XDoG and converts to GCode.",
            on_progress=lambda i, n, label: print(f"Progress: {i}/{n} – {label}"),
        )
        ctx = runner.run(initial_ctx)
    """

    def __init__(
        self,
        steps_config: list[dict[str, Any]],
        name: str = "Pipeline",
        description: str | None = None,
        dry_run: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.name: str = name
        self.description: str | None = description
        self.dry_run: bool = dry_run
        self.on_progress: ProgressCallback | None = on_progress
        self._steps: list[PipelineStep] = self._build_steps(steps_config)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(
        cls,
        config_path: Path,
        dry_run: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> "PipelineRunner":
        """
        Load a YAML config file and build a ready-to-run ``PipelineRunner``.

        This is the preferred entry point for both the CLI and the GUI:
        all YAML field names are encapsulated here, so callers deal only
        with a ``Path`` and optional flags.

        Expected YAML format::

            name: "My Pipeline"           # optional — defaults to the file stem
            description: "Optional text"  # optional — shown below name
            steps:
              - step: load_image
                label: "Load Source Image"  # optional — overrides the step's own name
                config: {}
              - step: stylise_canny
                config: {style_res: 1024}

        Parameters
        ----------
        config_path : Path
            Path to the ``.yaml`` pipeline configuration file.
        dry_run : bool
            When ``True`` the plan is printed but no step is executed.
        on_progress : ProgressCallback | None
            Optional callback invoked after each step; see ``__init__``.

        Returns
        -------
        PipelineRunner
            Fully configured runner, ready for ``runner.run(ctx)``.

        Raises
        ------
        FileNotFoundError
            If ``config_path`` does not exist.
        ValueError
            If the file is not valid YAML or is missing the ``steps`` key.
        ImportError
            If PyYAML is not installed.
        KeyError
            If an unknown step name is referenced in the config.
        """
        try:
            import yaml  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("PyYAML is not installed: pip install pyyaml") from exc

        if not config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found: {config_path}")

        with config_path.open(encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

        if not isinstance(data, dict) or "steps" not in data:
            raise ValueError(
                f"Pipeline config {config_path} must be a dict with a 'steps' key."
            )

        logger.debug(
            "Configuration loaded: %s  (%d steps)", config_path, len(data["steps"])
        )

        return cls(
            steps_config=data["steps"],
            # Fall back to the config's file name (e.g. "xdog_sketch") rather than
            # the generic "Pipeline" so every consumer - CLI log, GUI list, GUI
            # job panel - shows the same, identifiable name without extra work.
            name=data.get("name") or config_path.stem,
            description=data.get("description"),
            dry_run=dry_run,
            on_progress=on_progress,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, ctx: ImageContext) -> ImageContext:
        """
        Guide ``ctx`` sequentially through all configured steps.

        In dry-run mode the header and each step label are printed to
        stdout but ``step.process()`` is **not** called and the context
        is returned unchanged.

        Parameters
        ----------
        ctx : ImageContext
            Start context (typically with populated ``metadata["source_path"]``;
            ``intermediates`` is initially empty).

        Returns
        -------
        ctx : ImageContext
            Context after all steps have executed (or unchanged in dry-run).

        Raises
        ------
        MissingContextError
            When a step's ``requires()`` list names a key that is not yet
            present in the context (normal mode only).
        """
        total = len(self._steps)
        dry_run: bool = getattr(self, "dry_run", False)
        log = print if dry_run else logger.info

        log(f"Pipeline '{getattr(self, 'name', 'Pipeline')}' started ({total} steps)")
        description: str | None = getattr(self, "description", None)
        if description:
            log(f"  {description}")

        for i, step in enumerate(self._steps, start=1):
            display_name = step.display_name
            log(f"Step {i}/{total}: {display_name}")

            if not dry_run:
                self._check_requires(step, ctx)
                ctx = step.process(ctx)
                logger.debug("Step %d/%d completed: %s", i, total, display_name)

            on_progress = getattr(self, "on_progress", None)
            if on_progress is not None:
                on_progress(i, total, display_name)

        if dry_run:
            print("No steps were executed.")
        else:
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

            step = cls(config)
            step.label = entry.get("label") or None
            step._registry_key = name
            steps.append(step)
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
        step_name = step.display_name
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
        return f"PipelineRunner(name={getattr(self, 'name', 'Pipeline')!r}, steps={names!r})"

