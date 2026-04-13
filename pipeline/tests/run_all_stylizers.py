#!/usr/bin/env python3
"""
pipeline/tests/run_all_stylizers.py - Smoke test of all stylizers

Processes an input image once with each stylizer config YAML
from ``pipeline/configs/stylize_*.yaml`` via the normal PipelineRunner
and saves results (PNG + SVG + GCODE) in ``output/``.

Usage
-----
    # from the plotter root directory:
    python pipeline/tests/run_all_stylizers.py

    # specific image:
    python pipeline/tests/run_all_stylizers.py --image foto.jpg

    # test single config:
    python pipeline/tests/run_all_stylizers.py --config pipeline/configs/stylize_canny.yaml

    # specify output directory:
    python pipeline/tests/run_all_stylizers.py --output-dir /tmp/plotter_out

Output
------
    pipeline/tests/output/
        stylize_canny/      testimage.png  testimage.svg  testimage.gcode
        stylize_xdog/       testimage.png  …
        stylize_adaptive/   testimage.png  …
        stylize_hed/        testimage.png  …  (only if controlnet_aux installed)
        stylize_dexined/    testimage.png  …  (only if controlnet_aux installed)
        stylize_lineart/    testimage.png  …  (only if controlnet_aux installed)
        stylize_informative/testimage.png  …
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import yaml

# ---------------------------------------------------------------------------
# Path bootstrap: to make imports work regardless of where the script
# is launched from (from tests/, from pipeline/ or from project root).
# ---------------------------------------------------------------------------
_TESTS_DIR    = Path(__file__).resolve().parent
_PIPELINE_DIR = _TESTS_DIR.parent
_PLOTTER_ROOT = _PIPELINE_DIR.parent
for _p in (_PLOTTER_ROOT, _PIPELINE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline.core.base import ImageContext      # noqa: E402
from pipeline.core.runner import PipelineRunner  # noqa: E402
from pipeline.steps.vectorize_step import paths_to_svg  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONFIGS_DIR = _TESTS_DIR / "pipeline_configs"

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _find_stylizer_configs(configs_dir: Path) -> list[Path]:
    """Returns all ``stylize_*.yaml`` files sorted."""
    return sorted(configs_dir.glob("stylize_*.yaml"))


def _config_name(yaml_path: Path) -> str:
    """``stylize_canny.yaml`` → ``canny``"""
    return yaml_path.stem.removeprefix("stylize_")


def _print_header(configs: list[Path]) -> None:
    names = ", ".join(_config_name(c) for c in configs)
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  Stylizer Smoke Test{RESET}")
    print(f"{'─' * 60}")
    print(f"  Stylizers : {names}")


def _run_config(
    yaml_path: Path,
    image_path: Path,
    output_dir: Path,
) -> tuple[bool | None, str]:
    """
    Executes a single YAML pipeline and saves PNG + SVG + GCODE.

    Returns ``(True, msg)`` on success,
            ``(None, msg)`` if optional dependency is missing, and
            ``(False, msg)`` on actual error.
    """
    from PIL import Image as _Image

    name = _config_name(yaml_path)
    run_dir = output_dir / f"stylize_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    png_path   = run_dir / f"{image_path.stem}.png"
    svg_path   = run_dir / f"{image_path.stem}.svg"
    gcode_path = run_dir / f"{image_path.stem}.gcode"

    try:
        # Load YAML and inject source_path into the first step
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        steps_cfg: list[dict] = cfg["steps"]
        steps_cfg[0].setdefault("config", {})["source_path"] = image_path

        runner = PipelineRunner(steps_cfg)

        ctx = ImageContext(
            image=_Image.open(image_path).convert("RGB"),
            metadata={"source_path": image_path},
        )

        t0 = time.monotonic()
        ctx = runner.run(ctx)
        elapsed = time.monotonic() - t0

        binary = ctx.intermediates["binary"]
        paths  = ctx.intermediates.get("paths", [])

        # PNG
        cv2.imwrite(str(png_path), binary)

        # SVG
        if paths:
            paths_to_svg(paths, binary.shape[:2], svg_path)

        # GCODE
        gcode_lines: list[str] = ctx.intermediates.get("gcode_lines", [])
        if gcode_lines:
            gcode_path.write_text("\n".join(gcode_lines) + "\n", encoding="utf-8")

        return True, (
            f"{elapsed:.2f}s  →  {run_dir.name}/"
            f"  ({len(paths)} paths, {len(gcode_lines)} GCode lines)"
        )

    except ImportError as exc:
        short = str(exc).split("\n")[0]
        return None, f"skipped (missing dependency: {short})"  # type: ignore[return-value]

    except Exception as exc:  # noqa: BLE001
        return False, f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Main Program
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executes all stylize_*.yaml configs via the PipelineRunner."
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=_TESTS_DIR / "testimage.png",
        metavar="PATH",
        help="Input image (default: pipeline/tests/testimage.png)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="YAML",
        help="Single config file (default: all stylize_*.yaml)",
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
        print(f"{RED}Error: Input image not found: {image_path}{RESET}")
        sys.exit(1)

    # Build config list
    if args.config:
        configs = [args.config.resolve()]
    else:
        configs = _find_stylizer_configs(_CONFIGS_DIR)
        if not configs:
            print(f"{RED}Error: No stylize_*.yaml in {_CONFIGS_DIR}{RESET}")
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    _print_header(configs)
    print(f"  Image       : {image_path}")
    print(f"  Output      : {output_dir}")
    print(f"  Configs     : {_CONFIGS_DIR}")
    print(f"{'─' * 60}\n")

    results: list[tuple[str, bool | None, str]] = []

    for yaml_path in configs:
        name = _config_name(yaml_path)
        print(f"  [{name:<14}]  … ", end="", flush=True)

        success, msg = _run_config(yaml_path, image_path, output_dir)

        if success is True:
            symbol = f"{GREEN}✓{RESET}"
        elif success is None:
            symbol = f"{YELLOW}~{RESET}"
        else:
            symbol = f"{RED}✗{RESET}"

        print(f"{symbol}  {msg}")
        results.append((name, success, msg))

    # Summary
    n_ok   = sum(1 for _, s, _ in results if s is True)
    n_skip = sum(1 for _, s, _ in results if s is None)
    n_err  = sum(1 for _, s, _ in results if s is False)

    print(f"\n{'─' * 60}")
    print(
        f"  Results: {GREEN}{n_ok} successful{RESET}  "
        f"{YELLOW}{n_skip} skipped{RESET}  "
        f"{RED}{n_err} errors{RESET}"
    )
    print(f"{'─' * 60}\n")

    if n_ok > 0:
        print(f"  Saved files in: {output_dir}\n")

    sys.exit(1 if n_err > 0 else 0)


if __name__ == "__main__":
    main()

