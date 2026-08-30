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

## Documentation gaps

- [ ] **No schematic / wiring diagram.** `electronics.md` describes the 5 V/GND
  distribution board and the solenoid MOSFET circuit in text + ASCII only.
  Add a proper schematic (or at least annotated photos) for: the MOSFET
  gate/flyback/pull-down circuit, and how the two X optical endstops are
  combined onto D9.
- [ ] **No complete GRBL `$$` reference, and calibration is thin.**
  `firmware/README.md` has a first-run checklist of ~18 settings, but no full
  table of every `$n` with its meaning/units, and no guidance on: tuning
  `$100/$101` against a measured travel, `$120/$121` acceleration, direction
  inversion (`$3`), or squaring/skew of the drawing. `testing.md` TC5b-G
  covers only the X-length teach. Write a "GRBL settings & calibration"
  section (in `firmware/README.md` or a new `firmware/GRBL.md`).
- [ ] **`send_gcode` gives no success/failure feedback.** Neither the CLI nor
  the GUI reports whether a plot finished cleanly, stalled, or hit an alarm.
  Decide the mechanism (step raises on GRBL error / writes a status into
  `ctx`; GUI surfaces it in the log panel) and document it. See discussion in
  the session notes.

## Docs / tests

- [ ] `pipeline/examples/run_examples.sh` is broken: the example block is
  duplicated verbatim; `--config ../configs/pipeline/examples/…` resolves to
  nothing; configs live in `pipeline/configs/`, not `pipeline/examples/`;
  `pipeline-run --version` is not a real flag. Either fix or delete.
