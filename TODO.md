# TODO — known open issues

**Status: the whole project is work in progress.** Hardware wiring, firmware
configuration and the software pipeline are still changing, and several docs
have drifted apart during past refactors. This file is the single list of
known contradictions and errors that still need to be resolved.

Inline `TODO:` markers throughout the docs point back here.

---

## Hardware / firmware

- [ ] **Endstop wiring is described two incompatible ways.**
  - `firmware/src/config.h`, `BOM.md` and `electronics.md` §Endstops:
    **2 optical endstops total** — `D9 = X_MIN`, `D10 = Y_MIN`, both axes home
    toward MIN (`HOMING_CYCLE_0 = X | Y`).
  - `firmware/test/tc2_x_endstops/` + `testing.md` TC2 / TC6-G +
    `electronics.md` verification table: **2 endstops on the X axis**
    (`D10 = X_MAX`), no Y endstop.
  - These are mutually exclusive. Decide the real layout, then fix `testing.md`
    TC2/TC6-G, `electronics.md`, and the test sketch. Note: under GRBL 1.1 on
    the Uno, X and Y each have exactly one limit pin — "X_MAX on D10" only
    exists in the standalone test sketch.
- [ ] **`testing.md` TC9-G vs. the old firmware/README TC9-G** used opposite
  M3/M5 order. `testing.md` now has `M5` (pen down) → dwell → `M3 S1000`
  (pen up); confirm this matches the assembled hardware and the
  `grbl_a4_pen.toml` templates.
- [ ] **GRBL startup banner**: `testing.md` §2.0 shows
  `Grbl 1.1h ['$' for help]` + `[MSG:Caution: Unlocked]`; confirm the exact
  strings the shipped build prints.

## Pipeline configs

- [ ] **`pipeline/configs/standard_pipeline.yaml` is stale.**
  `name`/`description` say "ControlNet … style transfer" but there is no
  stylizer step; the file header comment says "Informative Drawings"; it uses
  the legacy `gcode_gen` step; it ends in `save_gcode`/`send_gcode`, which is
  incompatible with the GUI model (regular pipelines must produce a PNG).
  It is still referenced as the main example in `pipeline/README.md` and
  `testing.md` TC-P3 / Phase 4.
- [ ] **No `pipeline/configs/plotter.yaml`.** `gui/config.py`
  (`plotter_pipeline_stem = "plotter"`) and `routers/plotter.py` require a
  pipeline with stem `plotter`; "Send to Plotter" returns HTTP 422 without it.
  Add one (`load_image → vectorise → gcode_from_svg → send_gcode`).

## Packaging / installation

- [ ] **`PyYAML` (and `fastapi`/`uvicorn`) live only in the `gui` extra.**
  The docs now use `pip install -e "pipeline/[gui]"` as the baseline, but a
  bare `pip install -e pipeline/` still cannot run `pipeline-run` on a YAML
  config (`PipelineRunner.from_yaml` needs PyYAML). Move `PyYAML` into core
  `dependencies` in `pipeline/pyproject.toml`.

## Docs / tests

- [ ] **The pipeline-config smoke test is completely non-functional.**
  - `pipeline/tests/run_all_pipeline_configs.py` has a second module
    docstring pasted in after `import argparse`, and the real imports
    (`from pathlib import Path`, `import sys`, colour constants,
    `_CONFIGS_DIR` / `_TESTS_DIR`) are missing entirely → it dies with
    `NameError: name 'Path' is not defined` on line 79, before doing
    anything.
  - `pipeline/tests/run_all_tests.py` hard-codes
    `RUN_STYLIZERS = ROOT / "run_all_stylizers.py"`, which does not exist,
    so it silently skips the smoke phase and only runs pytest.
  - Net effect: `testing.md` TC-P2 cannot pass as written. Either fix
    `run_all_pipeline_configs.py` (imports + point it at
    `pipeline/tests/pipeline_configs/`) and repoint `run_all_tests.py`
    at it, or drop both and simplify TC-P2 to plain `pytest`.
  - (`--skip-stylizers` does exist — on `run_all_tests.py`, not on
    `run_all_pipeline_configs.py`; TC-P2 attaches it to the wrong script.)
- [ ] `pipeline/examples/run_examples.sh` is broken: the example block is
  duplicated verbatim; `--config ../configs/pipeline/examples/…` resolves to
  nothing; configs live in `pipeline/configs/`, not `pipeline/examples/`;
  `pipeline-run --version` is not a real flag. Either fix or delete.
