#!/usr/bin/env bash
# pipeline/scripts/run_server.sh — Start the Plotter Pipeline Manager GUI server.
#
# The pipeline package is installed as an editable install (pip install -e),
# so no manual PYTHONPATH manipulation is needed.
#
# Usage (from anywhere):
#   ./pipeline/scripts/run_server.sh [--input-dir input] [--tools-dir configs] [--port 8080] …
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=helpers/env.sh
source "$SCRIPT_DIR/helpers/env.sh"

activate_venv
resolve_venv_python

exec "$PYTHON" -m pipeline.gui "$@"
