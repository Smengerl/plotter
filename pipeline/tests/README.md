
# pipeline/tests — test pipelines and smoke runners

This directory contains unit tests and a set of pipeline configuration
YAML files used for smoke testing the pipeline steps. Two helper scripts
are provided:

- `run_all_pipeline_configs.py` — executes every YAML in
  `pipeline_tests/pipeline_configs/` using the `PipelineRunner`.
- `run_all_stylizers.py` — legacy stylizer smoke runner (kept for
  backwards compatibility).

## Important behavior

The unified pipeline config runner intentionally does NOT preload the
image into the pipeline context. Instead it sets:

```python
ctx = ImageContext(metadata={"source_path": Path("pipeline/tests/testimage.png")})
```

 This enforces the requirement that pipelines be self-contained: if a
 YAML needs to load an image from disk it must include a `load_image`
 step which reads `metadata['source_path']`. If a pipeline requires a
 pre-loaded `ctx.image`, the YAML must be designed accordingly and tests
 should run it by a custom harness that provides `ctx.image`.

## Why

This makes test behavior explicit and prevents silent inconsistencies:
the runner no longer overrides a pipeline's configured behavior by
mutating or pre-loading the image.

## Running tests

Unit tests (fast):

```bash
.venv/bin/pytest pipeline/tests/ -v
```

Full smoke tests (may download model weights):

```bash
python pipeline/tests/run_all_pipeline_configs.py
```

If you want the old behavior where the runner preloads the image for
convenience, run `run_all_stylizers.py` instead — but prefer fixing the
YAML to be explicit about `load_image` in the long term.
