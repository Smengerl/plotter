#!/usr/bin/env python3
"""
pipeline/tests/run_all_tests.py - Unified test runner

Runs the pytest unit tests, then the pipeline-config smoke test
(pipeline/tests/run_all_pipeline_configs.py).

Usage:
    python pipeline/tests/run_all_tests.py [--skip-smoke] [--fast] [--pytest-args "-k test_x"]

Invoke from the repo root. Uses `sys.executable -m pytest` so it runs inside
the active environment (the project's .venv — `pip install -e pipeline/`).

Exit code: non-zero if any step fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
RUN_SMOKE = ROOT / "run_all_pipeline_configs.py"


def find_unit_tests() -> List[Path]:
    """Return the `test_*.py` files to run with pytest."""
    files: List[Path] = []
    for p in sorted(ROOT.glob("test_*.py")):
        if p.name in ("run_all_tests.py", "run_all_pipeline_configs.py"):
            continue
        files.append(p)
    return files


def run_pytest(test_files: List[Path], extra_args: List[str]) -> int:
    cmd = [sys.executable, "-m", "pytest", "-v"]
    if test_files:
        cmd += [str(p) for p in test_files]
    else:
        # fallback: run all tests in directory
        cmd += [str(ROOT)]
    if extra_args:
        cmd += extra_args

    print("Running pytest:", " ".join(cmd))
    res = subprocess.run(cmd)
    return res.returncode


def run_smoke(output_dir: Path, image: Path | None, fast: bool) -> int:
    if not RUN_SMOKE.exists():
        print("Smoke test runner not found; skipping.")
        return 0

    cmd = [sys.executable, str(RUN_SMOKE), "--output-dir", str(output_dir)]
    if image:
        cmd += ["--image", str(image)]
    if fast:
        cmd += ["--fast"]

    print("Running pipeline-config smoke test:", " ".join(cmd))
    res = subprocess.run(cmd)
    return res.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified test runner for pipeline/tests")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip the pipeline-config smoke test")
    parser.add_argument("--fast", action="store_true", help="Smoke test: CPU-only configs (no model downloads)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output", help="Output dir for smoke-test results")
    parser.add_argument("--image", type=Path, default=None, help="Optional input image for the smoke test")
    parser.add_argument("--pytest-args", type=str, default="", help="Extra args to forward to pytest (quoted string)")
    args = parser.parse_args()

    extra_pytest_args: List[str] = []
    if args.pytest_args:
        # naive split; recommend users provide simple flags
        extra_pytest_args = args.pytest_args.split()

    unit_tests = find_unit_tests()
    print(f"Found {len(unit_tests)} unit test files")

    code = run_pytest(unit_tests, extra_pytest_args)
    if code != 0:
        print("Pytest failed; aborting further tests.")
        sys.exit(code)

    if args.skip_smoke:
        print("Skipping the pipeline-config smoke test (--skip-smoke set)")
        sys.exit(0)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    smoke_code = run_smoke(args.output_dir, args.image, args.fast)
    if smoke_code != 0:
        print("Pipeline-config smoke test reported errors.")
        sys.exit(smoke_code)

    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
