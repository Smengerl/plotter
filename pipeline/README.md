# Pipeline Architecture & Usage Guide

## Quick Setup

### Installation

The pipeline is set up with a single script:

```bash
./setup_pipeline.sh
```

This installs all core dependencies including:

- Image processing (OpenCV, Pillow, numpy)
- Vectorization (vpype, vpype-gcode)
- Edge detection (controlnet-aux, torch, timm)
- Style transfer (diffusers, transformers, safetensors)
- Hardware communication (pyserial, PyGrbl_Streamer)
- Testing (pytest)

**Manual setup** (if not using setup_pipeline.sh):

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r pipeline/requirements.txt
```

**For GPU acceleration** (optional):

Replace `torch` with your platform-specific build:

```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# macOS (M1/M2/M3) — Auto-detects Metal Performance Shaders
# No action needed, torch will use MPS automatically
```

---

## Overview

The plotter pipeline is a modular, sequential image-to-GCode processing system. Each step receives an `ImageContext`, transforms it, and passes it to the next step.

```text
Input Image (PIL)
    ↓
Stylization (edge detection)
    ↓
Vectorization (raster → vector paths)
    ↓
GCode Generation (vpype native)
    ↓
Optional: Send to GRBL Hardware
    ↓
Output: GCode file or physical lines
```

## Architecture

### Core Components

- **`pipeline/core/base.py`** — `ImageContext` (data transport), `PipelineStep` (base class)
- **`pipeline/core/registry.py`** — Step registry mapping names to classes
- **`pipeline/core/runner.py`** — Sequential execution engine

### Data Transport: ImageContext

All steps communicate via `ImageContext`:

```python
class ImageContext:
    image: PIL.Image        # Current working image (RGB)
    metadata: dict[str, Any]  # Input/output paths, dimensions
    intermediates: dict[str, Any]  # Step outputs shared with downstream steps
    config: dict[str, Any]  # Global pipeline config
```

**Key intermediates**:

- `binary` — uint8 array (H, W), 255=line, 0=background
- `paths` — List of (N, 2) float32 arrays, pixel coordinates
- `gcode_lines` — List of GCode command strings
- `image_shape` — (H, W) fallback if binary unavailable

## Pipeline Execution Flow

### 1. Stylization (Edge Detection & Style Transfer)

**Purpose**: Convert raster image to binary edge map (lines on white background) or apply artistic style transfer.

**Available Steps**:

| Step Name | Backend | Required Packages | Quality |
| --- | --- | --- | --- |
| `stylise_canny` | OpenCV | numpy, opencv-python | Fast, simple |
| `stylise_xdog` | Custom | numpy | Artistic, edge-preserving |
| `stylise_adaptive` | OpenCV | numpy, opencv-python | Adaptive threshold |
| `stylise_hed` | Neural Network | controlnet-aux, torch | High quality |
| `stylise_dexined` | Neural Network | controlnet-aux, torch | Lineart focused |
| `stylise_lineart` | Neural Network | controlnet-aux, torch | ControlNet-v1.1 |
| `stylise_informative` | Neural Network (ONNX/PyTorch) | torch, timm, huggingface-hub | Sketch-like |
| `stylise_controlnet` | Stable Diffusion 1.5 + ControlNet | diffusers, torch, transformers | Precise style + structure |
| `stylise_img2img` | Stable Diffusion 2.1 | diffusers, torch, transformers | Lightweight style transfer |

**Config Keys** (common across all stylizers):

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `style_res` | int | 1024 | Longest side of intermediate image (pixels) |
| `model_path` | str/Path | None | Custom model directory (None = auto-download) |
| `device` | str | "auto" | PyTorch device: "auto", "cuda", "mps", "cpu" |

**NN-specific**:

- `lineart_coarse` (bool, default False) — Use coarse lineart detection
- `lineart_detect_res` (int, default 512) — Detection resolution
- `lineart_image_res` (int, default 512) — Output resolution
- `inform_style` (int, default 1) — Informative drawings: 1=sharp, 2=soft
- **ControlNet** (`stylise_controlnet`):
  - `prompt` (str) — Style prompt (e.g., "oil painting, Van Gogh style")
  - `negative_prompt` (str) — What to avoid in generation
  - `controlnet_type` (str, default "lineart") — ControlNet variant (canny, lineart, softedge, scribble, pose, depth, normal, seg)
  - `num_inference_steps` (int, default 20) — Diffusion denoising steps
  - `guidance_scale` (float, default 7.5) — Prompt adherence strength
  - `strength` (float, default 0.8) — How much to modify image (0.0–1.0)
  - `enable_model_cpu_offload` (bool, default False) — Reduce VRAM (slower)
- **Image-to-Image** (`stylise_img2img`):
  - `prompt` (str) — Style prompt
  - `negative_prompt` (str) — What to avoid
  - `strength` (float, default 0.7) — Modification intensity (0.0–1.0): lower = preserve more original
  - `num_inference_steps` (int, default 20) — Quality vs speed
  - `guidance_scale` (float, default 7.5) — Prompt adherence
  - `enable_model_cpu_offload` (bool, default False) — Reduce VRAM

**Output**:

- `ctx.intermediates["binary"]` — uint8 array (H, W)

---

## ControlNet Style Transfer

Use Stable Diffusion 1.5 with ControlNet for precise artistic style transfer while maintaining structure control.

### Quick Start

**Prerequisites**:

```bash
pip install diffusers transformers safetensors torch accelerate
```

**Run with default style**:

```bash
python pipeline/examples/run_controlnet_example.py
```

**Run with custom prompt**:

```bash
python pipeline/examples/run_controlnet_example.py \
    --prompt "watercolor painting, soft colors, impressionist style"
