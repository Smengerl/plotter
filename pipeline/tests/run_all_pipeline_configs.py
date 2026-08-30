#!/usr/bin/env python3
"""
pipeline/tests/run_all_pipeline_configs.py - Pipeline-config smoke test

Runs every ``*.yaml`` in ``pipeline/tests/pipeline_configs/`` through the
normal ``PipelineRunner`` against a test image and reports pass / skip /
error for each. Intermediate outputs (PNG / SVG / GCODE, when produced) are
written under ``pipeline/tests/output/<config_stem>/``.

The runner provides only ``metadata["source_path"]`` — it does NOT preload
``ctx.image`` — so every config must be self-contained (start with a
``load_image`` step).

Configs whose optional dependency is missing (e.g. ``diffusers`` for the
ControlNet / Img2Img configs) are reported as *skipped*, not failed.

Usage (from the repo root):

    python pipeline/tests/run_all_pipeline_configs.py
    python pipeline/tests/run_all_pipeline_configs.py --fast          # CPU-only configs
    python pipeline/tests/run_all_pipeline_configs.py --image foto.jpg
    python pipeline/tests/run_all_pipeline_configs.py --config pipeline/tests/pipeline_configs/stylize_canny.yaml
    python pipeline/tests/run_all_pipeline_configs.py --output-dir /tmp/plotter_out

Exit code: non-zero if any config errors.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import yaml

from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner
from pipeline.steps.vectorize_step import paths_to_svg

# ── Paths ────────────────────────────────────────────────────────────────────
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent.parent
_CONFIGS_DIR = _TESTS_DIR / "pipeline_configs"
_INPUT_DIR = _REPO_ROOT / "pipeline" / "input"

# Config stems that need neither a model download nor a GPU.
_FAST_CONFIGS = {"stylize_canny", "stylize_xdog", "stylize_adaptive", "vectorize"}

# ── Terminal colours ─────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _find_configs(configs_dir: Path) -> list[Path]:
    """Return all ``*.yaml`` files in *configs_dir*, sorted."""
    return sorted(configs_dir.glob("*.yaml"))


def _config_name(yaml_path: Path) -> str:
    """``stylize_canny.yaml`` -> ``stylize_canny``."""
    return yaml_path.stem


def _print_header(configs: list[Path]) -> None:
    names = ", ".join(_config_name(c) for c in configs)
    print(f"\n{BOLD}{'-' * 60}{RESET}")
    print(f"{BOLD}  Pipeline-config smoke test{RESET}")
    print(f"{'-' * 60}")
    print(f"  Configs : {names}")


def _run_config(
    yaml_path: Path,
    image_path: Path,
    output_dir: Path,
) -> tuple[bool | None, str]:
    """Execute a single config YAML.

    Returns ``(True, msg)`` on success, ``(None, msg)`` if an optional
    dependency is missing, ``(False, msg)`` on an actual error.
    """
    name = _config_name(yaml_path)
    run_dir = output_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)

    png_path = run_dir / f"{image_path.stem}.png"
    svg_path = run_dir / f"{image_path.stem}.svg"
    gcode_path = run_dir / f"{image_path.stem}.gcode"

    try:
        runner = PipelineRunner.from_yaml(yaml_path)

        # Provide only the source path; LoadImageStep loads the image itself.
        ctx = ImageContext(metadata={"source_path": image_path})

        t0 = time.monotonic()
        ctx = runner.run(ctx)
        elapsed = time.monotonic() - t0

        binary = ctx.intermediates.get("binary")
        paths = ctx.intermediates.get("paths", [])
        gcode_lines: list[str] = ctx.intermediates.get("gcode_lines", [])

        if binary is not None:
            cv2.imwrite(str(png_path), binary)
            shape = binary.shape[:2]
        elif ctx.has_image:
            ctx.image.save(png_path)
            shape = (ctx.image.height, ctx.image.width)
        else:
            shape = None

        if paths and shape is not None:
            paths_to_svg(paths, shape, svg_path)

        if gcode_lines:
            gcode_path.write_text("\n".join(gcode_lines) + "\n", encoding="utf-8")

        return True, (
            f"{elapsed:.2f}s  ->  {run_dir.name}/  "
            f"({len(paths)} paths, {len(gcode_lines)} GCode lines)"
        )

    except ImportError as exc:
        return None, f"skipped (missing dependency: {str(exc).splitlines()[0]})"

    except Exception as exc:  # noqa: BLE001
        return False, f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every pipeline_configs/*.yaml through the PipelineRunner."
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=_INPUT_DIR / "testimage.png",
        metavar="PATH",
        help="Input image (default: pipeline/input/testimage.png)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="YAML",
        help="Run a single config file instead of the whole directory",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Only run the CPU-only configs (no model downloads)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_TESTS_DIR / "output",
        metavar="DIR",
        help="Output directory (default: pipeline/tests/output/)",
    )
    args = parser.parse_args()

    image_path: Path = args.image.resolve()
    output_dir: Path = args.output_dir.resolve()

    if not image_path.exists():
        print(f"{RED}Error: input image not found: {image_path}{RESET}")
        sys.exit(1)

    if args.config:
        configs = [args.config.resolve()]
    else:
        configs = _find_configs(_CONFIGS_DIR)
        if args.fast:
            configs = [c for c in configs if _config_name(c) in _FAST_CONFIGS]
        if not configs:
            print(f"{RED}Error: no configs found in {_CONFIGS_DIR}{RESET}")
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    _print_header(configs)
    print(f"  Image   : {image_path}")
    print(f"  Output  : {output_dir}")
    print(f"{'-' * 60}\n")

    results: list[tuple[str, bool | None, str]] = []

    for yaml_path in configs:
        name = _config_name(yaml_path)
        print(f"  [{name:<20}]  ... ", end="", flush=True)
        success, msg = _run_config(yaml_path, image_path, output_dir)
        symbol = {True: f"{GREEN}OK{RESET}", None: f"{YELLOW}~ {RESET}", False: f"{RED}X {RESET}"}[success]
        print(f"{symbol}  {msg}")
        results.append((name, success, msg))

    n_ok = sum(1 for _, s, _ in results if s is True)
    n_skip = sum(1 for _, s, _ in results if s is None)
    n_err = sum(1 for _, s, _ in results if s is False)

    print(f"\n{'-' * 60}")
    print(
        f"  Results: {GREEN}{n_ok} ok{RESET}  "
        f"{YELLOW}{n_skip} skipped{RESET}  "
        f"{RED}{n_err} errors{RESET}"
    )
    print(f"{'-' * 60}\n")

    sys.exit(1 if n_err > 0 else 0)


if __name__ == "__main__":
    main()
