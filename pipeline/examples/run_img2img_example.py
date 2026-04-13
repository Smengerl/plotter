#!/usr/bin/env python3
"""
pipeline/examples/run_img2img_example.py - Run Image-to-Image style transfer examples

Demonstrates img2img style transfer using Stable Diffusion 2.1 with different
style prompts and strength parameters.

Usage:
    python run_img2img_example.py [--input <image>] [--output <dir>] [--prompt <text>] [--strength <0-1>]
    
    or directly:
    
    ./run_img2img_example.py [--input <image>] [--output <dir>] [--prompt <text>] [--strength <0-1>]

Examples:
    # Run with default config
    python run_img2img_example.py
    ./run_img2img_example.py

    # Custom prompt
    python run_img2img_example.py --prompt "watercolor painting, soft colors"

    # Different strength (lower = less modification)
    python run_img2img_example.py --strength 0.5

    # Custom image and output
    python run_img2img_example.py --input photo.jpg --output results/ --prompt "oil painting"
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Determine repo root and venv path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VENV_DIR = _REPO_ROOT / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
_SETUP_SCRIPT = _REPO_ROOT / "setup_pipeline.sh"

# If not running in venv, try to auto-setup and re-execute with venv Python
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    # Not in a venv
    if _VENV_PYTHON.exists():
        # Re-execute this script with venv Python
        sys.exit(subprocess.run([str(_VENV_PYTHON), __file__] + sys.argv[1:], cwd=_REPO_ROOT).returncode)
    elif _SETUP_SCRIPT.exists():
        # Setup venv first, then re-execute
        print(f"Virtual environment not found at {_VENV_DIR}")
        print(f"Running setup_pipeline.sh to create it...")
        result = subprocess.run(["bash", str(_SETUP_SCRIPT)], cwd=_REPO_ROOT)
        if result.returncode != 0:
            print("❌ setup_pipeline.sh failed. Please run it manually: ./setup_pipeline.sh", file=sys.stderr)
            sys.exit(1)
        # Re-execute with venv Python
        sys.exit(subprocess.run([str(_VENV_PYTHON), __file__] + sys.argv[1:], cwd=_REPO_ROOT).returncode)

# Add repo to path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def run_img2img_example(
    input_image: Path | str,
    output_dir: Path | str,
    prompt: str | None = None,
    strength: float | None = None,
) -> None:
    """Run Image-to-Image style transfer pipeline.

    Args:
        input_image: Path to input image
        output_dir: Directory to save output GCode
        prompt: Custom style prompt (optional)
        strength: Modification intensity 0.0–1.0 (optional)
    """
    from pipeline.core.base import ImageContext
    from pipeline.core.runner import PipelineRunner
    import yaml

    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        logger.error("Input image not found: %s", input_image)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load img2img config
    config_path = Path(__file__).parent.parent / "configs" / "demo_img2img_style.yaml"
    if not config_path.exists():
        logger.error("Config not found: %s", config_path)
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override prompt if provided
    if prompt:
        config["steps"][0]["config"]["prompt"] = prompt
        logger.info("Custom prompt: %s", prompt)

    # Override strength if provided
    if strength is not None:
        strength = max(0.0, min(1.0, strength))  # Clamp to 0.0–1.0
        config["steps"][0]["config"]["strength"] = strength
        logger.info("Custom strength: %.2f", strength)

    # Update output path in config
    gcode_output = output_dir / "img2img_style.gcode"

    # Load image and create context
    from PIL import Image

    image = Image.open(input_image).convert("RGB")
    logger.info("Image loaded: %s (%dx%d)", input_image, image.width, image.height)

    ctx = ImageContext(
        image=image,
        metadata={
            "source_path": input_image,
            "output_path": gcode_output,
            "source_size": (image.height, image.width),
        },
    )

    # Run pipeline
    logger.info("=== Image-to-Image Pipeline Started ===")
    logger.info("Input: %s", input_image)
    logger.info("Output: %s", gcode_output)
    logger.info("Prompt: %s", config["steps"][0]["config"]["prompt"])
    logger.info("Strength: %.2f", config["steps"][0]["config"]["strength"])

    try:
        runner = PipelineRunner(config["steps"])
        runner.run(ctx)
        logger.info("=== Pipeline Completed ===")
        logger.info("✅ GCode saved to: %s", gcode_output)
    except ImportError as e:
        logger.error("❌ Missing dependencies for Image-to-Image:")
        logger.error("   pip install diffusers transformers safetensors torch accelerate")
        logger.error("   %s", str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("❌ Pipeline failed: %s", str(e))
        sys.exit(1)


def main() -> int:
    """Parse arguments and run examples."""
    parser = argparse.ArgumentParser(
        description="Run Image-to-Image style transfer pipeline"
    )
    parser.add_argument(
        "--input",
        default=str(_REPO_ROOT / "pipeline" / "tests" / "testimage.png"),
        help="Input image path (default: pipeline/tests/testimage.png)",
    )
    parser.add_argument(
        "--output",
        default=str(_REPO_ROOT / "output"),
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Custom style prompt (overrides config default)",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=None,
        help="Modification strength 0.0–1.0 (default: 0.75 from config)",
    )

    args = parser.parse_args()

    logger.info("Image-to-Image Style Transfer Example")
    logger.info("=" * 50)
    logger.info("")

    run_img2img_example(
        input_image=args.input,
        output_dir=args.output,
        prompt=args.prompt,
        strength=args.strength,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