```

**Run via main.py CLI**:

```bash
python main.py \
    --config pipeline/configs/demo_controlnet_style.yaml \
    --input photo.jpg \
    --output result.gcode \
    --verbose
```

### ControlNet Types

| Type | Best For | Notes |
| --- | --- | --- |
| `lineart` | Clean pen sketches | Default, best for plotting |
| `canny` | Edge-based technical | Sharp edges, lineart style |
| `softedge` | Soft flowing lines | Less aggressive than canny |
| `scribble` | Hand-drawn look | Sketchy appearance |
| `pose` | Preserving poses | Keep human/body structure |
| `depth` | 3D structure | Preserve depth information |
| `normal` | Surface normals | Geometric form |
| `seg` | Semantic segmentation | Object regions |

### Style Prompt Examples

**Technical / Technical Drawings**:

```
"technical drawing, blueprints, architectural lines, engineering diagram"
"circuit diagram, technical schematic, detailed line drawing"
```

**Artistic Styles**:

```
"oil painting, rich colors, classical Renaissance style"
"watercolor painting, soft colors, impressionist"
"charcoal drawing, dark mood, dramatic shadows"
"pen sketch, ink drawing, detailed illustration"
```

**Abstract / Stylized**:

```
"abstract art, geometric shapes, minimalist"
"popart style, bold colors, high contrast"
"anime style, manga illustration, cel shading"
```

**Photo Effects**:

```
"black and white sketch, high contrast edges"
"stained glass art, colorful segments"
"vintage engraving, Victorian illustration"
```

### Configuration

Edit `pipeline/configs/demo_controlnet_style.yaml`:

```yaml
- step: stylise_controlnet
  config:
    prompt: "your custom prompt here"
    negative_prompt: "things to avoid"
    controlnet_type: lineart  # or canny, softedge, etc.
    num_inference_steps: 25   # Higher = better quality, slower
    guidance_scale: 7.5       # How much to follow prompt
    enable_model_cpu_offload: false  # Set true if out of VRAM
```

### Python API

```python
from pipeline.examples.run_controlnet_example import run_controlnet_example
from pathlib import Path

# Simple run
run_controlnet_example(
    input_image="photo.jpg",
    output_dir="output/"
)

