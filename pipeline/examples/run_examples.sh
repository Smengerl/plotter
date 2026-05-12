#!/usr/bin/env bash
# pipeline/examples/run_examples.sh
#
# Run all style-transfer example pipelines.
#
# Each pipeline is configured entirely in its YAML file — edit the YAML to
# change prompts, parameters, or steps. All outputs go to output/.
#
# Usage:
#   ./pipeline/examples/run_examples.sh [INPUT_IMAGE]
#
# Prerequisites:
#   python3 -m venv .venv
#   .venv/bin/pip install -e "pipeline/[diffusers]"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PLOTTER_RUN="$ROOT_DIR/.venv/bin/pipeline-run"

if [[ ! -x "$PLOTTER_RUN" ]]; then
  echo "❌ .venv not found or pipeline-run not installed." >&2
  echo "   Run: python3 -m venv .venv && .venv/bin/pip install -e \"pipeline/[diffusers]\"" >&2
  exit 1
fi

cd "$ROOT_DIR"

INPUT="${1:-pipeline/tests/testimage.png}"
OUTPUT_DIR="output"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Plotter Style-Transfer Examples"
echo "Input: $INPUT"
echo "=========================================="
echo ""

# Check once whether diffusers/torch are available
if ! "$PLOTTER_RUN" --version >/dev/null 2>&1 && ! python3 -c "import torch, diffusers" 2>/dev/null; then
    echo "❌ PyTorch / diffusers not installed. Run:"
    echo "   .venv/bin/pip install -e \"pipeline/[diffusers]\""
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

    "$PLOTTER_RUN" \
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

