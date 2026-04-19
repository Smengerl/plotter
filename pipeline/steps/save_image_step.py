"""
pipeline/steps/save_image_step.py - Save the current image to disk

Counterpart to LoadImageStep: writes ``ctx.image`` (PIL) to a file.
Useful for debugging intermediate results (e.g. after style transfer)
or as the final step of an image-only pipeline.

Output path resolution (in order of priority):
  1. ctx.metadata["output_path"]  — runtime value, set before runner.run()
  2. config["output_path"]        — static value from pipeline config

Data transport via ImageContext
--------------------------------
Reads   ctx.image                      - PIL image to save
        ctx.metadata["output_path"]    - runtime output path (optional)
Writes  nothing  — pure side effect (file on disk)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.core.base import ImageContext, PipelineStep

logger = logging.getLogger(__name__)

# Supported PIL save formats, mapped to their canonical extension
_SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class SaveImageStep(PipelineStep):
    """
    Save ``ctx.image`` to a file on disk.

    The output path is resolved in this order:
    1. ``ctx.metadata["output_path"]`` — set at runtime before ``runner.run()``
    2. ``config["output_path"]``       — static value in the pipeline config

    The image format is inferred from the file extension.
    JPEG saves use ``quality`` (default 95); PNG saves use ``compress_level``
    (default 6, range 0–9).

    Config keys        Default  Meaning
    ----------------------------------------------------------
    output_path        None     Static fallback output path (str or Path).
                                Overridden by metadata["output_path"] if set.
    quality            95       JPEG quality (1–95). Ignored for other formats.
    compress_level     6        PNG compression level (0=none, 9=max).
                                Ignored for other formats.
    overwrite          True     If False, raises FileExistsError when the
                                target file already exists.
    """

    def requires(self) -> list[str]:
        return ["image"]

    def process(self, ctx: ImageContext) -> ImageContext:
        # --- Resolve output path: runtime metadata > static config ---
        output_path = ctx.metadata.get("output_path") or self.config.get("output_path")
        if not output_path:
            raise ValueError(
                "SaveImageStep: output_path not set.  "
                "Provide it via ctx.metadata['output_path'] (runtime) "
                "or config['output_path'] (static pipeline config)."
            )

        output_path = Path(output_path)
        suffix = output_path.suffix.lower()

        if suffix not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"SaveImageStep: unsupported file extension '{suffix}'.  "
                f"Supported: {', '.join(sorted(_SUPPORTED_FORMATS))}"
            )

        # --- Overwrite guard ---
        overwrite: bool = bool(self.config.get("overwrite", True))
        if not overwrite and output_path.exists():
            raise FileExistsError(
                f"SaveImageStep: target file already exists and overwrite=False: {output_path}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Format-specific save options ---
        save_kwargs: dict[str, Any] = {}
        if suffix in (".jpg", ".jpeg"):
            save_kwargs["quality"] = int(self.config.get("quality", 95))
            # JPEG does not support alpha — ensure RGB
            image = ctx.image.convert("RGB")  # type: ignore[union-attr]
        elif suffix == ".png":
            save_kwargs["compress_level"] = int(self.config.get("compress_level", 6))
            image = ctx.image  # type: ignore[assignment]
        else:
            image = ctx.image  # type: ignore[assignment]

        image.save(output_path, **save_kwargs)

        logger.info(
            "SaveImageStep: image saved to %s (%dx%d px, mode=%s)",
            output_path, image.width, image.height, image.mode,
        )
        return ctx