# Custom prompt
run_controlnet_example(
    input_image=Path("photo.jpg"),
    output_dir=Path("results/"),
    prompt="oil painting, Van Gogh style, starry night"
)
```

### Performance

| Hardware | Time per Image | Quality |
| --- | --- | --- |
| CPU only | 30–60 min | Good |
| GPU (CUDA) | 30–120 sec | Excellent |
| GPU (M1/M2) | 1–3 min | Very good |
| With `cpu_offload: true` | 2–5 min | Good |

### Troubleshooting

**Out of Memory (VRAM)**:

```yaml
enable_model_cpu_offload: true  # Slower but uses less VRAM
num_inference_steps: 15  # Faster, lower quality
```

**Models Won't Download**:

```bash
huggingface-cli login
# Enter your HF token from https://huggingface.co/settings/tokens
```

**No GPU Detected**:

```bash
python -c "import torch; print(torch.cuda.is_available())"  # CUDA
python -c "import torch; print(torch.backends.mps.is_available())"  # macOS
```

---

## Image-to-Image Style Transfer

Use lightweight Stable Diffusion 2.1 for quick style transfer with adjustable strength parameter. Uses ~2GB less VRAM than ControlNet.

### Quick Start

**Prerequisites**:

```bash
pip install diffusers transformers safetensors torch accelerate
```

**Run with default style**:

```bash
python pipeline/examples/run_img2img_example.py
```

**Adjust strength (modification intensity)**:

```bash
# Subtle style change (preserves more original content)
python pipeline/examples/run_img2img_example.py --strength 0.4

# Moderate style transfer (default: 0.75)
python pipeline/examples/run_img2img_example.py --strength 0.7

# Aggressive transformation
python pipeline/examples/run_img2img_example.py --strength 0.9
```

**Run via main.py CLI**:

```bash
python main.py \
    --config pipeline/configs/demo_img2img_style.yaml \
    --input photo.jpg \
    --output result.gcode \
    --verbose
```

### Strength Parameter Guide

| Strength | Effect | Use Case |
| --- | --- | --- |
| 0.1–0.3 | Very subtle | Slight enhancement, preservation of original |
| 0.3–0.5 | Light modification | Gentle style application |
| 0.5–0.7 | Moderate change | Balanced style transfer (default: 0.75) |
| 0.7–0.85 | Strong modification | Pronounced artistic effect |
| 0.85–0.99 | Very aggressive | Strong transformation, may lose structure |

### Style Prompt Examples

**Painting Styles**:

```
"oil painting, rich colors, classical style"
"watercolor painting, soft colors, impressionist"
"acrylic painting, bold brushstrokes, modern"
"pastel drawing, soft tones, delicate"
```

**Drawing Styles**:

```
"charcoal drawing, dark mood, dramatic shadows"
"pencil sketch, detailed line drawing, realistic"
"ink drawing, pen sketch, detailed illustration"
"graphite drawing, fine details, monochrome"
```

**Artistic Effects**:

```
"abstract art, geometric shapes, minimalist"
"stained glass art, colorful segments, glowing"
"vintage engraving, Victorian illustration"
"anime style, cel shading, comic book"
```

**Photographic Effects**:

```
"black and white sketch, high contrast edges"
"pen and ink, technical drawing, lineart"
"etching style, fine hatching, classical"
```

### Configuration

Edit `pipeline/configs/demo_img2img_style.yaml`:

```yaml
- step: stylise_img2img
  config:
    prompt: "your custom prompt here"
    negative_prompt: "things to avoid"
    strength: 0.75  # Adjust this for modification intensity (0.0–1.0)
    num_inference_steps: 25  # Higher = better quality, slower
    guidance_scale: 7.5  # How much to follow prompt
    enable_model_cpu_offload: false  # Set true if out of VRAM
```

### Python API

```python
from pipeline.examples.run_img2img_example import run_img2img_example
from pathlib import Path

# Simple run
run_img2img_example(
    input_image="photo.jpg",
    output_dir="output/"
)

