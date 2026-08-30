# pipeline/tests — unit tests and smoke runners

For where these tests fit into bring-up, see
[../../testing.md → Phase 3](../../testing.md#phase-3--pipeline-software-tests).

This directory contains the pytest unit tests (`test_*.py`) plus a set of
pipeline configuration YAMLs (`pipeline_configs/`) used for smoke testing the
pipeline steps. Two helper scripts are provided:

- `run_all_pipeline_configs.py` — runs each `*.yaml` in
  `pipeline/tests/pipeline_configs/` through `PipelineRunner`. `--fast`
  restricts it to the CPU-only configs (no model downloads).
- `run_all_tests.py` — unified runner: pytest for `test_*.py`, then the smoke
  test (`--skip-smoke` / `--fast` / `--pytest-args "..."`).

## Important behavior

The smoke runner intentionally does NOT preload the image into the pipeline
context. Instead it sets only the source path:

```python
ctx = ImageContext(metadata={"source_path": Path("pipeline/input/testimage.png")})
```

This enforces that pipelines are self-contained: a YAML that needs an image
from disk must include a `load_image` step which reads
`metadata['source_path']`. A pipeline that requires a pre-loaded `ctx.image`
must be run by a custom harness that provides it.

## Why

This makes test behavior explicit and prevents silent inconsistencies: the
runner no longer overrides a pipeline's configured behavior by mutating or
pre-loading the image.

## Running tests

Unit tests (fast):

```bash
.venv/bin/pytest pipeline/tests/ -v
```

Config smoke test (`--fast` = CPU-only, no downloads):

```bash
.venv/bin/python pipeline/tests/run_all_pipeline_configs.py --fast
```
