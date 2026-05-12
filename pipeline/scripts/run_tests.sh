#!/usr/bin/env bash
# pipeline/scripts/run_tests.sh — Run pipeline tests inside the project's venv.
#
# Usage (from anywhere):
#   ./pipeline/scripts/run_tests.sh                 # all tests
#   ./pipeline/scripts/run_tests.sh -k stylize      # filter by name
#   ./pipeline/scripts/run_tests.sh --skip-stylizers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=helpers/env.sh
source "$SCRIPT_DIR/helpers/env.sh"

activate_venv
resolve_venv_python

exec "$PYTHON" -m pytest "$ROOT_DIR/pipeline/tests/" "$@"
