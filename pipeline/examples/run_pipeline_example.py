#!/usr/bin/env python3
"""
pipeline/examples/run_pipeline_example.py

Direct Python example for running the pipeline programmatically
without using the CLI (main.py).

Useful for:
- Integration in other Python projects
- Custom preprocessing/postprocessing
- Debugging pipeline steps
- Batch processing
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo to path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import yaml
from PIL import Image

from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner


def run_standard_pipeline(input_image_path: Path, output_gcode_path: Path) -> None:
    """
    Example 1: Run the standard pipeline (Informative Stylizer).

    Args:
        input_image_path: Path to input image
        output_gcode_path: Path to save GCode output
    """
    print("=" * 60)
    print("Example 1: Standard Pipeline (Informative Stylizer)")
    print("=" * 60)

    # Load configuration
    config_path = _REPO_ROOT / "pipeline" / "configs" / "standard_pipeline.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create pipeline runner
    runner = PipelineRunner(config["steps"])

    # Load image and create context
    img = Image.open(input_image_path)
    ctx = ImageContext(img)

    # Run pipeline
    print(f"Input: {input_image_path} ({img.size[0]}×{img.size[1]} px)")
    print(f"Running {len(config['steps'])} steps...")
    ctx = runner.run(ctx)

    # Save result
    ctx.save_gcode(output_gcode_path)
    print(f"✅ Output: {output_gcode_path}")
    print()


def run_controlnet_pipeline(
    input_image_path: Path, output_gcode_path: Path, prompt: str = None
) -> None:
    """
    Example 2: Run ControlNet style transfer pipeline.

    Args:
        input_image_path: Path to input image
        output_gcode_path: Path to save GCode output
        prompt: Custom style prompt (optional)
    """
    print("=" * 60)
    print("Example 2: ControlNet Style Transfer")
    print("=" * 60)

    # Load demo configuration
    config_path = _REPO_ROOT / "pipeline" / "configs" / "demo_controlnet_style.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override prompt if provided
    if prompt:
        config["steps"][0]["config"]["prompt"] = prompt
        print(f"Custom prompt: {prompt}")

    # Create pipeline runner
    runner = PipelineRunner(config["steps"])

    # Load image and create context
    img = Image.open(input_image_path)
    ctx = ImageContext(img)

    # Run pipeline
    print(f"Input: {input_image_path} ({img.size[0]}×{img.size[1]} px)")
    print(f"Running {len(config['steps'])} steps...")
    print("Note: First run downloads ~4GB models (ControlNet + SD 1.5)")
    ctx = runner.run(ctx)

    # Save result
    ctx.save_gcode(output_gcode_path)
    print(f"✅ Output: {output_gcode_path}")
    print()


def inspect_pipeline_config(config_path: Path) -> None:
    """
    Example 3: Inspect pipeline configuration without running.

    Args:
        config_path: Path to configuration YAML file
    """
    print("=" * 60)
    print(f"Example 3: Inspect Pipeline - {config_path.name}")
    print("=" * 60)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    print(f"Total steps: {len(config['steps'])}")
    print()

    for i, step_config in enumerate(config["steps"], 1):
        step_name = step_config["step"]
        enabled = step_config.get("enabled", True)
        status = "✅ Enabled" if enabled else "⏸️  Disabled"

        print(f"Step {i}: {step_name} {status}")

        # Show config keys
        step_cfg = step_config.get("config", {})
        if step_cfg:
            for key, value in step_cfg.items():
                # Truncate long values
                val_str = str(value)
                if len(val_str) > 50:
                    val_str = val_str[:47] + "..."
                print(f"  - {key}: {val_str}")

        print()


def run_all_test_pipelines(input_image_path: Path, output_dir: Path) -> None:
    """
    Example 4: Run all test pipeline configurations.

    Args:
        input_image_path: Path to input image
        output_dir: Directory to save outputs
    """
    print("=" * 60)
    print("Example 4: Run All Test Pipelines")
    print("=" * 60)

    test_config_dir = _REPO_ROOT / "pipeline" / "tests" / "pipeline_configs"
    config_files = sorted(test_config_dir.glob("stylize_*.yaml"))

    print(f"Found {len(config_files)} test pipelines")
    print()

    output_dir.mkdir(parents=True, exist_ok=True)

    for config_path in config_files:
        print(f"Running: {config_path.stem}")

        # Load config
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Create runner
        runner = PipelineRunner(config["steps"])

        # Load image
        img = Image.open(input_image_path)
        ctx = ImageContext(img)

        # Run
        try:
            ctx = runner.run(ctx)
            output_path = output_dir / f"{config_path.stem}.gcode"
            ctx.save_gcode(output_path)
            print(f"  ✅ {output_path}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        print()

    print("✅ All test pipelines completed")
    print()


def main():
    """Run all examples."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline execution examples"
    )
    parser.add_argument(
        "example",
        nargs="?",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Which example to run (1–4)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_REPO_ROOT / "pipeline" / "tests" / "testimage.png",
        help="Input image path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "output",
        help="Output directory",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Custom prompt for ControlNet (example 2 only)",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input image not found: {args.input}")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    if args.example == 1:
        run_standard_pipeline(args.input, args.output / "standard_pipeline.gcode")

    elif args.example == 2:
        run_controlnet_pipeline(
            args.input, args.output / "controlnet_style.gcode", args.prompt
        )

    elif args.example == 3:
        inspect_pipeline_config(_REPO_ROOT / "pipeline" / "configs" / "standard_pipeline.yaml")

    elif args.example == 4:
        run_all_test_pipelines(args.input, args.output)

    print("=" * 60)
    print("✅ Examples Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
