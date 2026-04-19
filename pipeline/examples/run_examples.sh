#!/usr/bin/env bash
# pipeline/examples/run_examples.sh
#
# Examples for running the image-to-GCode pipeline with different configurations
#
# Prerequisites:
#   - Python 3.13+ venv activated
#   - All dependencies installed (pip install -r requirements.txt)
#   - Test image at: pipeline/tests/testimage.png

# Don't exit on ControlNet errors - continue with other examples
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Python executable from venv
PYTHON="${REPO_ROOT}/.venv/bin/python"

# Test if venv exists
if [ ! -f "$PYTHON" ]; then
    echo "❌ Error: Python venv not found at $PYTHON"
    echo "   Please run: source .venv/bin/activate"
    exit 1
fi

# Test image location
TEST_IMAGE="pipeline/tests/testimage.png"
OUTPUT_DIR="output"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Plotter Pipeline Examples"
echo "=========================================="
echo ""

# ============================================================================
# Example 1: Standard Pipeline (Informative Stylizer)
# ============================================================================
echo "1️⃣  Standard Pipeline (Informative Stylizer)"
echo "   Config: pipeline/configs/standard_pipeline.yaml"
echo "   Stylizer: Neural network-based sketch generation"
echo ""

"$PYTHON" pipeline/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input "$TEST_IMAGE" \
    --output "$OUTPUT_DIR/standard_pipeline.gcode" \
    --verbose

echo "   ✅ Output: $OUTPUT_DIR/standard_pipeline.gcode"
echo ""

# ============================================================================
# Example 2: ControlNet Style Transfer (Requires GPU + diffusers)
# ============================================================================
echo "2️⃣  ControlNet Style Transfer"
echo "   Script: run_controlnet_example.py"
echo "   Stylizer: Stable Diffusion 1.5 + ControlNet lineart"
echo "   ⚠️  Note: First run downloads ~4GB models!"
echo ""

if "$PYTHON" -c "import torch; import diffusers; print('PyTorch + diffusers available')" 2>/dev/null; then
    "$PYTHON" pipeline/examples/run_controlnet_example.py \
        --input "$TEST_IMAGE" \
        --output "$OUTPUT_DIR" \
        --prompt "ink drawing, pen sketch, detailed line art" 2>&1 | grep -E "Image loaded|GCode saved|Pipeline" || true
    echo "   ✅ Output: $OUTPUT_DIR/controlnet_style.gcode"
else
    echo "   ⚠️  Skipped: Install diffusers for ControlNet support:"
    echo "      pip install diffusers transformers safetensors torch accelerate"
fi
echo ""

# ============================================================================
# Example 3: Dry Run (Validate Pipeline, Don't Execute)
# ============================================================================
echo "3️⃣  Dry Run - Validate Pipeline Structure"
echo "   Tests pipeline configuration without processing"
echo ""

"$PYTHON" pipeline/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input "$TEST_IMAGE" \
    --output "$OUTPUT_DIR/dry_run.gcode" \
    --dry-run 2>&1 | grep -E "Complete|Step|Error" || true

echo "   ✅ Pipeline validated successfully"
echo ""

# ============================================================================
# Example 4: Custom Config (Test Pipeline)
# ============================================================================
echo "4️⃣  Test Pipeline (All Stylizers)"
echo "   Runs all available stylizers on test image"
echo ""

# Run all test configs
for config in pipeline/tests/pipeline_configs/stylize_*.yaml; do
    if [ ! -f "$config" ]; then
        echo "   ⚠️  No test configs found in pipeline/tests/pipeline_configs/"
        break
    fi
    
    step_name=$(basename "$config" .yaml)
    echo "   Running: $step_name"
    
    "$PYTHON" pipeline/main.py \
        --config "$config" \
        --input "$TEST_IMAGE" \
        --output "$OUTPUT_DIR/${step_name}.gcode" \
        --verbose 2>&1 | tail -2 || echo "   ⚠️  Failed (see error above)"
done

echo ""
echo "   ✅ All test pipelines completed"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "=========================================="
echo "✅ Examples Complete!"
echo "=========================================="
echo ""
echo "Generated GCode files:"
if ls "$OUTPUT_DIR"/*.gcode 1> /dev/null 2>&1; then
    ls -lh "$OUTPUT_DIR"/*.gcode
else
    echo "   (No files generated - check errors above)"
fi
echo ""
