"""
pipeline/core/base.py - Shared data structure for all pipeline steps.

ImageContext
    Passed between steps and grows with each step's output.
    Fields:
        image         - Currently active PIL image.  LoadImageStep sets it
                        from ``source_path``; subsequent steps read and update it.
                        Accessing the property raises ValueError if not set yet.
        metadata      - Immutable metadata from source image and config
                        values shared across multiple steps
                        (e.g. path, image size in pixels, target size in mm).
                        Runtime values (e.g. output_path) are also stored here so
                        they can be set dynamically before running the pipeline.
        intermediates - Intermediate results from individual steps for
                        downstream steps or debugging output
                        (e.g. binary array, paths list, gcode lines)

PipelineStep and MissingContextError are defined in
``pipeline/steps/base/pipeline_step.py`` and re-exported here for
backward compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared Data Structure
# ---------------------------------------------------------------------------

class ImageContext:
    """
    Shared data transport for the pipeline.

    Filled with input image at the start and then passed sequentially
    through all steps. Each step reads its inputs and writes its outputs.

    Attributes
    ----------
    image : PIL.Image.Image
        Currently active image (PIL, RGB mode).
        ``LoadImageStep`` loads it from ``metadata["source_path"]`` and
        all stylization steps read *and* update this field.
        Accessing this property raises ``ValueError`` if no image has been
        set yet — use :attr:`has_image` to check first when the image is
        optional.

    has_image : bool
        ``True`` if a PIL image is currently stored in the context.

    metadata : dict[str, Any]
        Input values and runtime state relevant across multiple steps.
        Typical keys:

        ``"source_path"``      - pathlib.Path to original image file
        ``"source_shape"``     - (H, W) of original in pixels
        ``"target_width_mm"``  - Drawing width in mm
        ``"target_height_mm"`` - Drawing height in mm
        ``"output_path"``      - Target path for SaveGCodeStep / SaveImageStep
                                 (set here so it can be overridden at runtime)

    intermediates : dict[str, Any]
        Intermediate results from individual steps. Typical keys:

        ``"binary"``       - ndarray[uint8] (H,W) after stylization;
                             also provides image size via .shape[:2]
        ``"paths"``        - list[ndarray[float32]] after vectorization
        ``"gcode_lines"``  - list[str] after GCode generation
    """

    def __init__(
        self,
        image: "PILImage.Image | None" = None,
        metadata: "dict[str, Any] | None" = None,
        intermediates: "dict[str, Any] | None" = None,
    ) -> None:
        self._image: "PILImage.Image | None" = image
        self.metadata: dict[str, Any] = metadata if metadata is not None else {}
        self.intermediates: dict[str, Any] = intermediates if intermediates is not None else {}

    # ------------------------------------------------------------------
    # image property
    # ------------------------------------------------------------------

    @property
    def image(self) -> "PILImage.Image":
        """Return the currently active PIL image.

        Raises:
            ValueError: If no image has been set yet.
        """
        if self._image is None:
            raise ValueError(
                "ImageContext.image: no image set. "
                "Make sure LoadImageStep runs before accessing ctx.image."
            )
        return self._image

    @image.setter
    def image(self, value: "PILImage.Image | None") -> None:
        """Store a new PIL image (or ``None`` to clear)."""
        self._image = value

    @property
    def has_image(self) -> bool:
        """``True`` if a PIL image is currently stored in the context."""
        return self._image is not None

    # ------------------------------------------------------------------
    # gray property
    # ------------------------------------------------------------------

    @property
    def image_as_gray(self) -> "npt.NDArray[np.uint8]":
        """Return ``ctx.image`` as a 2-D (H, W) uint8 grayscale ndarray.

        Converts the currently active PIL RGB image to a grayscale numpy
        array using OpenCV.  The result is recomputed on every access so
        it always reflects the current ``ctx.image``.

        Returns:
            2-D uint8 ndarray with shape (H, W).

        Raises:
            ValueError: If no image has been set yet.
        """
        if self._image is None:
            raise ValueError(
                "ImageContext.gray: no image set. "
                "Make sure LoadImageStep runs before accessing ctx.gray."
            )
        import cv2  # local import keeps core/base.py free of hard cv2 dependency
        import numpy as np

        rgb_array = np.array(self._image.convert("RGB"))
        gray: npt.NDArray[np.uint8] = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
        return gray.astype(np.uint8)

    def pil_to_binary(self, pil: "PILImage.Image", threshold: int) -> "npt.NDArray[np.uint8]":
        """Convert a PIL image to a binary uint8 ndarray using a threshold.

        Args:
            pil: PIL image (any mode).  Converted to grayscale first.
            threshold: Integer threshold in [0, 255]; pixels > threshold → 255.

        Returns:
            2-D uint8 ndarray where line = 255 and background = 0.
        """
        import cv2  # type: ignore[import]
        import numpy as np

        gray = np.array(pil.convert("L"))
        _, binary = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY)
        return binary.astype(np.uint8)

    def set_stylize_result(self, binary: "npt.NDArray[np.uint8]") -> None:
        """Store a binary stylization result into the context in one call.

        1. Normalises *binary* to uint8 (no-op if already correct dtype).
        2. Stores it in ``ctx.intermediates["binary"]`` for ``VectorizeStep``
           and other downstream consumers.
        3. Converts it to a grayscale-then-RGB PIL image and writes it to
           ``ctx.image`` so that chained stylizers or ``SaveImageStep`` work.

        Every ``_stylise()`` implementation must call this instead of
        returning the array.

        Args:
            binary: 2-D ndarray (H, W) where 255 = line, 0 = background.
        """
        import numpy as np
        from PIL import Image as _PILImage

        binary_u8 = binary.astype(np.uint8, copy=False)
        self.intermediates["binary"] = binary_u8
        self.image = _PILImage.fromarray(binary_u8, mode="L").convert("RGB")


    @image.setter
    def image_as_grayscale_pil(self, pil: "PILImage.Image", threshold: int) -> None:
        """Binarize *pil* and store the result — combines ``pil_to_binary`` and
        ``set_stylize_result`` in a single call.

        Useful for stylizers (NN, Diffusion) whose output is a PIL image that
        must be thresholded before being written back into the context.

        Args:
            pil: Stylizer output (any PIL mode). Converted to grayscale first.
            threshold: Integer threshold in [0, 255]; pixels > threshold → 255.
        """
        self.set_stylize_result(self.pil_to_binary(pil, threshold))

    @property
    def image_as_grayscale_pil(self) -> "PILImage.Image":
        """Return ``ctx.image`` converted to grayscale and back to RGB PIL.

        Combines ``ctx.gray`` and ``ctx.gray_to_rgb_pil`` in a single
        property access. The result is a three-channel PIL image whose
        three channels carry identical grayscale values — the format
        expected by NN detectors that require RGB input but only operate
        on luminance.

        Raises:
            ValueError: If no image has been set yet.
        """
        
        import cv2  # type: ignore[import]
        import numpy as np
        from PIL import Image

        return Image.fromarray(cv2.cvtColor(np.asarray(self.image_as_gray), cv2.COLOR_GRAY2RGB))


# Re-export PipelineStep and MissingContextError from their canonical module so
# that existing ``from pipeline.core.base import PipelineStep`` imports keep
# working without modification.  The import is placed AFTER ImageContext is fully
# defined to avoid a circular-import: base → steps/base/__init__ → stylizer_base → base.
from pipeline.steps.base.pipeline_step import MissingContextError, PipelineStep  # noqa: F401, E402

