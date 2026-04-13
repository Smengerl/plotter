#!/usr/bin/env bash
# setup_pipeline.sh — Set up Python virtualenv for image-to-GCode pipeline
#
# Recommended Python version: 3.13
#   - vpype 1.15.x requires Python >=3.11, <3.14
#   - Python 3.14 is NOT yet supported by vpype
#
# Install Python 3.13 (if not present):
#   brew install python@3.13
#
# Usage:
#   ./setup_pipeline.sh              # Standard: Python 3.13
#   PYTHON=python3.12 ./setup_pipeline.sh  # Alternative Python version
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/pipeline/requirements.txt"

# --- Determine Python interpreter ---
# Can be overridden via PYTHON env var, else prefers python3.13
if [ -n "${PYTHON:-}" ]; then
    PYTHON_BIN="$PYTHON"
elif command -v python3.13 &>/dev/null; then
    PYTHON_BIN="python3.13"
elif command -v python3.12 &>/dev/null; then
    PYTHON_BIN="python3.12"
elif command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
else
    echo "ERROR: No Python 3.11–3.13 found." >&2
    echo "  vpype requires Python >=3.11, <3.14." >&2
    echo "  Install:  brew install python@3.13" >&2
    exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" --version 2>&1)"
echo "=== Image-to-GCode Pipeline Setup ==="
echo "Project directory: $SCRIPT_DIR"
echo "Python:            $PYTHON_VERSION  ($PYTHON_BIN)"

# Version check: Python 3.14+ is rejected
PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
PY_MAJOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')"
if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 14 ]; then
    echo "" >&2
    echo "ERROR: Python 3.$PY_MINOR is not supported." >&2
    echo "  vpype 1.15.x requires Python >=3.11, <3.14." >&2
    echo "  Please use Python 3.13:  brew install python@3.13" >&2
    echo "  Then:  PYTHON=python3.13 ./setup_pipeline.sh" >&2
    exit 1
fi

# --- Create or verify virtualenv ---
if [ -d "$VENV_DIR" ]; then
    EXISTING_PY="$("$VENV_DIR/bin/python" --version 2>&1 || echo 'unknown')"
    echo "Existing venv found: $EXISTING_PY"
    echo "  To recreate:  rm -rf .venv && ./setup_pipeline.sh"
else
    echo "Creating virtualenv in .venv …"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo ""
echo "--- Upgrading pip ---"
pip install --upgrade pip --quiet

# --- Verify requirements.txt exists ---
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "ERROR: Requirements file not found: $REQUIREMENTS_FILE" >&2
    exit 1
fi

echo "--- Installing all dependencies from pipeline/requirements.txt ---"
pip install -r "$REQUIREMENTS_FILE"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Python version: $(python --version)"
echo "vpype version:  $(python -c 'import vpype; print(vpype.__version__)' 2>/dev/null || echo 'not importable')"
echo ""
echo "Activate virtualenv:     source .venv/bin/activate"
echo "Run tests:               pytest pipeline/tests/"
echo "Run pipeline:            python main.py --config pipeline/configs/standard_pipeline.yaml --input <image>"
echo "Run ControlNet example:  python pipeline/examples/run_controlnet_example.py"
echo "Run Img2Img example:     python pipeline/examples/run_img2img_example.py"
echo ""
echo "For GPU acceleration (optional):"
echo "  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
echo ""
echo "Dependencies installed:"
grep -v "^#" "$REQUIREMENTS_FILE" | grep -v "^$" | sed 's/^/  • /'
