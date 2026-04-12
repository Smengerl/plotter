#!/usr/bin/env bash
# setup_pipeline.sh — Richtet das Python-Virtualenv für die img2gcode Pipeline ein
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== img2gcode Pipeline Setup ==="
echo "Projektverzeichnis: $SCRIPT_DIR"

# Virtualenv anlegen
# Virtualenv anlegen
if [ ! -d "$VENV_DIR" ]; then
    echo "Erstelle virtualenv in .venv …"
    python3 -m venv "$VENV_DIR"
fi

# Aktivieren
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Python: $(python --version)"
echo "Installiere Kernabhängigkeiten …"

pip install --upgrade pip --quiet
pip install -r pipeline/requirements.txt
echo "
Optional: Neuronale Modelle (HED / DexiNed):
    pip install controlnet-aux torch torchvision pillow
"

echo ""
echo "=== Fertig ==="
echo ""
echo "Virtualenv aktivieren:  source .venv/bin/activate"
echo "Pipeline ausführen:     python pipeline/img2gcode.py <bild>"
echo "Tests ausführen:        pytest"
echo ""
echo "Optional: Neuronale Modelle (HED / DexiNed):"
echo "  pip install controlnet-aux torch torchvision pillow"