# Custom prompt and strength
run_img2img_example(
    input_image=Path("photo.jpg"),
    output_dir=Path("results/"),
    prompt="watercolor painting, soft impressionist style",
    strength=0.65
)
```

### Performance

| Hardware | Time per Image | Quality |
| --- | --- | --- |
| CPU only | 10–30 min | Good |
| GPU (CUDA) | 1–3 min | Excellent |
| GPU (M1/M2) | 3–10 min | Very good |
| With `cpu_offload: true` | 5–15 min | Good |

### Comparison: ControlNet vs Image-to-Image

| Feature | ControlNet | Image-to-Image |
| --- | --- | --- |
| Model size | ~4GB | ~2GB |
| VRAM required | 6–8GB | 4–6GB |
| Speed (GPU) | 30–120 sec | 1–3 min |
| Speed (CPU) | 30–60 min | 10–30 min |
| Structure preservation | Excellent | Good |
| Style control | Very precise | Good |
| ControlNet types | 8 options | N/A |
| Best for | Technical + Style | Quick style transfer |

**Use Image-to-Image if**:

- You want faster processing
- You have lower VRAM budget
- You want simple style transfer
- Quick experimentation is priority

**Use ControlNet if**:

- You need precise structure control
- You want multiple conditioning types
- You have sufficient VRAM
- Professional results are priority

### Troubleshooting

**Out of Memory (VRAM)**:

```yaml
enable_model_cpu_offload: true  # Slower but uses less VRAM
num_inference_steps: 15  # Faster
```

**Models Won't Download**:

```bash
huggingface-cli login
# Enter your HF token from https://huggingface.co/settings/tokens
```

**No GPU Detected**:

```bash
python -c "import torch; print(torch.cuda.is_available())"  # CUDA
python -c "import torch; print(torch.backends.mps.is_available())"  # macOS
```

---

### 2. Vectorization

**Purpose**: Extract connected components from binary image → vector paths.

**Step Name**: `vectorise`

**Config Keys**:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `min_path_px` | float | 10 | Minimum path length (pixels) |
| `simplify_eps` | float | 1.5 | Curve simplification tolerance (pixels) |
| `invert_logic` | bool | False | Invert black/white (True = black lines) |

**Algorithm**:

1. Find all connected components in binary image (8-connectivity)
2. Trace contours using OpenCV `findContours`
3. Simplify curves using Douglas-Peucker (epsilon=`simplify_eps`)
4. Filter short paths (< `min_path_px` pixels)
5. Output: List of paths, each a (N, 2) float32 array

**Output**:

- `ctx.intermediates["paths"]` — List of numpy arrays (pixel coordinates)

---

### 3. GCode Generation

**Purpose**: Transform vector paths to plotter coordinates → GCode commands.

Two implementations available:

#### 3a. Native GCode (Recommended): `gcode_gen`

Uses `vpype` + `vpype-gcode` with TOML profile system.

**Config Keys**:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `profile` | str | "grbl_a4_pen" | TOML profile name (from gwrite section) |
| `toml_path` | str/Path | None | Path to TOML profile file (None = internal default) |
| `target_width_mm` | float | 190.0 | Drawing width (mm) = A4 - 2×5mm margins |
| `target_height_mm` | float | 277.0 | Drawing height (mm) = A4 - 2×10mm margins |
| `keep_aspect` | bool | True | Maintain aspect ratio when scaling |
| `linesort` | bool | True | Optimize path order (nearest-neighbor heuristic) |

**Pipeline**:

1. Scale paths from pixel → vpype document (CSS pixels)
2. Apply image transformation (flip, rotate if needed)
3. Run `vpype_cli.execute()` with TOML profile
4. Extract GCode from vpype pipeline

**TOML Profile Format** (`pipeline/configs/grbl_a4_pen.toml`):

```toml
[gwrite]
default_profile = "grbl_a4_pen"

[gwrite.grbl_a4_pen]
unit = "mm"
offset_x = 0
offset_y = 0
document_start = "G21\nG90\n"
document_end = "M5\n"
segment_first = "{x:.3f} {y:.3f}\n"
segment = "G00 X{x:.3f} Y{y:.3f}\n"
line_end = "M3 S1000\nG01 X{x:.3f} Y{y:.3f}\n"
```

**Output**:

- `ctx.intermediates["gcode_lines"]` — List of GCode command strings

#### 3b. Legacy GCode (Deprecated): `gcode_gen`

Direct coordinate transformation without vpype.

**Config Keys**:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `target_width_mm` | float | 190.0 | Drawing width (mm) |
| `target_height_mm` | float | 277.0 | Drawing height (mm) |
| `origin_x` | float | 5.0 | Left margin (mm) |
| `origin_y` | float | 5.0 | Bottom margin (mm) |
| `keep_aspect` | bool | True | Maintain aspect ratio |
| `feedrate_draw` | int | 1500 | Drawing speed (mm/min) |
| `feedrate_travel` | int | 3000 | Travel speed (mm/min) |
| `pen_down_cmd` | str | "M3 S1000" | GRBL pen-down command |
| `pen_up_cmd` | str | "M5" | GRBL pen-up command |
| `pen_delay_ms` | int | 100 | Wait after pen-down (ms) |

**Coordinate Transformation**:

```
Pixel Space (image):       (0, 0)────────── x (W)
                            │
                            │ y (H)
                            v

