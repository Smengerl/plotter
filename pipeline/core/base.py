"""
pipeline/core/base.py - Shared data structure and abstract base class
                        for all pipeline steps.

ImageContext
    Passed between steps and grows with each step's output.
    Fields:
        image         - Optional PIL image (only for steps that need it;
                        may be None)
        metadata      - Immutable metadata from source image and config
                        values shared across multiple steps
                        (e.g. path, image size in pixels, target size in mm)
        intermediates - Intermediate results from individual steps for
                        downstream steps or debugging output
                        (e.g. binary array, paths list, gcode lines)

PipelineStep
    Abstract base class. Each concrete step inherits from it and
    implements ``process()``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared Data Structure
# ---------------------------------------------------------------------------

@dataclass
class ImageContext:
    """
    Shared data transport for the pipeline.

    Filled with input image at the start and then passed sequentially
    through all steps. Each step reads its inputs and writes its outputs.

    Attributes
    ----------
    image : PIL.Image.Image | None
        Currently active image. Optional - steps that don't need an image
        (e.g. GCodeGenStep, SendGcodeStep) can leave ``image`` as None.

    metadata : dict[str, Any]
        Immutable or rarely changed values relevant across multiple steps.
        Typical keys:

        ``"source_path"``      - pathlib.Path to original image
        ``"source_shape"``     - (H, W) of original in pixels
        ``"target_width_mm"``  - Drawing width in mm
        ``"target_height_mm"`` - Drawing height in mm

    intermediates : dict[str, Any]
        Intermediate results from individual steps. Typical keys:

        ``"binary"``       - ndarray[uint8] (H,W) after stylization;
                             also provides image size via .shape[:2]
        ``"paths"``        - list[ndarray[float32]] after vectorization
        ``"gcode_lines"``  - list[str] after GCode generation
    """

    image: "PILImage.Image | None" = None
    metadata: dict[str, Any] = field(default_factory=dict)
    intermediates: dict[str, Any] = field(default_factory=dict)


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

    Example::

        class MyStep(PipelineStep):
            def process(self, ctx: ImageContext) -> ImageContext:
                value = self.config.get("my_param", 42)
                # ... transformation ...
                ctx.intermediates["my_result"] = result
                return ctx
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}

    @abstractmethod
    def process(self, ctx: ImageContext) -> ImageContext:
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

