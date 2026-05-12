#!/usr/bin/env bash
# pipeline/scripts/setup_pipeline.sh — Set up Python virtual environment for the pipeline.
#
# Usage (run from anywhere — the script finds the project root itself):
#   ./pipeline/scripts/setup_pipeline.sh                     # installs extras: gui (default)
#   EXTRAS=gui,diffusers ./pipeline/scripts/setup_pipeline.sh  # include SD backends
#   SYS_PYTHON=python3.12 ./pipeline/scripts/setup_pipeline.sh  # pin a specific interpreter
#
# Supported Python: 3.11, 3.12, 3.13  (vpype 1.15.x does not support 3.14+)
# Install Python 3.13 on macOS:  brew install python@3.13
set -euo pipefail

# ── Locate project root & load shared helpers ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=helpers/env.sh
source "$SCRIPT_DIR/helpers/env.sh"

# Allow SYS_PYTHON env-var override before version check
# (named SYS_PYTHON to avoid conflict with the venv PYTHON set by resolve_venv_python)
[[ -n "${SYS_PYTHON:-}" ]] || true   # already set by env.sh; user may export before running

# ── Python version gate ───────────────────────────────────────────────────────
check_python_version

echo "=== Image-to-GCode Pipeline Setup ==="
echo "Project root:  $ROOT_DIR"
echo "Python:        $("$SYS_PYTHON" --version 2>&1)  ($SYS_PYTHON)"

# ── Create or reuse virtual environment ──────────────────────────────────────
EXTRAS="${EXTRAS:-gui}"

if [[ -d "$VENV" ]]; then
  EXISTING_PY="$("$VENV_BIN/python" --version 2>&1 || echo 'unknown')"
  echo "Existing venv: $EXISTING_PY"
  echo "  (To recreate: rm -rf .venv && ./pipeline/scripts/setup_pipeline.sh)"
  activate_venv   # activate existing venv via helper (platform-independent)
  echo ""
  echo "--- Upgrading pip & reinstalling pipeline[${EXTRAS}] ---"
  resolve_venv_pip
  "$PIP" install --upgrade pip setuptools wheel --quiet
  "$PIP" install -e "$ROOT_DIR/pipeline[${EXTRAS}]"
else
  activate_venv --auto-create "$EXTRAS"
fi

resolve_venv_python
resolve_venv_pip

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Python:  $("$PYTHON" --version 2>&1)"
echo "vpype:   $("$PYTHON" -c 'import vpype; print(vpype.__version__)' 2>/dev/null || echo 'not installed')"
echo ""
if is_windows; then
  echo "Activate venv:     .venv\\Scripts\\activate"
  echo "Run tests:         .venv\\Scripts\\pytest pipeline\\tests\\"
  echo "Start GUI server:  pipeline\\scripts\\run_server.sh"
else
  echo "Activate venv:     source .venv/bin/activate"
  echo "Run tests:         ./pipeline/scripts/run_tests.sh"
  echo "Start GUI server:  ./pipeline/scripts/run_server.sh"
fi
echo ""
echo "Optional extras:"
echo "  SD backends (ControlNet / Img2Img):"
echo "    EXTRAS=gui,diffusers ./pipeline/scripts/setup_pipeline.sh"
echo "  GPU acceleration (CUDA):"
echo "    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118"