Plotter Space (mm):        (ox, oy)─────── x
                            │
                            │ y
                            v
```

Y-axis is flipped (image: top-left origin, plotter: bottom-left origin).

---

### 4. Optional: Send to GRBL Hardware

**Purpose**: Stream GCode to GRBL-compatible plotter via serial connection.

**Step Name**: `send_gcode`

**Config Keys**:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `port` | str | "/dev/ttyUSB0" | Serial port (e.g., "/dev/ttyUSB0", "COM3") |
| `baudrate` | int | 115200 | Serial communication speed |
| `dry_run` | bool | True | Test mode (read commands, don't send) |

**Transport**:

- Uses `PyGrbl_Streamer` for GRBL communication
- Streams line-by-line with flow control
- Monitors for alarms/errors
- Logs progress to logger

**Output**:

- No intermediate (sends to hardware)

---

## Configuration Files

### Example Pipeline: Canny Edge Detection

**File**: `pipeline/configs/standard_pipeline.yaml`

```yaml
steps:
  # 1. Stylization
  - step: stylise
    config:
      source_path: /path/to/image.jpg
      style_res: 1024

  # 2. Vectorization
  - step: vectorise
    config:
      min_path_px: 10
      simplify_eps: 1.5

  # 3. GCode (native vpype)
  - step: gcode_gen
    config:
      profile: grbl_a4_pen
      target_width_mm: 190.0
      target_height_mm: 277.0
      keep_aspect: true
      linesort: true

  # 4. Send to GRBL (optional)
  - step: send_gcode
    enabled: false  # Set to true to actually send
    config:
      port: /dev/ttyUSB0
      baudrate: 115200
      dry_run: false
```

### Running the Pipeline

```bash
# Using main.py
python main.py \
  --config pipeline/configs/standard_pipeline.yaml \
  --input photo.jpg \
  --output photo.gcode \
  --verbose

# Dry-run (list steps, don't execute)
python main.py \
  --config pipeline/configs/standard_pipeline.yaml \
  --input photo.jpg \
  --output photo.gcode \
  --dry-run

# Using PipelineRunner directly
import yaml
from pipeline.core.runner import PipelineRunner

with open("pipeline/configs/standard_pipeline.yaml") as f:
    cfg = yaml.safe_load(f)
runner = PipelineRunner(cfg["steps"])
ctx = runner.run(ctx)  # where ctx = ImageContext
```

---

## Writing Custom Steps

All steps inherit from `PipelineStep`:

```python
from pipeline.core.base import ImageContext, PipelineStep

class MyCustomStep(PipelineStep):
    """
    Description of what your step does.
    
    Config keys:
        my_param (str): Description
        another_param (float): Description
    """
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Validate config, initialize resources
        
    def process(self, ctx: ImageContext) -> ImageContext:
        """Transform context and return modified copy."""
        # Read from ctx.intermediates
        # Write to ctx.intermediates
        # Return ctx
        return ctx
