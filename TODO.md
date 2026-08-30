# TODO — known open issues

**Status: the whole project is work in progress.** Hardware wiring, firmware
configuration and the software pipeline are still changing, and several docs
have drifted apart during past refactors. This file is the single list of
known contradictions and errors that still need to be resolved.

Inline `TODO:` markers throughout the docs point back here.

---

## Hardware / firmware

The machine layout is now settled and captured in
[electronics.md → Machine configuration](electronics.md#machine-configuration-canonical):
**2 optical endstops both on X (X_MIN + X_MAX) on D9, no Y endstop, X-only
homing, solenoid on D11 via `VARIABLE_SPINDLE`.** `config.h`, `electronics.md`,
`testing.md` and `firmware/README.md` were updated to match. Remaining:

- [ ] **Optical-endstop polarity / `$5` is unverified.** `config.h` sets
  `DEFAULT_INVERT_LIMIT_PINS 1` with the rationale "HIGH when open, LOW when
  triggered" — but in GRBL 1.1 that polarity means `$5` should be **0**
  (`$5=1` → *HIGH* = triggered). Measure the real module output (beam clear
  vs. blocked), set `$5`, fix the comment. Also confirm the two parallel X
  switches can share D9 without an output clash (open-collector / wired-OR).
- [ ] **Reduced solenoid holding current — not yet implemented.** With PWM on
  D11 the pen-up drive can pull in at `S1000` then hold at ~`S350` to cut the
  coil heat. Change `line_end` (and `document_start`) in
  `pipeline/configs/grbl_a4_pen.toml` to `M3 S1000` → `G4 P0.05` → `M3 S350`,
  tune the hold value, verify coil temperature after a long plot. Firmware
  needs no change. Full write-up in electronics.md → "Solenoid pen lift".
- [ ] **`firmware/test/tc2_x_endstops` needs updating.** It reads X_MAX on D10;
  production wiring has both X switches on D9. Rework it to drive toward each
  end and let the operator confirm which end was reached (no second pin).
  Rename the sketch / PlatformIO env to `tc2_endstops`.
- [ ] **`config.h` `DEFAULT_X_MAX_TRAVEL` is a placeholder (220 mm).** Real
  value comes from testing.md TC5b-G ("teach") and lives in `$130`; verify
  the teach procedure works on the hardware.
- [ ] **`testing.md` TC9-G M3/M5 order** — `M5` (pen down) → dwell → `M3 S1000`
  (pen up). Confirm against the assembled hardware.
- [ ] **GRBL startup banner** — `testing.md` §2.0 shows
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
