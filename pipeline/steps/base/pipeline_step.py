"""
pipeline/steps/base/pipeline_step.py - Abstract base class for all pipeline steps.

PipelineStep
    Abstract base class. Each concrete step inherits from it and
    implements ``process()``.  Optionally override ``requires()`` to declare
    which context keys the step needs - the runner will check them before
    executing the step.

MissingContextError
    Raised by the runner when a required context key is absent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.core.base import ImageContext

# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------

class PipelineStep(ABC):
    """
    Abstract base class for all pipeline steps.

    Each step receives its context, transforms it, and returns it.
    The ``config`` dict contains all parameters the step needs
    for its work.

    Parameters
    ----------
    config : dict
        Configuration values for this step. Keys and defaults are
        documented in the respective subclass. Missing keys are
        handled via ``self.config.get(key, default)``.
    label : str | None
        Optional human-readable display name for this step, read from the
        YAML ``label`` key by the runner. When it is not set, the display
        name falls back to the registry key the step was built from
        (e.g. ``"stylise_xdog"``), then to the class name. See
        :pyattr:`display_name`.

    Example::

        class MyStep(PipelineStep):
            def process(self, ctx: ImageContext) -> ImageContext:
                value = self.config.get("my_param", 42)
                # ... transformation ...
                ctx.intermediates["my_result"] = result
                return ctx
    """

    #: Canonical step name. Concrete steps may set this to their registry key
    #: (e.g. ``name = "stylise_xdog"``). Used as a display-name fallback for
    #: steps constructed outside the runner; the runner itself passes the
    #: registry key via ``_registry_key``.
    name: str | None = None

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self.label: str | None = None
        #: Registry key this step was built from; set by ``PipelineRunner``.
        self._registry_key: str | None = None

    @property
    def display_name(self) -> str:
        """Human-readable name for logs and progress reporting.

        Resolution order: YAML ``label`` -> registry key the step was built
        from -> class-level ``name`` -> class name. Always returns a string.
        """
        return (
            self.label
            or self._registry_key
            or type(self).name
            or type(self).__name__
        )

    def requires(self) -> list[str]:
        """
        Declare the context keys that this step requires before it can run.

        The runner calls this before ``process()`` and raises
        ``MissingContextError`` if any declared key is absent.

        Keys use dot-notation to address nested dicts:
          - ``"metadata.source_path"``     → ctx.metadata["source_path"]
          - ``"intermediates.binary"``     → ctx.intermediates["binary"]
          - ``"image"``                    → ctx.image (not None)

        Returns
        -------
        list[str]
            Keys that must be present. Return ``[]`` (default) to skip
            the check entirely.

        Example::

            def requires(self) -> list[str]:
                return ["image", "intermediates.binary"]
        """
        return []

    @abstractmethod
    def process(self, ctx: "ImageContext") -> "ImageContext":
        """
        Execute the step on the given context.

        Parameters
        ----------
        ctx : ImageContext
            Incoming context with data from previous step.

        Returns
        -------
        ctx : ImageContext
            Same context, enriched with this step's output.
            Steps should mutate ``ctx`` and return it - do not create
            a new object unless explicitly necessary.
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self.config!r})"


# ---------------------------------------------------------------------------
# Precondition Error
# ---------------------------------------------------------------------------

class MissingContextError(RuntimeError):
    """
    Raised by the runner when a step's declared ``requires()`` keys
    are not present in the ``ImageContext``.

    Attributes
    ----------
    step_name : str
        Name of the step that reported the missing key.
    missing_key : str
        The dot-notation key that was absent from the context.
    """

    def __init__(self, step_name: str, missing_key: str) -> None:
        self.step_name = step_name
        self.missing_key = missing_key
        super().__init__(
            f"Step '{step_name}' requires '{missing_key}' in the context, "
            f"but it is missing or None.  "
            f"Make sure the step that produces this value runs before '{step_name}'."
        )