```

**Steps to register**:

1. Create `pipeline/steps/my_step.py` with `MyCustomStep` class
2. Add import to `pipeline/core/registry.py`
3. Add entry to `STEP_REGISTRY` dict
4. Create tests in `pipeline/tests/test_my_step.py`
5. Run `.venv/bin/pytest pipeline/tests/ -v` (all tests must pass)

---

## Device Detection

Steps with neural networks auto-detect compute devices:

```
Priority: CUDA > MPS (Metal) > CPU
```

Override with `device` config key:

- `"auto"` — Auto-detect (default)
- `"cuda"` — NVIDIA GPU (if available)
- `"mps"` — Apple Metal GPU (if on macOS)
- `"cpu"` — CPU fallback

---

## Performance Tips

1. **Resize input image** — Larger `style_res` = slower. Default 1024px is good balance.
2. **Simplification** — Increase `simplify_eps` for smoother, fewer paths (faster plotter time).
3. **Min path length** — Increase `min_path_px` to skip tiny artifacts.
4. **Linesort** — Enable for large path counts (> 100 paths) to reduce travel distance.
5. **GPU acceleration** — NN stylizers run ~10x faster on CUDA/MPS vs CPU.

---

## Troubleshooting

### "Step not found in registry"

→ Check step name matches `STEP_REGISTRY` keys in `pipeline/core/registry.py`

### "vpype not found"

→ Activate venv: `source .venv/bin/activate` or use `.venv/bin/python`

### "controlnet_aux not installed"

→ Run: `pip install controlnet-aux torch torchvision pillow`

### Tests failing after code changes

→ Run: `.venv/bin/pytest pipeline/tests/ -v`
→ All 62 tests must pass before committing

### Device detection issues

→ Check: `python -c "import torch; print(torch.cuda.is_available())"`
→ Or: `python -c "import torch; print(torch.backends.mps.is_available())"`

---

## References

- **vpype** — <https://github.com/abey79/vpype>
- **vpype-gcode** — <https://github.com/abey79/vpype-gcode>
- **controlnet-aux** — <https://github.com/huggingface/controlnet_aux>
- **GRBL** — <https://github.com/gnea/grbl>

## Architecture

### Core Components

- **`pipeline/core/base.py`** — `ImageContext` (data transport), `PipelineStep` (base class)
- **`pipeline/core/registry.py`** — Step registry mapping names to classes
- **`pipeline/core/runner.py`** — Sequential execution engine

### Data Transport: ImageContext

All steps communicate via `ImageContext`:

```python
class ImageContext:
    image: PIL.Image        # Current working image (RGB)
    metadata: dict[str, Any]  # Input/output paths, dimensions
    intermediates: dict[str, Any]  # Step outputs shared with downstream steps
    config: dict[str, Any]  # Global pipeline config
```

**Key intermediates**:

- `binary` — uint8 array (H, W), 255=line, 0=background
- `paths` — List of (N, 2) float32 arrays, pixel coordinates
- `gcode_lines` — List of GCode command strings
- `image_shape` — (H, W) fallback if binary unavailable

## Pipeline Execution Flow

### 1. Stylization (Edge Detection)

**Purpose**: Convert raster image to binary edge map (lines on white background).

**Available Steps**:

| Step Name | Backend | Required Packages | Quality |
|-----------|---------|-------------------|---------|
| `stylise` | OpenCV | numpy, opencv-python | Fast, simple |
| `stylise_xdog` | Custom | numpy | Artistic, edge-preserving |
| `stylise_adaptive` | OpenCV | numpy, opencv-python | Adaptive threshold |
| `stylise_hed` | Neural Network | controlnet-aux, torch | High quality |
| `stylise_dexined` | Neural Network | controlnet-aux, torch | Lineart focused |
| `stylise_lineart` | Neural Network | controlnet-aux, torch | ControlNet-v1.1 |
| `stylise_informative` | Neural Network (ONNX/PyTorch) | torch, timm, huggingface-hub | Sketch-like |

**Config Keys** (common across all stylizers):

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `source_path` | str/Path | Required | Path to input image file |
| `style_res` | int | 1024 | Longest side of intermediate image (pixels) |
| `model_path` | str/Path | None | Custom model directory (None = auto-download) |
| `device` | str | "auto" | PyTorch device: "auto", "cuda", "mps", "cpu" |

**NN-specific**:

- `lineart_coarse` (bool, default False) — Use coarse lineart detection
- `lineart_detect_res` (int, default 512) — Detection resolution
- `lineart_image_res` (int, default 512) — Output resolution
- `inform_style` (int, default 1) — Informative drawings: 1=sharp, 2=soft

**Output**:

- `ctx.intermediates["binary"]` — uint8 array (H, W)

---

### 2. Vectorization

**Purpose**: Extract connected components from binary image → vector paths.

**Step Name**: `vectorise`

**Config Keys**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `min_path_px` | float | 10 | Minimum path length (pixels) |
| `simplify_eps` | float | 1.5 | Curve simplification tolerance (pixels) |
| `invert_logic` | bool | False | Invert black/white (True = black lines) |

**Algorithm**:

1. Find all connected components in binary image (8-connectivity)
2. Trace contours using OpenCV `findContours`
3. Simplify curves using Douglas-Peucker (epsilon=`simplify_eps`)
4. Filter short paths (< `min_path_px` pixels)
5. Output: List of paths, each a (N, 2) float32 array

**Output**:

- `ctx.intermediates["paths"]` — List of numpy arrays (pixel coordinates)

---

### 3. GCode Generation

**Purpose**: Transform vector paths to plotter coordinates → GCode commands.

Two implementations available:

#### 3a. Native GCode (Recommended): `gcode_gen`

Uses `vpype` + `vpype-gcode` with TOML profile system.

**Config Keys**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `profile` | str | "grbl_a4_pen" | TOML profile name (from gwrite section) |
| `toml_path` | str/Path | None | Path to TOML profile file (None = internal default) |
| `target_width_mm` | float | 190.0 | Drawing width (mm) = A4 - 2×5mm margins |
| `target_height_mm` | float | 277.0 | Drawing height (mm) = A4 - 2×10mm margins |
| `keep_aspect` | bool | True | Maintain aspect ratio when scaling |
| `linesort` | bool | True | Optimize path order (nearest-neighbor heuristic) |

**Pipeline**:

1. Scale paths from pixel → vpype document (CSS pixels)
2. Apply image transformation (flip, rotate if needed)
3. Run `vpype_cli.execute()` with TOML profile
4. Extract GCode from vpype pipeline

**TOML Profile Format** (`pipeline/configs/grbl_a4_pen.toml`):

```toml
[gwrite]
default_profile = "grbl_a4_pen"

