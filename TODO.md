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
- [ ] `.gitignore` still contains `firmware/grbl/` although `firmware/grbl` is
  a registered submodule (`.gitmodules`). Harmless but confusing — remove.

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
- [ ] `pipeline/configs/xdog_sketch.yaml` has no `name:` field.

## Packaging / installation

- [ ] **`pipeline/README.md` install instructions vs. `pyproject.toml`.**
  `fastapi`, `uvicorn` and `PyYAML` live in the optional `gui` extra, not in
  core `dependencies`. So `pip install -e pipeline/` (documented as "core +
  GUI") cannot run `pipeline-server`, and cannot even run `pipeline-run` on a
  YAML config (needs PyYAML). Either move PyYAML to core deps or fix the docs
  (`pip install -e "pipeline/[gui]"`).
- [ ] **`setup_pipeline.sh` does not exist** (removed in the pyproject
  migration) but is still referenced by `testing.md` Phase 3 prerequisites
  and `.github/copilot-instructions.md`.
- [ ] **`requirements.txt` does not exist** but `.github/copilot-instructions.md`
  documents its structure and `testing.md` TC-P1 failure hints reference it.
- [ ] **Test count "62"** is hard-coded in `testing.md` TC-P1 and
  `.github/copilot-instructions.md`; the suite currently has ~109 test
  functions. Prefer "all tests pass" over a fixed number.
- [ ] **License mismatch**: `LICENSE.txt` + root `README.md` say CC BY-SA 4.0
  (whole project); `pipeline/pyproject.toml` says MIT. Decide the split
  (e.g. hardware/docs CC BY-SA, code MIT) and state it explicitly.
- [ ] `pipeline/README.md` NN-stylizer section claims `controlnet-aux`,
  `torch`, `torchvision` are "included in the `diffusers` extras" — they are
  in core `dependencies`; only ControlNet/Img2Img (SD) need `[diffusers]`.

## Docs / tests

- [ ] **GUI port**: `pipeline/README.md` says `http://localhost:8080`;
  `gui/config.py` / `server.py` default to `8000`.
- [ ] **`pipeline/tests/README.md` paths are stale**: `pipeline_tests/…` →
  `pipeline/tests/…`; `run_all_stylizers.py` does not exist (it is
  `run_all_tests.py`); the test image is `pipeline/input/testimage.png`, not
  `pipeline/tests/testimage.png`. Same wrong image path in `testing.md`
  TC-P2 / TC-P3 / TC-E*.
- [ ] `pipeline/tests/run_all_pipeline_configs.py` docstring names four
  different config directories; align it with what the script actually does
  (`pipeline/tests/pipeline_configs/stylize_*.yaml`).
- [ ] `testing.md` TC-P2 mentions a `--skip-stylizers` flag — verify it
  exists in `run_all_pipeline_configs.py`.
- [ ] `pipeline/examples/run_examples.sh` is broken: the example block is
  duplicated verbatim; `--config ../configs/pipeline/examples/…` resolves to
  nothing; configs live in `pipeline/configs/`, not `pipeline/examples/`;
  `pipeline-run --version` is not a real flag. Either fix or delete.

## Minor

- [ ] Root `README.md` "Authors": `https://github.com/Smenger` → `Smengerl`.
- [ ] Root `README.md` BOM section mentions "McMaster" references;
  `BOM.md` only has AliExpress links.
- [ ] Root `README.md` §Assembly: list items are all numbered `1.`.
