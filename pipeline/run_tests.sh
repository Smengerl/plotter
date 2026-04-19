#!/usr/bin/env bash
# pipeline/run_tests.sh — Run pipeline tests inside the project's .venv
#
# This script uses the Python interpreter in `.venv/bin/python` (created by
# pipeline/setup_pipeline.sh) to run the canonical test orchestrator
# `pipeline/tests/run_all_tests.py`. Any arguments are forwarded unchanged.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT/.venv/bin/python"
RUNNER="$ROOT/pipeline/tests/run_all_tests.py"

if [[ ! -f "$RUNNER" ]]; then
  echo "Error: test runner not found at: $RUNNER" >&2
  exit 2
fi

if [[ -x "$VENV_PY" ]]; then
  exec "$VENV_PY" "$RUNNER" "$@"
else
  cat >&2 <<-MSG
Error: project virtual environment not found or missing Python at:
  $VENV_PY

Create the venv via the project's setup script (for example):
  ./pipeline/setup_pipeline.sh

Or run the test runner with your active Python environment:
  python $RUNNER --skip-stylizers
MSG
  exit 3
fi