[gwrite.grbl_a4_pen]
unit = "mm"
offset_x = 0
offset_y = 0
document_start = "G21\nG90\n"
document_end = "M5\n"
segment_first = "{x:.3f} {y:.3f}\n"
segment = "G00 X{x:.3f} Y{y:.3f}\n"
line_end = "M3 S1000\nG01 X{x:.3f} Y{y:.3f}\n"
```

**Output**:

- `ctx.intermediates["gcode_lines"]` — List of GCode command strings

#### 3b. Legacy GCode (Deprecated): `gcode_gen`

Direct coordinate transformation without vpype.

**Config Keys**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `target_width_mm` | float | 190.0 | Drawing width (mm) |
| `target_height_mm` | float | 277.0 | Drawing height (mm) |
| `origin_x` | float | 5.0 | Left margin (mm) |
| `origin_y` | float | 5.0 | Bottom margin (mm) |
| `keep_aspect` | bool | True | Maintain aspect ratio |
| `feedrate_draw` | int | 1500 | Drawing speed (mm/min) |
| `feedrate_travel` | int | 3000 | Travel speed (mm/min) |
| `pen_down_cmd` | str | "M3 S1000" | GRBL pen-down command |
| `pen_up_cmd` | str | "M5" | GRBL pen-up command |
| `pen_delay_ms` | int | 100 | Wait after pen-down (ms) |

**Coordinate Transformation**:

```
Pixel Space (image):       (0, 0)────────── x (W)
                            │
                            │ y (H)
                            v

Plotter Space (mm):        (ox, oy)─────── x
                            │
                            │ y
                            v
```

Y-axis is flipped (image: top-left origin, plotter: bottom-left origin).

---

### 4. Optional: Send to GRBL Hardware

**Purpose**: Stream GCode to GRBL-compatible plotter via serial connection.

**Step Name**: `send_gcode`

**Config Keys**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `port` | str | "/dev/ttyUSB0" | Serial port (e.g., "/dev/ttyUSB0", "COM3") |
| `baudrate` | int | 115200 | Serial communication speed |
| `dry_run` | bool | True | Test mode (read commands, don't send) |

**Transport**:

- Uses `PyGrbl_Streamer` for GRBL communication
- Streams line-by-line with flow control
- Monitors for alarms/errors
- Logs progress to logger

**Output**:

- No intermediate (sends to hardware)

---

## Configuration Files

### Example Pipeline: Canny Edge Detection

**File**: `pipeline/configs/standard_pipeline.yaml`

```yaml
steps:
  # 1. Stylization
  - step: stylise
    config:
      source_path: /path/to/image.jpg
      style_res: 1024

  # 2. Vectorization
  - step: vectorise
    config:
      min_path_px: 10
      simplify_eps: 1.5

  # 3. GCode (native vpype)
  - step: gcode_gen
    config:
      profile: grbl_a4_pen
      target_width_mm: 190.0
      target_height_mm: 277.0
      keep_aspect: true
      linesort: true

  # 4. Send to GRBL (optional)
  - step: send_gcode
    enabled: false  # Set to true to actually send
    config:
      port: /dev/ttyUSB0
      baudrate: 115200
      dry_run: false
