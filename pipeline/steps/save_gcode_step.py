"""
pipeline/steps/save_gcode_step.py - Save GCode to file

PipelineStep that writes the GCode lines from ctx.intermediates["gcode_lines"]
to a file.

Output path resolution (in order of priority):
  1. ctx.metadata["output_path"]  — runtime value, set before runner.run()
  2. config["output_path"]        — static value from pipeline config
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.core.base import ImageContext, PipelineStep

logger = logging.getLogger(__name__)


class SaveGCodeStep(PipelineStep):
    """Save GCode lines to a file.

    Output path is resolved in this order:
    1. ``ctx.metadata["output_path"]`` — set at runtime before ``runner.run()``
    2. ``config["output_path"]``       — static value in the pipeline config

    This convention keeps runtime values in ``metadata`` (dynamic) and
    static defaults in ``config``, consistent with the rest of the pipeline.

    config keys    Default  Meaning
    -----------------------------------------------
    output_path    None     Static fallback path (str or Path).
                            Overridden by metadata["output_path"] if set.
    """

    def requires(self) -> list[str]:
        return ["intermediates.gcode_lines"]

    def process(self, ctx: ImageContext) -> ImageContext:
        """Write GCode lines to file.

        Args:
            ctx: ImageContext with gcode_lines in intermediates

        Returns:
            Modified ImageContext
        """
        # Priority: runtime metadata → static config
        output_path = ctx.metadata.get("output_path") or self.config.get("output_path")
        if not output_path:
            raise ValueError(
                "SaveGCodeStep: output_path not set.  "
                "Provide it via ctx.metadata['output_path'] (runtime) "
                "or config['output_path'] (static pipeline config)."
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        gcode_lines: list[str] = ctx.intermediates["gcode_lines"]

        content = "\n".join(gcode_lines)
        output_path.write_text(content)

        logger.info("SaveGCodeStep: GCode saved to %s (%d lines)", output_path, len(gcode_lines))
        return ctx
