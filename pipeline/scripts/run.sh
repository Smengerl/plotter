#!/usr/bin/env bash
# pipeline/scripts/run.sh — Run the plotter pipeline (image → GCode).
#
# Activates the project's .venv automatically, then delegates all arguments
# to pipeline/core/main.py.  The venv is created on first run if missing.
#
# Usage (from anywhere):
#   ./pipeline/scripts/run.sh --config pipeline/configs/standard_pipeline.yaml --input foto.jpg
#   ./pipeline/scripts/run.sh --config pipeline/configs/standard_pipeline.yaml --input foto.jpg --output out.gcode
#   ./pipeline/scripts/run.sh --config pipeline/configs/standard_pipeline.yaml --input foto.jpg --dry-run
#   ./pipeline/scripts/run.sh --config pipeline/configs/standard_pipeline.yaml --input foto.jpg --verbose
#   ./pipeline/scripts/run.sh --help
#
# Options passed through to pipeline/core/main.py:
#   --config YAML        Pipeline configuration file (required)
#   --input  IMAGE       Input image path (jpg, png, …)
#   --output FILE        Output file path (png, gcode, svg, …)
#   --dry-run            Validate and list steps without executing
#   -v, --verbose        Debug-level logging
#
# First-time setup:
#   ./pipeline/scripts/setup_pipeline.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=helpers/env.sh
source "$SCRIPT_DIR/helpers/env.sh"

# ── Print help without starting the venv (fast path) ─────────────────────────
for arg in "$@"; do
  if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
    cat <<EOF
Usage: $(basename "$0") --config YAML [OPTIONS]

Run the image-to-GCode pipeline.

Required:
  --config YAML          Path to pipeline configuration file (.yaml)

Optional:
  --input  IMAGE         Input image (jpg, png, …).
                         Overrides source_path in the YAML config.
  --output FILE          Output file (png, gcode, svg, …).
                         Overrides output_path in the YAML config.
  --dry-run              List and validate steps only — do not execute.
  -v, --verbose          Enable debug-level logging.
  -h, --help             Show this help and exit.

Examples:
  $(basename "$0") --config pipeline/configs/standard_pipeline.yaml \\
                   --input input/photo.jpg

  $(basename "$0") --config pipeline/configs/standard_pipeline.yaml \\
                   --input input/photo.jpg --output output/result.gcode

  $(basename "$0") --config pipeline/configs/standard_pipeline.yaml \\
                   --input input/photo.jpg --dry-run

Available configs (pipeline/configs/):
$(find "$ROOT_DIR/pipeline/configs" -name "*.yaml" -o -name "*.toml" 2>/dev/null \
  | sort | sed "s|$ROOT_DIR/||" | sed 's/^/  /')

Setup (first time):
  ./pipeline/scripts/setup_pipeline.sh
EOF
    exit 0
  fi
done

# ── Activate venv (auto-create if missing) ────────────────────────────────────
activate_venv --auto-create
resolve_venv_python

# ── Run pipeline ──────────────────────────────────────────────────────────────
exec "$PYTHON" -m pipeline.core.main "$@"
