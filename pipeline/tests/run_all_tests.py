#!/usr/bin/env python3
"""
pipeline/tests/run_all_tests.py - Unified test runner

Runs unit tests (pytest) for files in this folder and then optionally
runs the stylizer smoke tests (pipeline/tests/run_all_stylizers.py).

Usage:
    python pipeline/tests/run_all_tests.py [--skip-stylizers] [--pytest-args "-k test_x"]

This script is intended to be invoked from the project root. It uses
`sys.executable -m pytest` so it automatically runs inside the active
Python environment (preferably the project's .venv created by
`./setup_pipeline.sh`).

Behavior:
 - Finds unit test files matching `test_*.py` in pipeline/tests/ and
   runs pytest for them.
 - Then runs the pipeline config smoke tests (run_all_stylizers.py) which
   execute the sample YAML pipelines and write outputs into
   pipeline/tests/output/.

Exit code: non-zero if any step fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
RUN_STYLIZERS = ROOT / "run_all_stylizers.py"


def find_unit_tests() -> List[Path]:
    """Return list of test files to run with pytest.

    Excludes runner scripts and the pipeline_configs directory.
    """
    files: List[Path] = []
    for p in sorted(ROOT.glob("test_*.py")):
        # skip the orchestrator scripts if present
        if p.name in ("run_all_tests.py", "run_all_stylizers.py"):
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


def run_stylizers(output_dir: Path, image: Path | None = None) -> int:
    if not RUN_STYLIZERS.exists():
        print("Stylizer smoke test runner not found; skipping stylizer tests.")
        return 0

    cmd = [sys.executable, str(RUN_STYLIZERS)]
    if image:
        cmd += ["--image", str(image)]
    cmd += ["--output-dir", str(output_dir)]

    print("Running stylizer smoke tests:", " ".join(cmd))
    res = subprocess.run(cmd)
    return res.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified test runner for pipeline/tests")
    parser.add_argument("--skip-stylizers", action="store_true", help="Skip the stylizer smoke tests")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output", help="Output dir for stylizer results")
    parser.add_argument("--image", type=Path, default=None, help="Optional input image for stylizer smoke tests")
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

    if args.skip_stylizers:
        print("Skipping stylizer smoke tests (--skip-stylizers set)")
        sys.exit(0)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    styl_code = run_stylizers(args.output_dir, args.image)
    if styl_code != 0:
        print("Stylizer smoke tests reported errors.")
        sys.exit(styl_code)

    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
