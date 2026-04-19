#!/usr/bin/env bash
# pipeline/examples/run_examples.sh
#
# Run all style-transfer example pipelines using pipeline/main.py.
#
# Each pipeline is configured entirely in its YAML file — edit the YAML to
# change prompts, parameters, or steps. All outputs go to output/.
#
# Usage:
#   ./pipeline/examples/run_examples.sh [INPUT_IMAGE]
#
# Prerequisites:
#   source .venv/bin/activate   (or run pipeline/setup_pipeline.sh first)
#   pip install diffusers transformers safetensors torch accelerate

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${REPO_ROOT}/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "❌ venv not found. Run: ./pipeline/setup_pipeline.sh"
    exit 1
fi

INPUT="${1:-pipeline/tests/testimage.png}"
OUTPUT_DIR="output"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Plotter Style-Transfer Examples"
echo "Input: $INPUT"
echo "=========================================="
echo ""

# Check once whether diffusers/torch are available
if ! "$PYTHON" -c "import torch, diffusers" 2>/dev/null; then
    echo "❌ PyTorch / diffusers not installed. Run:"
    echo "   pip install diffusers transformers safetensors torch accelerate"
    echo ""
    exit 1
fi

run_example() {
    local num="$1"
    local label="$2"
    local config="$3"
    local output="$4"

    echo "${num}  ${label}"
    echo "   Config: ${config}"
    echo ""

    "$PYTHON" pipeline/main.py \
        --config "$config" \
        --input  "$INPUT" \
        --output "$OUTPUT_DIR/${output}" \
        --verbose

    echo ""
    echo "   ✅ $OUTPUT_DIR/${output}"
    echo ""
}

# ── ControlNet examples (structure-preserving) ────────────────────────────────
echo "── ControlNet (structure-preserving) ──────────────────────"
echo "   ⚠️  First run downloads ~4GB models (ControlNet + SD 1.5)"
echo ""

run_example "1️⃣ " "Pen Sketch       (lineart conditioning)" \
    "pipeline/examples/controlnet_pen_sketch.yaml"  "controlnet_pen_sketch.png"

run_example "2️⃣ " "Technical Drawing (canny conditioning)" \
    "pipeline/examples/controlnet_technical.yaml"   "controlnet_technical.png"

run_example "3️⃣ " "Woodcut Print     (softedge conditioning)" \
    "pipeline/examples/controlnet_woodcut.yaml"     "controlnet_woodcut.png"

# ── img2img examples (no ControlNet, faster) ──────────────────────────────────
echo "── img2img (no ControlNet, faster) ────────────────────────"
echo "   ⚠️  First run downloads ~4GB models (SD 1.5)"
echo ""

run_example "4️⃣ " "Oil Painting  (strength 0.75)" \
    "pipeline/examples/img2img_oil_painting.yaml"  "img2img_oil_painting.png"

run_example "5️⃣ " "Watercolor    (strength 0.55, subtle)" \
    "pipeline/examples/img2img_watercolor.yaml"    "img2img_watercolor.png"

run_example "6️⃣ " "Charcoal      (strength 0.85, aggressive)" \
    "pipeline/examples/img2img_charcoal.yaml"      "img2img_charcoal.png"

# ── Summary ───────────────────────────────────────────────────────────────────
echo "=========================================="
echo "✅ All examples complete"
echo "=========================================="
echo ""
echo "Generated images:"
ls -lh "$OUTPUT_DIR"/*.png 2>/dev/null || echo "   (none found)"
echo ""

