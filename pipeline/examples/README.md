# Pipeline Execution Examples

Complete guide to running the image-to-GCode pipeline with different example scripts.

## Quick Start

### 1️⃣ Standard Pipeline (Recommended)

```bash
# With test image
python main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input pipeline/tests/testimage.png \
    --output output/result.gcode

# With your own image
python main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input ~/photos/myimage.jpg \
    --output ~/output/myimage.gcode
```

Or use the dedicated script:

```bash
python pipeline/examples/run_pipeline_example.py 1 --input pipeline/tests/testimage.png
```

---

### 2️⃣ ControlNet Style Transfer

⚠️ **Requires GPU** (CUDA, MPS, or Apple Silicon) and ~4GB VRAM

```bash
python pipeline/examples/run_controlnet_example.py \
    --prompt "watercolor painting, soft colors, impressionist style"
```

**For full documentation**: See `pipeline/README.md` — **ControlNet Style Transfer** section

---

### 3️⃣ Image-to-Image Style Transfer

Lightweight with adjustable strength (0.0–1.0):

```bash
python pipeline/examples/run_img2img_example.py --strength 0.7
```

**For full documentation**: See `pipeline/README.md` — **Image-to-Image Style Transfer** section

---

### 4️⃣ Batch All Stylizers

```bash
python pipeline/examples/run_pipeline_example.py 4
# or
bash pipeline/examples/run_examples.sh
```

---

## Available Example Scripts

| Script | Purpose | GPU Required |
| --- | --- | --- |
| `run_pipeline_example.py` | Execute different pipelines | No |
| `run_controlnet_example.py` | ControlNet style transfer | Yes |
| `run_img2img_example.py` | Image-to-Image transfer | No* |
| `run_examples.sh` | Batch all stylizers | No |

\*Recommended for quality results

---

## Advanced Usage

### Create Custom Pipeline Config

Create `my_pipeline.yaml`:

```yaml
steps:
  # Step 1: Choose a stylizer
  - step: stylise
    config:
      style: lineart
      style_res: 1024
      device: auto

  # Step 2: Vectorize
  - step: vectorise
    config:
      min_path_px: 5
      simplify_eps: 1.0

  # Step 3: Generate GCode
  - step: gcode_gen
    config:
      target_width_mm: 200
      target_height_mm: 280
      feedrate_draw: 2000

  # Step 4 (optional): Send to plotter
  - step: send_gcode
    enabled: false  # Set to true to send to hardware
    config:
      port: /dev/tty.usbmodem1101
      baud: 115200
```

Run it:

```bash
python main.py \
    --config my_pipeline.yaml \
    --input image.jpg \
    --output image.gcode
```

### Python API (No CLI)

```python
import yaml
from pathlib import Path
from PIL import Image
from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner

# Load config
with open("pipeline/configs/standard_pipeline.yaml") as f:
    config = yaml.safe_load(f)

# Create runner
runner = PipelineRunner(config["steps"])

# Process image
img = Image.open("input.jpg")
ctx = ImageContext(img)
ctx = runner.run(ctx)

# Save output
ctx.save_gcode("output.gcode")
```

### Inspect Pipeline Steps

```bash
python pipeline/examples/run_pipeline_example.py 3
```

**Output**:

```
Example 3: Inspect Pipeline - standard_pipeline.yaml
==================================================
Total steps: 3

Step 1: stylise ✅ Enabled
  - style: informative
  - style_res: 1024
  - device: auto

Step 2: vectorise ✅ Enabled
  - min_path_px: 10
  - simplify_eps: 1.5

Step 3: gcode_gen ✅ Enabled
  - target_width_mm: 180.0
  - origin_x: 5.0
  ...
```

### Validate Pipeline (Dry-Run)

```bash
python main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input pipeline/tests/testimage.png \
    --output output/test.gcode \
    --dry-run
```

### Python API (No CLI)

```python
import yaml
from pathlib import Path
from PIL import Image
from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner

with open("pipeline/configs/standard_pipeline.yaml") as f:
    config = yaml.safe_load(f)

runner = PipelineRunner(config["steps"])
img = Image.open("input.jpg")
ctx = ImageContext(img)
ctx = runner.run(ctx)
ctx.save_gcode("output.gcode")
```

---

## Stylizer Comparison

| Stylizer | Speed | Quality | GPU | Use Case |
| --- | --- | --- | --- | --- |
| `canny` | ⚡ Instant | Good | No | Fast edge detection |
| `xdog` | ⚡ <1s | Very Good | No | Artistic, edge-preserving |
| `adaptive` | ⚡ Instant | Good | No | Uneven lighting |
| `hed` | 🟡 5–10s | Excellent | Yes | Professional edges |
| `dexined` | 🟡 5–10s | Excellent | Yes | Clean lineart |
| `lineart` | 🟡 5–10s | Excellent | Yes | ControlNet lineart |
| `informative` | 🟡 2–5s | Very Good | Yes | Sketch-like (default) |
| `controlnet` | 🔴 30–120s | Excellent | **Yes** | Artistic style |
| `img2img` | 🔴 1–3min | Excellent | Yes | Lightweight style |

**Legend**: ⚡ = CPU instant | 🟡 = GPU recommended | 🔴 = GPU required

---

## Configuration Files Reference

See `pipeline/configs/`:

- `standard_pipeline.yaml` — Standard edge detection
- `demo_controlnet_style.yaml` — ControlNet style transfer
- `demo_img2img_style.yaml` — Image-to-Image style transfer
- `grbl_a4_pen.toml` — GCode generation profile

For full pipeline documentation, see **`pipeline/README.md`**.

---

## Next Steps

1. **Send to plotter**: Set `send_gcode.enabled: true` in config
2. **Batch processing**: Use `pipeline/examples/run_pipeline_example.py 4`
3. **Custom models**: Modify `model_id` in stylizer config
4. **Custom prompts**: Edit ControlNet `prompt` in config or pass `--prompt` flag