```

### Running the Pipeline

```bash
# Using main.py
python main.py \
  --config pipeline/configs/standard_pipeline.yaml \
  --input photo.jpg \
  --output photo.gcode \
  --verbose

# Dry-run (list steps, don't execute)
python main.py \
  --config pipeline/configs/standard_pipeline.yaml \
  --input photo.jpg \
  --output photo.gcode \
  --dry-run

# Using PipelineRunner directly
import yaml
from pipeline.core.runner import PipelineRunner

with open("pipeline/configs/standard_pipeline.yaml") as f:
    cfg = yaml.safe_load(f)
runner = PipelineRunner(cfg["steps"])
ctx = runner.run(ctx)  # where ctx = ImageContext
```

---

## Writing Custom Steps

All steps inherit from `PipelineStep`:

```python
from pipeline.core.base import ImageContext, PipelineStep

class MyCustomStep(PipelineStep):
    """
    Description of what your step does.
    
    Config keys:
        my_param (str): Description
        another_param (float): Description
    """
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Validate config, initialize resources
        
    def process(self, ctx: ImageContext) -> ImageContext:
        """Transform context and return modified copy."""
        # Read from ctx.intermediates
        # Write to ctx.intermediates
        # Return ctx
        return ctx
```

**Steps to register**:

1. Create `pipeline/steps/my_step.py` with `MyCustomStep` class
2. Add import to `pipeline/core/registry.py`
3. Add entry to `STEP_REGISTRY` dict
4. Create tests in `pipeline/tests/test_my_step.py`
5. Run `.venv/bin/pytest pipeline/tests/ -v` (all tests must pass)

---

## Device Detection

Steps with neural networks auto-detect compute devices:

```
Priority: CUDA > MPS (Metal) > CPU
```

Override with `device` config key:

- `"auto"` — Auto-detect (default)
- `"cuda"` — NVIDIA GPU (if available)
- `"mps"` — Apple Metal GPU (if on macOS)
- `"cpu"` — CPU fallback

---

## Performance Tips

1. **Resize input image** — Larger `style_res` = slower. Default 1024px is good balance.
2. **Simplification** — Increase `simplify_eps` for smoother, fewer paths (faster plotter time).
3. **Min path length** — Increase `min_path_px` to skip tiny artifacts.
4. **Linesort** — Enable for large path counts (> 100 paths) to reduce travel distance.
5. **GPU acceleration** — NN stylizers run ~10x faster on CUDA/MPS vs CPU.

---

## Troubleshooting

### "Step not found in registry"

→ Check step name matches `STEP_REGISTRY` keys in `pipeline/core/registry.py`

### "vpype not found"

→ Activate venv: `source .venv/bin/activate` or use `.venv/bin/python`

### "controlnet_aux not installed"

→ Run: `pip install controlnet-aux torch torchvision pillow`

### Tests failing after code changes

→ Run: `.venv/bin/pytest pipeline/tests/ -v`
→ All 62 tests must pass before committing

### Device detection issues

→ Check: `python -c "import torch; print(torch.cuda.is_available())"`
→ Or: `python -c "import torch; print(torch.backends.mps.is_available())"`

---

## References

- **vpype** — <https://github.com/abey79/vpype>
- **vpype-gcode** — <https://github.com/abey79/vpype-gcode>
- **controlnet-aux** — <https://github.com/huggingface/controlnet_aux>
- **GRBL** — <https://github.com/gnea/grbl>
