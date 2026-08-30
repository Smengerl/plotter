#!/usr/bin/env python3
"""
main.py - Generic pipeline entry point for the pen plotter

Loads a YAML configuration file, builds a PipelineRunner from it,
and pipes the input image through all configured steps.

Usage examples
--------------
Normal execution (run from the project root)::

    python pipeline/core/main.py --config pipeline/examples/standard_pipeline.yaml --input foto.jpg --output out.gcode

List steps only without executing::

    python pipeline/core/main.py --config pipeline/examples/standard_pipeline.yaml --input foto.jpg --output out.gcode --dry-run

Custom configuration::

    python pipeline/core/main.py --config pipeline/configs/my_pipeline.yaml --input image.png --output image.gcode
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure the project root (parent of pipeline/) is on sys.path so that
# `from pipeline.core...` imports work when the script is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main",
        description="Generic pipeline runner for the pen plotter.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--config",
        type=Path,
        required=True,
        metavar="YAML",
        help="Path to pipeline configuration file (.yaml)",
    )
    p.add_argument(
        "--input",
        type=Path,
        required=False,
        default=None,
        metavar="IMAGE",
        help="Path to input image (jpg, png, …). Overrides source_path in load_image YAML config.",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=False,
        default=None,
        metavar="FILE",
        help="Path to output file (e.g. out.png, out.gcode). Overrides output_path in save_image YAML config.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List and validate steps only, do not execute",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Verbose debug output",
    )

    return p


# ---------------------------------------------------------------------------
# ImageContext Initialization
# ---------------------------------------------------------------------------

def build_initial_context(
    input_path: "Path | None",
    output_path: "Path | None",
) -> "Any":
    """
    Build an empty ImageContext with CLI-provided path overrides in metadata.

    Image loading and saving are handled exclusively by pipeline steps
    (``load_image`` and ``save_image``).  This function only injects
    the CLI ``--input`` / ``--output`` paths into metadata so that the
    steps can pick them up as runtime overrides over any static paths
    defined in the YAML config.
    """
    from pipeline.core.base import ImageContext

    metadata: dict[str, Any] = {}
    if input_path is not None:
        metadata["source_path"] = input_path
    if output_path is not None:
        metadata["output_path"] = output_path

    return ImageContext(metadata=metadata)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # --- Logging setup ---
    # Console shows INFO+ by default, DEBUG with --verbose.
    # Noisy third-party libraries are capped at WARNING regardless.
    console_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)-7s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logging.getLogger().handlers[0].setLevel(console_level)

    # Silence noisy third-party loggers
    for lib in (
        "diffusers", "transformers", "torch", "torchvision",
        "PIL", "PIL.PngImagePlugin", "PIL.TiffImagePlugin",
        "httpx", "httpcore", "urllib3", "filelock",
        "controlnet_aux", "timm", "huggingface_hub",
        "matplotlib", "onnxruntime",
    ):
        logging.getLogger(lib).setLevel(logging.WARNING)

    # --- Build runner (load + parse YAML, validate steps) ---
    from pipeline.core.runner import PipelineRunner
    try:
        runner = PipelineRunner.from_yaml(args.config, dry_run=args.dry_run)
    except (FileNotFoundError, ValueError, ImportError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    if not args.dry_run:
        logger.info("Input  : %s", args.input or "(from load_image YAML config)")
        logger.info("Output : %s", args.output or "(from save_image YAML config)")
        logger.info("Config : %s", args.config)

    ctx = build_initial_context(args.input, args.output)
    runner.run(ctx)

    return 0


if __name__ == "__main__":
    sys.exit(main())
