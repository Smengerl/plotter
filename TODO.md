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
`testing.md` and `firmware/README.md` were updated to match, and
`firmware/src/config.h` is now actually wired into the build (`-include`;
it overrides `HOMING_CYCLE_0` and asserts `VARIABLE_SPINDLE`, machine
params via `$`). Remaining:

- [ ] **Optical-endstop polarity / `$5` is unverified.** In GRBL 1.1,
  `$5=1` → "pin HIGH = triggered", `$5=0` → "pin LOW = triggered". Measure
  the real module output (beam clear vs. blocked) and set `$5` on the board.
  Also confirm the two parallel X switches can share D9 without an output
  clash (open-collector / wired-OR).
- [ ] **Tune the solenoid holding current.** `grbl_a4_pen.toml` now pulls the
  pen up at `S1000` then holds at `S350` (~35 % PWM). Find the lowest hold
  value that reliably keeps the pen up during travel, and check the coil is
  no more than warm after a long plot. Update `S_HOLD` in both
  `document_start` and `line_end`.
- [ ] **`$130` (X max travel) must be taught** — testing.md TC5b-G. Verify the
  teach procedure (home X_MIN, jog to X_MAX, read MPos) works on the hardware.
- [ ] **Verify homing + solenoid on the real board** now that `config.h` is
  wired in: `$H` homes X only (no Z/Y move), `M3`/`M5` drive the pen on D11.
- [ ] **`testing.md` TC9-G M3/M5 order** — `M5` (pen down) → dwell → `M3 S1000`
  (pen up). Confirm against the assembled hardware.
- [ ] **GRBL startup banner** — `testing.md` §2.0 shows
  `Grbl 1.1h ['$' for help]` + `[MSG:Caution: Unlocked]`; confirm the exact
  strings the shipped build prints.

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
