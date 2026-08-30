# Plotter Pipeline

> ⚠️ **Work in progress** — see [../TODO.md](../TODO.md) for known open issues
> (install-extras vs. `pyproject.toml`, GUI port, stale example config,
> missing `plotter.yaml`).

Image-to-GCode pipeline for the pen plotter. Takes any photo or image as
input, applies an optional stylization step, vectorizes the result, and
outputs GCode for GRBL.

For where this fits in the overall bring-up, see
[../testing.md → Phase 3](../testing.md#phase-3--pipeline-software-tests).

---

## Table of Contents

1. [Quickstart](#quickstart)
2. [Installation](#installation)
3. [Entry Points](#entry-points)
4. [Config File Format](#config-file-format)
5. [Available Steps](#available-steps)
6. [Adding Custom Steps](#adding-custom-steps)
7. [Overriding Paths via CLI](#overriding-paths-via-cli)
8. [Alternative tools](#alternative-tools)
9. [License](#license)

---

## Quickstart

**Requirements:** Python 3.13 — install with `brew install python@3.13` on macOS.

> ⚠️ **Python 3.14 is not supported.** `vpype 1.15.x` requires Python `<3.14`.
> On macOS, `python3` often resolves to 3.14 — always use `python3.13` explicitly.

```bash
# 1. Create virtual environment and install dependencies
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip "setuptools<82" wheel
.venv/bin/pip install -e "pipeline/[gui]"   # core + web GUI; add ,diffusers for SD

# 2. Run the pipeline
.venv/bin/pipeline-run \
    --config pipeline/configs/standard_pipeline.yaml \
    --input  pipeline/input/testimage.png \
    --output output/result.gcode
```

The entry point commands carry the `.venv` interpreter in their shebang —
no manual `source .venv/bin/activate` required.

For models behind the HuggingFace gate (FLUX, SD3, some ControlNet weights):

```bash
.venv/bin/get-hf-token
```

---

## Installation

### Requirements

- Python **3.13** — vpype 1.15.x requires Python `>=3.11,<3.14`; Python 3.14 is **not supported**
  - macOS: `brew install python@3.13`
  - Linux: `sudo apt install python3.13 python3.13-venv`
  - Windows: download from [python.org](https://www.python.org/downloads/)

> ⚠️ On macOS, `python3` and `python` often resolve to the latest system Python (currently 3.14).
> Always use `python3.13` explicitly when creating the venv.

### Create the virtual environment

```bash
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip "setuptools<82" wheel
```

### Install the pipeline package

```bash
# Core only — CLI, OpenCV + NN stylizers, vectorise, G-code
.venv/bin/pip install -e pipeline/

# Core + web GUI (recommended default)
.venv/bin/pip install -e "pipeline/[gui]"

# Add the Stable Diffusion backends (ControlNet, Img2Img)
.venv/bin/pip install -e "pipeline/[gui,diffusers]"

# Everything including dev/test tools
.venv/bin/pip install -e "pipeline/[gui,diffusers,dev]"
```

The `-e` flag installs in **editable mode** — changes to source files are
reflected immediately without reinstalling.

### Upgrade an existing installation

```bash
.venv/bin/pip install --upgrade pip "setuptools<82" wheel
.venv/bin/pip install -e "pipeline/[gui]"
```

To start completely fresh:

```bash
rm -rf .venv
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip "setuptools<82" wheel
.venv/bin/pip install -e "pipeline/[gui]"
```

### Windows

Replace `.venv/bin/` with `.venv\Scripts\` in all commands:

```powershell
python -m venv .venv
.venv\Scripts\pip install --upgrade pip "setuptools<82" wheel
.venv\Scripts\pip install -e "pipeline/[gui]"
.venv\Scripts\pipeline-run --config pipeline/configs/standard_pipeline.yaml
```

### GPU acceleration (CUDA)

After the standard install, replace the CPU torch build:

```bash
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## Entry Points

After installation, pip registers four commands in `.venv/bin/`
(Windows: `.venv\Scripts\`). They require no shell activation.

### `pipeline-run` — Run the pipeline

```bash
.venv/bin/pipeline-run --config pipeline/configs/standard_pipeline.yaml --input input/photo.jpg
```

| Option | Description |
| --- | --- |
| `--config YAML` | Pipeline config file — **required** |
| `--input IMAGE` | Input image path (jpg, png, …) |
| `--output FILE` | Output file path (gcode, png, svg, …) |
| `--dry-run` | List and validate steps without executing |
| `-v, --verbose` | Debug-level logging |

### `pipeline-server` — GUI web server

Starts the FastAPI-based Pipeline Manager GUI at `http://127.0.0.1:8000`
(override with `--host` / `--port`).
Requires the `gui` extras: `.venv/bin/pip install -e "pipeline/[gui]"`.

```bash
.venv/bin/pipeline-server
.venv/bin/pipeline-server --port 9000
.venv/bin/pipeline-server --input-dir pipeline/input --tools-dir pipeline/configs
```

### `get-hf-token` — Save a HuggingFace token

```bash
.venv/bin/get-hf-token
```

Interactive prompt to store an API token for gated HuggingFace models.

### `pipeline-test` — Run the test suite

```bash
.venv/bin/pipeline-test                  # all tests
.venv/bin/pipeline-test -k stylize       # filter by name
.venv/bin/pipeline-test -x               # stop on first failure
```

---

## Config File Format

Pipelines are defined as YAML files (`.yaml`) or TOML files (`.toml`) in
`pipeline/configs/`. Both formats are supported.

### YAML pipeline config

A YAML config has a `steps` list. Each entry specifies the step name and its
parameters:

```yaml
# pipeline/configs/my_pipeline.yaml

steps:
  - step: load_image
    config:
      source_path: input/photo.jpg   # static path (overridable via --input)
      style_res: 1024                # max side length after scaling (0 = full)

  - step: stylise_canny
    config:
      canny_low: 50
      canny_high: 150

  - step: vectorise
    config:
      min_path_px: 10
      simplify_eps: 1.5

  - step: gcode_from_svg
    config:
      profile: grbl_a4_pen           # profile name from TOML file
      target_width_mm: 190.0
      target_height_mm: 277.0

  - step: save_gcode
    config:
      output_path: output/result.gcode   # static path (overridable via --output)

  - step: send_gcode
    enabled: false                       # disabled steps are skipped
    config:
      port: /dev/tty.usbmodem1101
      baud: 115200
```

#### Step entry keys

| Key | Required | Description |
| --- | --- | --- |
| `step` | ✅ | Step name — must match a key in `STEP_REGISTRY` |
| `config` | ✅ | Parameters for this step (can be `{}`) |
| `label` | — | Custom display name shown in log output |
| `enabled` | — | Set `false` to skip this step (default: `true`) |

### TOML GCode profile

`.toml` files define GCode output templates (vpype-gcode-compatible format).
They are referenced by `gcode_from_svg` steps via the `toml_path` /
`profile` config keys. The default profile is
`pipeline/configs/grbl_a4_pen.toml`.

Key TOML sections:

```toml
[gwrite]
default_profile = "my_profile"

[gwrite.my_profile]
unit          = "mm"
vertical_flip = true       # SVG origin top-left → GCode origin bottom-left
offset_x      = 5.0        # left margin in mm
offset_y      = 5.0        # bottom margin in mm

document_start = """..."""  # GCode header (initialization, homing, pen up)
segment_first  = """..."""  # emitted before first point of each path
segment        = "G1 X{x:.3f} Y{y:.3f}\n"
segment_last   = "G1 X{x:.3f} Y{y:.3f}\n"
line_end       = "...\n"    # emitted after each path (pen up)
document_end   = """..."""  # GCode footer
```

Available template variables: `{x}`, `{y}` (coordinates in mm).

---

## Available Steps

### Image I/O

#### `load_image`

Loads the source image from disk into `ctx.image` (PIL, RGB).
Must be the first step in any image pipeline.

| Config key | Default | Description |
| --- | --- | --- |
| `source_path` | — | Static input path. Overridden by `--input` at runtime. |
| `style_res` | `1024` | Max side length in pixels after scaling. `0` = full resolution. |

#### `save_image`

Writes `ctx.image` to disk. Useful for saving intermediate results or as
the final step of an image-only pipeline.

| Config key | Default | Description |
| --- | --- | --- |
| `output_path` | — | Static output path. Overridden by `--output` at runtime. |
| `quality` | `95` | JPEG quality (1–95). Ignored for other formats. |
| `compress_level` | `6` | PNG compression level (0–9). Ignored for other formats. |
| `overwrite` | `true` | Set `false` to raise an error if the file already exists. |

---

### Stylizers — OpenCV (no GPU required)

These steps convert `ctx.image` to a binary edge map (`ctx.intermediates["binary"]`).
They require only numpy and opencv — no GPU, no model download.

#### `stylise_canny`

Classic Canny edge detector.

| Config key | Default | Description |
| --- | --- | --- |
| `canny_low` | `50` | Lower hysteresis threshold |
| `canny_high` | `150` | Upper hysteresis threshold |
| `canny_blur` | `3` | Gaussian blur kernel size (odd number) |

#### `stylise_xdog`

eXtended Difference-of-Gaussians (XDoG) — produces clean, sketch-like
line drawings. Good general-purpose stylizer without neural networks.
(Winnemöller et al. 2012)

| Config key | Default | Description |
| --- | --- | --- |
| `sigma` | `0.4` | Inner Gaussian σ |
| `k_sigma` | `1.6` | Outer Gaussian factor (k × σ) |
| `epsilon` | `0.0` | Threshold; `0` = adaptive (90th percentile) |
| `phi` | `10.0` | Sharpness of the soft threshold |
| `threshold` | `20.0` | Final binarization threshold (0–255); `0` = skip |

#### `stylise_adaptive`

OpenCV adaptive threshold — good for documents and high-contrast images.

| Config key | Default | Description |
| --- | --- | --- |
| `block_size` | `11` | Neighborhood size (odd number ≥ 3) |
| `adapt_c` | `2.0` | Constant subtracted from the mean |
| `adapt_method` | `"gaussian"` | `"gaussian"` or `"mean"` |
| `adapt_blur` | `0` | Optional pre-blur kernel size (0 = disabled) |

---

### Stylizers — Neural Network (GPU recommended)

These steps download pre-trained models from HuggingFace on first use.
Their dependencies (`controlnet-aux`, `torch`, `torchvision`, `timm`,
`onnxruntime`) are already in the core `dependencies` — no extra needed
beyond the standard install. Only the diffusion stylizers below
(`stylise_controlnet`, `stylise_img2img`) additionally need `[diffusers]`.

All NN stylizers share these common config keys:

| Config key | Default | Description |
| --- | --- | --- |
| `device` | `"auto"` | `"auto"` (cuda › mps › cpu), `"cpu"`, `"cuda"`, `"mps"` |
| `threshold` | `128` | Binarization threshold applied to the model output (0–255) |
| `model_path` | `None` | Local model path; if `None` the HF repo is used |

#### `stylise_hed`

Holistically-nested Edge Detection (HED). Produces smooth, continuous
edge maps. Well-suited for portraits and organic shapes.

No additional config keys beyond the common ones above.

#### `stylise_dexined`

DexiNed-based edge detection (coarse lineart mode). Produces thick,
expressive contours.

No additional config keys beyond the common ones above.

#### `stylise_lineart`

ControlNet-v1.1 Lineart Preprocessor. Produces clean, fine-grain line
drawings — the recommended choice for most photos.

| Config key | Default | Description |
| --- | --- | --- |
| `lineart_coarse` | `false` | Coarse mode (thicker, bolder lines) |
| `lineart_detect_res` | `512` | Internal detection resolution |
| `lineart_image_res` | `512` | Output image resolution |

#### `stylise_informative`

Informative Drawings (Chan et al. CVPR 2022). Converts photos to clean,
artistic sketches that preserve semantic structure.

Tries ONNX first (`pip install onnxruntime`), falls back to PyTorch.

No additional config keys beyond the common ones above.

---

### Stylizers — Diffusion (HuggingFace token required for some models)

These steps require `diffusers`, `transformers`, `torch`, `accelerate`.
Install via `.venv/bin/pip install -e "pipeline/[gui,diffusers]"`.

For gated models (FLUX, SD3): run `.venv/bin/get-hf-token` first.

All diffusion stylizers share these common config keys:

| Config key | Default | Description |
| --- | --- | --- |
| `prompt` | — | Style guidance text |
| `negative_prompt` | `"blurry, low quality, distorted"` | What to avoid |
| `num_inference_steps` | `20` | Quality vs. speed trade-off |
| `guidance_scale` | `7.5` | How strongly the prompt is followed (1–15) |
| `device` | `"auto"` | `"auto"`, `"cpu"`, `"cuda"`, `"mps"` |
| `enable_model_cpu_offload` | `false` | Reduce VRAM at cost of speed |
| `binary_threshold` | `128` | Binarization threshold (0–255) |
| `hf_token_path` | `None` | Path to HF token file (default: `.hf_token` in project root) |

#### `stylise_controlnet`

Style transfer via ControlNet + Stable Diffusion 1.5. Applies a
text-guided artistic style while preserving structure from the input image.

| Config key | Default | Description |
| --- | --- | --- |
| `controlnet_type` | `"lineart"` | Structure guide: `canny`, `lineart`, `softedge`, `scribble`, `pose`, `depth`, `normal`, `seg` |
| `base_model` | `"runwayml/stable-diffusion-v1-5"` | HF model ID |

#### `stylise_img2img`

Lighter alternative to ControlNet — standard SD 1.5 img2img without
conditioning. Lower VRAM usage and faster than ControlNet.

| Config key | Default | Description |
| --- | --- | --- |
| `strength` | `0.7` | Modification intensity (0.0 = no change, 1.0 = full generation) |
| `model_id` | `"stable-diffusion-v1-5/stable-diffusion-v1-5"` | HF model ID |

---

### Vectorization

#### `vectorise`

Converts the binary edge map from a stylizer into a list of vector paths.
Can also be used directly after `load_image` without a stylizer (binarizes
`ctx.image` automatically in that case).

| Config key | Default | Description |
| --- | --- | --- |
| `min_path_px` | `10` | Minimum contour arc length in pixels — shorter paths are discarded |
| `simplify_eps` | `1.5` | Ramer-Douglas-Peucker tolerance in pixels (`0` = no simplification) |
| `binary_threshold` | `128` | Threshold used when binarizing `ctx.image` directly (no prior stylizer) |

---

### GCode Generation

#### `gcode_from_svg`  *(recommended)*

Generates GCode using a TOML profile (vpype-gcode-compatible format).
The default profile is `pipeline/configs/grbl_a4_pen.toml`.

| Config key | Default | Description |
| --- | --- | --- |
| `profile` | `"grbl_a4_pen"` | Profile name inside the TOML file |
| `toml_path` | built-in default | Path to TOML profile file |
| `target_width_mm` | `190.0` | Drawing width in mm (A4 minus margins) |
| `target_height_mm` | `277.0` | Drawing height in mm (A4 minus margins) |
| `keep_aspect` | `true` | Maintain image aspect ratio |
| `linesort` | `true` | Optimize path order to minimize travel distance |

#### `gcode_gen`  *(legacy)*

Generates GCode with a built-in coordinate transformation — no TOML profile.
Use `gcode_from_svg` for new pipelines; `gcode_gen` is kept for
backward compatibility.

| Config key | Default | Description |
| --- | --- | --- |
| `target_width_mm` | `180.0` | Drawing width in mm |
| `target_height_mm` | `250.0` | Drawing height in mm |
| `origin_x` | `5.0` | Left margin in mm |
| `origin_y` | `5.0` | Bottom margin in mm |
| `keep_aspect` | `true` | Maintain aspect ratio |
| `feedrate_draw` | `1500` | Drawing feedrate in mm/min |
| `feedrate_travel` | `3000` | Travel feedrate in mm/min |
| `pen_down_cmd` | `"M5"` | GRBL command for pen down |
| `pen_up_cmd` | `"M3 S1000"` | GRBL command for pen up |
| `pen_delay_ms` | `100` | Wait after pen down (ms) |

---

### GCode Output

#### `save_gcode`

Writes the GCode lines to a file. Output path resolution:

1. `ctx.metadata["output_path"]` — set via `--output` at runtime
2. `config["output_path"]` — static path in the YAML config

| Config key | Default | Description |
| --- | --- | --- |
| `output_path` | — | Static fallback output path |

#### `send_gcode`

Sends GCode directly to a GRBL controller via serial port using
`pygrbl_streamer`. Typically kept `enabled: false` in the config and
enabled only for actual plotting.

| Config key | Default | Description |
| --- | --- | --- |
| `port` | `"/dev/tty.usbmodem1101"` | Serial port |
| `baud` | `115200` | Baud rate |
| `dry_run` | `false` | Log GCode without sending to the port |
| `completion_timeout` | `300` | Timeout per GCode line in seconds |

---

## Adding Custom Steps

### 1. Create the step class

Create `pipeline/steps/my_step.py` and inherit from `PipelineStep`:

```python
# pipeline/steps/my_step.py
from __future__ import annotations
from pipeline.core.base import ImageContext, PipelineStep

class MyStep(PipelineStep):
    """
    One-line description.

    Config keys   Default   Description
    ------------------------------------
    my_param      42        What this controls.
    """

    def requires(self) -> list[str]:
        # Declare which context keys must be present before this step runs.
        # Valid values: "image", "intermediates.binary", "intermediates.paths",
        #               "intermediates.gcode_lines"
        return ["image"]

    def process(self, ctx: ImageContext) -> ImageContext:
        my_param = self.config.get("my_param", 42)

        # Read from ctx
        image = ctx.image  # PIL.Image

        # Write results back
        import numpy as np
        ctx.intermediates["binary"] = np.zeros((100, 100), dtype="uint8")

        return ctx
```

### 2. Register the step

Add it to `STEP_REGISTRY` in `pipeline/core/registry.py`:

```python
from pipeline.steps.my_step import MyStep

STEP_REGISTRY: dict[str, type["PipelineStep"]] = {
    # ... existing entries ...
    "my_step": MyStep,
}
```

### 3. Use it in a config

```yaml
steps:
  - step: load_image
    config:
      source_path: input/photo.jpg

  - step: my_step
    config:
      my_param: 99

  - step: vectorise
    config: {}
```

### 4. Add tests

Create `pipeline/tests/test_my_step.py`:

```python
from pipeline.core.base import ImageContext
from pipeline.steps.my_step import MyStep
from PIL import Image

def test_my_step_basic():
    step = MyStep(config={"my_param": 99})
    ctx = ImageContext()
    ctx.image = Image.new("RGB", (64, 64), color=(128, 128, 128))
    result = step.process(ctx)
    assert "binary" in result.intermediates
```

Run all tests:

```bash
.venv/bin/pipeline-test
```

---

## Overriding Paths via CLI

The `load_image` and `save_gcode` / `save_image` steps support a
**two-level path resolution** that lets the CLI override static paths
defined in the YAML config at runtime.

### Priority order

| Priority | Source | How to set |
| --- | --- | --- |
| 1 (highest) | `ctx.metadata["source_path"]` | `--input IMAGE` on the CLI |
| 2 | `config["source_path"]` in YAML | Static path in the config file |

The same pattern applies for `output_path`:

| Priority | Source | How to set |
| --- | --- | --- |
| 1 (highest) | `ctx.metadata["output_path"]` | `--output FILE` on the CLI |
| 2 | `config["output_path"]` in YAML | Static path in the config file |

### Examples

**Config has a static path, CLI overrides it:**

```yaml
# pipeline/configs/my_pipeline.yaml
steps:
  - step: load_image
    config:
      source_path: input/default.jpg   # used when no --input is given
  - step: save_gcode
    config:
      output_path: output/default.gcode
```

```bash
# Override both paths at runtime:
.venv/bin/pipeline-run \
    --config pipeline/configs/my_pipeline.yaml \
    --input  input/my_photo.jpg \
    --output output/my_photo.gcode
```

**Config has no static path, path is required from CLI:**

```yaml
steps:
  - step: load_image
    config: {}   # no source_path → --input is required
  - step: save_gcode
    config: {}   # no output_path → --output is required
```

```bash
.venv/bin/pipeline-run \
    --config pipeline/configs/my_pipeline.yaml \
    --input  input/my_photo.jpg \
    --output output/my_photo.gcode
```

If neither the config nor the CLI provides a path, the step raises a
`ValueError` with a descriptive message.

### Programmatic override (Python API)

The same mechanism works when using the pipeline directly from Python:

```python
from pathlib import Path
from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner

runner = PipelineRunner.from_yaml(Path("pipeline/configs/my_pipeline.yaml"))

ctx = ImageContext(metadata={
    "source_path": Path("input/my_photo.jpg"),
    "output_path": Path("output/my_photo.gcode"),
})

runner.run(ctx)
```

---

## Alternative tools

This pipeline is the supported path, but the plotter is a plain GRBL machine —
any SVG→G-code and G-code-sender toolchain works.

**SVG / vector graphics → G-code**

- [Inkscape](https://inkscape.org/) with the [Gcodetools](https://github.com/cnc-club/gcodetools) extension
- [vpype](https://github.com/abey79/vpype) + [vpype-gcode](https://github.com/plottertools/vpype-gcode) (this project uses both internally)
- [svg2gcode](https://github.com/sameer/svg2gcode) — simple CLI converter

Configure the tool to emit `M3 S1000` (pen UP) and `M5` (pen DOWN) at path
boundaries — see the profile in [configs/grbl_a4_pen.toml](configs/grbl_a4_pen.toml).

**Sending G-code to the plotter**

- [UGS (Universal G-code Sender)](https://universalgcodesender.com/) — cross-platform GUI
- [bCNC](https://github.com/vlachoudis/bCNC) — Python-based, feature-rich
- [CNCjs](https://cnc.js.org/) — browser-based, runs as a Node.js server

Connect at 115200 baud. Only one process may hold the serial port at a time.

---

## License

This pipeline is licensed **MIT** ([LICENSE](LICENSE)). It talks to GRBL only
over the serial port (no shared code with the GPLv3 firmware), so it is not
bound by GRBL's copyleft. See the
[project-wide licensing table](../README.md#license).
