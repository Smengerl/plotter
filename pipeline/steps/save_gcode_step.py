"""
pipeline/steps/save_gcode_step.py - Save GCode to file

PipelineStep that writes the GCode lines from ctx.intermediates["gcode_lines"]
to a file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.core.base import ImageContext, PipelineStep

logger = logging.getLogger(__name__)


class SaveGCodeStep(PipelineStep):
    """Save GCode lines to a file."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize SaveGCodeStep.

        Args:
            config: Dictionary with optional keys:
                - output_path: Path to write GCode file (str or Path)
                  If not provided, uses ctx.output_path
        """
        super().__init__(config or {})

    def process(self, ctx: ImageContext) -> ImageContext:
        """Write GCode lines to file.

        Args:
            ctx: ImageContext with gcode_lines in intermediates

        Returns:
            Modified ImageContext
        """
        # Get output path from metadata or config
        output_path = self.config.get("output_path")
        if not output_path:
            output_path = ctx.metadata.get("output_path")
        if not output_path:
            raise ValueError("SaveGCodeStep: output_path not provided in config or metadata")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get GCode lines
        gcode_lines = ctx.intermediates.get("gcode_lines", [])
        if not gcode_lines:
            logger.warning("SaveGCodeStep: No GCode lines found in context")
            return ctx

        # Write file
        content = "\n".join(gcode_lines)
        output_path.write_text(content)

        logger.info("SaveGCodeStep: GCode saved to %s (%d lines)", output_path, len(gcode_lines))
        return ctx
