"""
pipeline/steps/save_image_step.py - Save the current image to disk

Counterpart to LoadImageStep: writes ``ctx.image`` (PIL) to a file.
Useful for debugging intermediate results (e.g. after style transfer)
or as the final step of an image-only pipeline.

Output path resolution (in order of priority):
  1. ctx.metadata["output_path"]  — runtime override, e.g. set via CLI --output
  2. config["output_path"]        — static path defined in the pipeline YAML

Whichever source is used is reported at DEBUG level.
If neither is set, a ValueError is raised with a clear message.

Data transport via ImageContext
--------------------------------
Reads   ctx.image                       - PIL image to save
        ctx.metadata["output_path"]     - Runtime path override (optional)
        config["output_path"]           - Static YAML path (optional fallback)
Writes  nothing — pure side effect (file on disk)
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

    **Output path resolution** (first match wins):

    1. ``ctx.metadata["output_path"]`` — runtime override, e.g. injected by
       ``main.py`` from the CLI ``--output`` argument.
       Debug output: ``"destination: CLI override → <path>"``
    2. ``config["output_path"]``       — static path in the pipeline YAML config.
       Debug output: ``"destination: YAML config → <path>"``

    If neither is set, a ``ValueError`` is raised immediately with a descriptive
    message explaining both options.

    The image format is inferred from the file extension.
    JPEG saves use ``quality`` (default 95); PNG saves use ``compress_level``
    (default 6, range 0–9).

    Config keys        Default  Meaning
    ----------------------------------------------------------
    output_path        None     Static output path (str or Path) from YAML config.
                                Overridden by ctx.metadata["output_path"] if set.
    quality            95       JPEG quality (1–95). Ignored for other formats.
    compress_level     6        PNG compression level (0=none, 9=max).
                                Ignored for other formats.
    overwrite          True     If False, raises FileExistsError when the
                                target file already exists.
    """

    name = "Save image"

    def requires(self) -> list[str]:
        return ["image"]

    def process(self, ctx: ImageContext) -> ImageContext:
        logger.info("SaveImageStep — format=%s, overwrite=%s",
                     self.config.get("format", "auto"),
                     self.config.get("overwrite", True))

        # --- Resolve output path: runtime metadata (CLI) > static YAML config ---
        runtime_path = ctx.metadata.get("output_path")
        config_path = self.config.get("output_path")

        if runtime_path:
            output_path = Path(runtime_path)
            logger.debug("SaveImageStep: destination: CLI override → %s", output_path)
        elif config_path:
            output_path = Path(config_path)
            logger.debug("SaveImageStep: destination: YAML config → %s", output_path)
        else:
            logger.error("SaveImageStep: output_path not set — provide --output or YAML output_path")
            raise ValueError(
                "SaveImageStep: output_path not set.\n"
                "  Option A — CLI override:  pass --output <path> to main.py\n"
                "  Option B — YAML config:   add 'output_path: <path>' under this step's config"
            )
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
