#!/usr/bin/env python3
"""
main.py - Generic pipeline entry point for the pen plotter

Loads a YAML configuration file, builds a PipelineRunner from it,
and pipes the input image through all configured steps.

Usage examples
--------------
Normal execution (run from the project root)::

    python pipeline/main.py --config pipeline/configs/standard_pipeline.yaml --input foto.jpg --output out.gcode

List steps only without executing::

    python pipeline/main.py --config pipeline/configs/standard_pipeline.yaml --input foto.jpg --output out.gcode --dry-run

Custom configuration::

    python pipeline/main.py --config pipeline/configs/my_pipeline.yaml --input image.png --output image.gcode
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure the project root (parent of pipeline/) is on sys.path so that
# `from pipeline.core...` imports work when the script is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
# Helper Functions
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> list[dict[str, Any]]:
    """
    Reads the YAML configuration file and returns the steps list.

    Expects the following format::

        steps:
          - step: stylise
            config: {style: canny}
          - step: vectorise
            config: {}

    Raises
    ------
    SystemExit : if the file does not exist, is not valid YAML,
                 or is missing the ``steps`` field.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        logger.error("PyYAML is not installed: pip install pyyaml")
        sys.exit(1)

    if not config_path.exists():
        logger.error("Configuration file not found: %s", config_path)
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            logger.error("Invalid YAML in %s: %s", config_path, exc)
            sys.exit(1)

    if not isinstance(data, dict) or "steps" not in data:
        logger.error(
            "Configuration in %s must be a dict with 'steps' key.", config_path
        )
        sys.exit(1)

    return data["steps"]


def print_plan(steps_config: list[dict[str, Any]], input_path: "Path | None", output_path: "Path | None") -> None:
    """Prints the execution plan in human-readable format to stdout (for --dry-run)."""
    print()
    print("=== Pipeline Plan (--dry-run) ===")
    print(f"  Input  : {input_path or '(from load_image YAML config)'}")
    print(f"  Output : {output_path or '(from save_image YAML config)'}")
    print(f"  Steps  : {len(steps_config)}")
    print()

    active = [e for e in steps_config if e.get("enabled", True)]
    skipped = [e for e in steps_config if not e.get("enabled", True)]

    for i, entry in enumerate(active, start=1):
        name = entry["step"]
        config = entry.get("config", {})
        print(f"  [{i}] {name}")
        for key, val in config.items():
            print(f"        {key}: {val!r}")

    if skipped:
        print()
        print("  Skipped (enabled: false):")
        for entry in skipped:
            print(f"    - {entry['step']}")

    print()
    print("No steps were executed.")
    print()


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

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # --- Load configuration ---
    steps_config = load_config(args.config)
    logger.debug("Configuration loaded: %s  (%d entries)", args.config, len(steps_config))

    # --- Dry-run: print plan only, do not execute ---
    if args.dry_run:
        print_plan(steps_config, args.input, args.output)
        return 0

    # --- Build runner (validates registry keys immediately) ---
    from pipeline.core.runner import PipelineRunner
    try:
        runner = PipelineRunner(steps_config)
    except KeyError as exc:
        logger.error("Invalid pipeline configuration: %s", exc)
        return 1

    logger.info("=== Pipeline started ===")
    logger.info("Input  : %s", args.input or "(from load_image YAML config)")
    logger.info("Output : %s", args.output or "(from save_image YAML config)")
    logger.info("Config : %s", args.config)

    # --- Build context with CLI path overrides and execute pipeline ---
    # Image loading and saving are handled by load_image / save_image steps.
    ctx = build_initial_context(args.input, args.output)
    runner.run(ctx)

    logger.info("=== Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
