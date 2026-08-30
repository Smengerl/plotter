#!/usr/bin/env bash
# pipeline/examples/run_examples.sh
#
# Runs a few pipelines against one input image so you can eyeball the output.
#   ./pipeline/examples/run_examples.sh [INPUT_IMAGE]
#
# Default input: pipeline/input/testimage.png. Outputs go to output/.
# Needs `.venv/bin/pip install -e "pipeline/[gui]"` (add ,diffusers for the
# ControlNet / Img2Img configs).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

RUN="$ROOT_DIR/.venv/bin/pipeline-run"
[[ -x "$RUN" ]] || { echo "❌ .venv not found — see pipeline/README.md" >&2; exit 1; }

INPUT="${1:-pipeline/input/testimage.png}"
OUT="output"
mkdir -p "$OUT"
echo "Input: $INPUT   Output dir: $OUT/"
echo

# End-to-end: sketch -> vectorize -> G-code file
"$RUN" --config pipeline/examples/standard_pipeline.yaml \
       --input "$INPUT" --output "$OUT/standard_pipeline.gcode"

# CPU-only stylizers (image -> PNG). No downloads.
for cfg in canny_edge xdog_sketch adaptive_threshold; do
    "$RUN" --config "pipeline/configs/${cfg}.yaml" \
           --input "$INPUT" --output "$OUT/${cfg}.png"
done

echo
echo "✅ done — results in $OUT/"
ls -lh "$OUT"
