# Test & Commissioning Guide

> ⚠️ **Work in progress.** Some steps below still contain known contradictions
> and stale references, marked inline with `TODO:` and tracked in
> [TODO.md](TODO.md). Read those markers before relying on the affected step.

**This document is the single source for the whole test and commissioning
sequence.** Other files (`README.md`, `firmware/README.md`, `electronics.md`,
`pipeline/README.md`) only link here — they do not repeat the procedure.

The sequence is split into phases:

| Phase | What is tested | TCs | Purpose |
|-------|----------------|-----|---------|
| [Phase 0](#phase-0--prerequisites) | Assembly, wiring, software install | — | Bring the machine and host into a testable state |
| [Phase 1](#phase-1--standalone-arduino-tests-no-grbl) | Standalone Arduino sketch per TC | TC1–TC4 | Test individual hardware components directly, no GRBL involved |
| [Phase 2](#phase-2--grbl-integration-tests) | GRBL (production firmware) | TC5-G–TC9-G | Verify the full hardware system through GRBL and G-code |
| [Phase 3](#phase-3--pipeline-software-tests) | Host-side Python pipeline | TC-P1–TC-P3 | Verify the image-processing and G-code generation pipeline |
| [Phase 4](#phase-4--full-system-end-to-end-plot) | Complete system (host + plotter) | TC-E1–TC-E3 | Run a real pipeline and send the output to the connected plotter |

Run the phases in order:

- Phase 1 first — fastest to flash, easiest to debug individual hardware signals.
- Phase 2 only after all Phase 1 tests pass.
- Phase 3 runs independently on the host PC and does **not** require the plotter to be connected.
- Phase 4 requires both Phase 2 (hardware verified) and Phase 3 (pipeline verified) to have passed.

---

## Phase 0 — Prerequisites

**Mechanics & electronics**

1. Frame printed and assembled — see [README.md → Assembly](README.md#assembly).
2. Electronics wired — see [electronics.md → Wiring steps](electronics.md#wiring-steps).
3. 12 V power supply connected to the CNC Shield screw terminals; USB cable to the Arduino.
4. PlatformIO installed (`pio` CLI or the VS Code extension).
5. A serial monitor ready (`pio device monitor`, or any 115200-baud terminal).

**Host software** (only needed from Phase 3 onward)

6. Python **3.13** (not 3.14 — `vpype` requires `<3.14`) and the project
   virtualenv installed — see
   [pipeline/README.md → Installation](pipeline/README.md#installation).

**GRBL settings** (only needed from Phase 2 onward)

7. After flashing GRBL, walk through the first-run parameter checklist and
   verify with `$$` — see
   [firmware/README.md → Key GRBL settings](firmware/README.md#key-grbl-settings-first-run-checklist).

---

## Phase 1 — Standalone Arduino Tests (no GRBL)

Each test is a self-contained Arduino sketch.  
Flash it, open the serial monitor at **115200 baud**, and follow the on-screen prompts.  
The sketch guides you through each step and prints `PASS` or `FAIL` at the end.

```
firmware/
└── test/
    ├── tc1_x_axis/       tc1_x_axis.cpp
    ├── tc2_x_endstops/   tc2_x_endstops.cpp
    ├── tc3_y_axis/       tc3_y_axis.cpp
    └── tc4_pen_lift/     tc4_pen_lift.cpp
```

Flash command pattern:

```bash
cd firmware
pio run -e <env_name> -t upload
pio device monitor
```

---

### TC1 — X-Axis Movement

**Goal:** Verify that the X stepper (carriage) moves and that the direction mapping is correct.

**Flash:**

```bash
pio run -e tc1_x_axis -t upload
```

**What the sketch does:**

| Step | Action | Expected |
|------|--------|----------|
| 1 | Prompts operator to centre the carriage | — |
| 2 | Moves X axis RIGHT (DIR=HIGH), 25 steps (~5 mm) | Carriage moves right |
| 3 | Asks: "Did the carriage move RIGHT?" | Operator confirms |
| 4 | Moves X axis LEFT (DIR=LOW), 800 steps (~10 mm) | Carriage moves left past centre |
| 5 | Asks: "Did the carriage move LEFT?" | Operator confirms |
| 6 | Prints PASS / FAIL | — |

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Wrong motor moves | X/Y motor cables swapped | Swap X and Y connectors on CNC Shield |
| Both directions reversed | DIR sense wrong | Flip the DIR level in the sketch; under GRBL later, set `$3=1` (invert X) |
| Motor buzzes, no movement | Current limit too low or motor coil pairs swapped | Re-adjust A4988 trimmer; check motor wiring order |

---

### TC2 — X-Axis Endstops

The machine has **two optical endstops, both on the X axis** (X_MIN + X_MAX),
and none on Y — see [electronics.md → Machine configuration](electronics.md#machine-configuration-canonical).

> **Wiring note.** In the *production* GRBL wiring both X switches share the
> `X_LIMIT` pin (D9). This standalone sketch instead reads X_MAX on D10 as a
> convenience, so for TC2 wire X_MAX's signal to the **Y-** header
> temporarily, then move both switches onto the **X-** header before flashing
> GRBL. (TODO, see [TODO.md](TODO.md): update the sketch so it exercises both
> switches through D9 and just asks the operator which end was reached.)

**Goal:** Verify both X-axis optical endstops fire at the correct ends and in the correct sense.

**Flash:**

```bash
pio run -e tc2_x_endstops -t upload
```

**What the sketch does:**

| Step | Action | Expected |
|------|--------|----------|
| 1 | Prompts operator to centre the carriage | — |
| 2 | Reads both endstop pins | Both HIGH (open / untriggered) |
| 3 | Drives carriage slowly toward MIN end (DIR=LOW) until X_MIN (D9) goes LOW | Carriage stops at front/left end |
| 4 | Asks: "Did the carriage stop at the X_MIN end?" | Operator confirms |
| 5 | Drives carriage slowly toward MAX end (DIR=HIGH) until X_MAX (D10) goes LOW | Carriage stops at back/right end |
| 6 | Asks: "Did the carriage stop at the X_MAX end?" | Operator confirms |
| 7 | Prints PASS / FAIL | — |

**Endstop logic:** the sketch reads the raw pin (LOW = beam blocked). Under
GRBL this is governed by `$5` — see the TODO in
[electronics.md → Endstops](electronics.md#endstops).

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Endstop already LOW at idle | Optical beam blocked, or wiring short | Check endstop placement and wiring |
| Endstop never fires | No 5 V supply on endstop header, or signal wire missing | Check 3-pin connector (GND/5V/SIG) |
| MIN and MAX swapped | Endstop cables exchanged | Swap X_MIN and X_MAX connectors |
| Carriage reaches mechanical stop without trigger | Endstop not in the optical path | Adjust endstop mounting position |

---

### TC3 — Y-Axis Movement

**Goal:** Verify that the Y stepper (paper feed) moves and that paper is fed in the correct direction.

**Flash:**

```bash
pio run -e tc3_y_axis -t upload
```

**What the sketch does:**

| Step | Action | Expected |
|------|--------|----------|
| 1 | Prompts operator to insert a sheet of paper into the paper bail | — |
| 2 | Drives Y axis IN (DIR=HIGH), 100 steps (~20 mm) | Paper pulled into plotter |
| 3 | Asks: "Was paper pulled IN?" | Operator confirms |
| 4 | Drives Y axis OUT (DIR=LOW), 100 steps (~20 mm) | Paper ejected |
| 5 | Asks: "Was paper pushed OUT?" | Operator confirms |
| 6 | Prints PASS / FAIL | — |

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Carriage moves instead of paper feed | X/Y motor cables swapped | Swap X and Y connectors on CNC Shield |
| Both directions reversed | DIR sense wrong | Flip the DIR level in the sketch; under GRBL later, set `$3=2` (invert Y) |
| Motor turns but paper doesn't move | Feed roller not gripping | Check roller tension spring and bail assembly |

---

### TC4 — Pen Lift (Solenoid)

**Goal:** Verify the solenoid fires on command and the pen returns via spring on release.

**Flash:**

```bash
pio run -e tc4_pen_lift -t upload
```

**What the sketch does:**

| Step | Action | Expected |
|------|--------|----------|
| 1 | Prompts operator to confirm flyback diode and 12 V supply | — |
| 2–5 | Cycles solenoid 4 times: 1 s ON → 3 s OFF (cool-down) | Audible click + visible pen drop each cycle; pen returns up each time |
| 6 | Asks: "Did solenoid actuate on all cycles?" | Operator confirms |
| 7 | Asks: "Did pen return UP after each cycle?" | Operator confirms |
| 8 | Prints PASS / FAIL | — |

> ⚠️ **Safety:** Do not energise the solenoid continuously for more than ~2 s.  
> The 3 s cool-down between cycles is the minimum recommended interval.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No actuation at all | MOSFET gate not reaching D11; no 12 V supply | Check D11 wiring to MOSFET gate; check 12 V rail |
| Weak / incomplete stroke | MOSFET Vgs threshold too high; 12 V insufficient | Use a logic-level MOSFET (IRLZ44N); check PSU voltage under load |
| Pen does not return | Return spring missing or too weak | Check / replace return spring; verify solenoid slider moves freely |
| MOSFET gets very hot | Flyback diode missing | Install 1N4007 across solenoid coil immediately |

---

## Phase 2 — GRBL Integration Tests

Flash GRBL (production firmware) and control the plotter via G-code from a PC.  
The same four functions are tested, this time through the full GRBL stack.

### 2.0 — Flash GRBL and connect

```bash
cd firmware
pio run -e uno -t upload
pio device monitor            # 115200 baud
```

After reset you should see:

```
Grbl 1.1h ['$' for help]
[MSG:Caution: Unlocked]
```

If GRBL shows `ALARM:` on startup, homing is required first (see TC5-G below).

**Recommended G-code sender:** [UGS (Universal G-code Sender)](https://universalgcodesender.com/)  
Connect at **115200 baud**. Use the MDI (Manual Data Input) console to send commands.

---

### TC5-G — Initialisation and Homing

**Goal:** GRBL starts cleanly and the homing cycle completes without errors.

**Procedure:**

```gcode
$H
```

Only the **X axis** homes (`HOMING_CYCLE_0 = X`). Y has no endstop and is not
homed; Z is disabled.

**Expected sequence:**

1. Carriage accelerates toward X_MIN.
2. Slows down and touches X_MIN.
3. Backs off by `$27` (5 mm pull-off).
4. GRBL responds with `ok`; machine position X is set to 0. (Y stays at its
   power-up value — Y is not homed.)

| Response | Meaning |
|----------|---------|
| `ok` | Homing successful |
| `ALARM:8` | Endstop not reached within travel limit — check endstop wiring |
| `ALARM:9` | Endstop still triggered after pull-off — check sensor alignment |

After this, run **TC5b-G** to measure and store the X-axis length.

---

### TC5b-G — Teach the X-axis length

GRBL homes X against X_MIN only. X_MAX shares the same limit pin, so its
position must be measured once and stored in `$130`.

```gcode
$21=1                 ; enable hard limits so X_MAX stops the jog
$H                    ; home to X_MIN → machine X = 0
```

Then jog toward X_MAX in small steps until GRBL raises `ALARM:1`:

```gcode
$J=G91 X20 F500       ; repeat until ALARM:1 (X_MAX reached)
```

```gcode
?                     ; note the last MPos:X before the alarm = usable X length
$X                    ; clear the alarm
$130=<that value minus ~3 mm>   ; store X max travel
$20=1                 ; enable soft limits — moves are now bounded
```

Re-run whenever the belt, pulleys or switch positions change.

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No `ALARM:1` at the far end | X_MAX not wired to `X_LIMIT` (D9), or `$21=0` | Check both X switches share D9; set `$21=1` |
| `ALARM:1` immediately on `$H` | X_MAX (or X_MIN) stuck triggered, or `$5` inverted | Check optical alignment; verify `$5` (see TODO.md) |

---

### TC6-G — Endstop Signals in Idle State

**Goal:** Confirm both X endstops read as open when the carriage is clear, and that each one is seen by GRBL.

Both X switches sit on the `X_LIMIT` pin, so GRBL reports **`Pn:X` for either
one** — it cannot tell them apart. There is no `Pn:Y` (Y has no endstop).

**Step 1 — Status check with carriage in the middle:**

```gcode
$X
?
```

The `Pn:` field must be **absent** (no limit flags):

```
<Idle|MPos:0.000,0.000,0.000|FS:0,0>
```

**Step 2 — Trigger X_MIN by hand:**  
Block the X_MIN optical sensor with a finger, then send `?`.  
Expected: status contains `Pn:X`. Unblock — confirm `Pn:X` disappears.

**Step 3 — Trigger X_MAX by hand:**  
Block the X_MAX optical sensor — confirm `Pn:X` appears again (same flag as
X_MIN), then disappears when released.

| Observation | Meaning |
|-------------|---------|
| `Pn:X` only when expected | Endstop wiring correct |
| `Pn:X` always present | Sensor permanently triggered or signal wire shorted |
| `Pn:X` never appears | No 5 V on header, broken signal wire, or sensor faulty |

---

### TC7-G — X-Axis Movement via GRBL

**Goal:** Verify GRBL moves the X axis the correct distance in each direction.

**Procedure:**

```gcode
$X                  ; clear alarm lock (if present)
G91                 ; relative positioning mode
G1 X5 F500          ; move X +5 mm (carriage should move RIGHT)
```

> Confirm: carriage moved right ~5 mm.

```gcode
G1 X-10 F500        ; move X -10 mm (carriage should move LEFT, past start)
G90                 ; back to absolute positioning
```

> Confirm: carriage moved left ~10 mm.

**Step — Drive to X_MIN with hard limits:**

```gcode
$21=1
G91
G1 X-200 F800
```

> Expected: GRBL stops when X_MIN triggers and raises `ALARM:1`.  
> The carriage must **not** crash into the mechanical stop.

```gcode
$21=0
$X
G90
```

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Wrong motor moves | X/Y motor cables swapped | Swap connectors on CNC Shield |
| Both directions reversed | Direction invert wrong | Send `$3=1` (invert X) |
| Carriage crashes through endstop | Hard limit not wired / `$21` not set | Check endstop wiring; set `$21=1` |

---

### TC8-G — Y-Axis Movement via GRBL

**Goal:** Verify GRBL feeds paper correctly in both directions.

Y has no endstop and is never homed — GRBL treats the current position as
`Y = 0`. Insert a sheet of paper into the paper bail first; that position is
your origin. If soft limits are on (`$20=1`), a `Y-` move past 0 is refused,
so send `G92 Y0` after loading paper if you need headroom for the OUT move.

```gcode
$X                  ; clear alarm
G91                 ; relative mode
G1 Y30 F500         ; feed paper IN 30 mm
```

> Confirm: paper is pulled into the plotter.

```gcode
G1 Y-30 F500        ; feed paper OUT 30 mm
G90
```

> Confirm: paper is ejected.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Carriage moves instead of paper | X/Y motor cables swapped | Swap connectors |
| Both directions reversed | Direction invert wrong | Send `$3=2` (invert Y) |
| Motor turns, paper doesn't move | Roller not gripping | Check roller tension |

---

### TC9-G — Pen Lift via GRBL (1 s down, then up)

**Goal:** Verify GRBL controls the solenoid via M3/M5 spindle commands with correct timing.

> ⚠️ Same solenoid safety rules apply: do not energise continuously for more than ~2 s.

> **TODO** ([TODO.md](TODO.md)): confirm the M3/M5 mapping against the
> assembled hardware and `pipeline/configs/grbl_a4_pen.toml` — this guide
> assumes inverted wiring (`M3 S1000` = energised = pen **UP**, `M5` = pen
> **DOWN** via spring).

```gcode
M5                  ; solenoid OFF → pen DOWN (spring return)
G4 P1               ; dwell 1 second
M3 S1000            ; solenoid ON  → pen UP (lift)
```

> Confirm: solenoid clicks and pen moves DOWN on `M5`, pen returns UP after `G4 P1` + `M3`.

Repeat three more times with cool-down pauses:

```gcode
G4 P3
M5
G4 P1
M3 S1000
G4 P3
M5
G4 P1
M3 S1000
G4 P3
M5
G4 P1
M3 S1000
```

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Solenoid does not fire | Spindle settings wrong | Check `$30=1000` and `$31=0` via `$$` |
| Solenoid fires but pen doesn't move | Mechanical binding | Check solenoid slider moves freely |
| Pen does not return | Return spring missing or weak | Check / replace return spring |
| MOSFET very hot | Flyback diode missing | Install 1N4007 across solenoid coil immediately |

---

## Phase 3 — Pipeline Software Tests

This phase verifies the host-side Python pipeline that converts images to G-code.  
It runs entirely on the host PC — **no plotter connection is required**.

### Phase 3 Prerequisites

- Python **3.13** (not 3.14 — `vpype` requires `<3.14`) and the project
  virtualenv set up — see
  [pipeline/README.md → Installation](pipeline/README.md#installation)
  (`python3.13 -m venv .venv && .venv/bin/pip install -e "pipeline/[gui]"`).

- All hardware tests (Phase 1 + Phase 2) should have passed before an end-to-end plot is attempted, but Phase 3 can be run independently at any time.

The test image used throughout Phase 3 & 4 is `pipeline/input/testimage.png`.

Two configs are used below:
- `pipeline/examples/standard_pipeline.yaml` — offline: image → sketch →
  vectorize → **G-code file** (Phase 3).
- `pipeline/configs/plotter.yaml` — image → vectorize → G-code → **serial
  stream to GRBL** (Phase 4). Set its `port:` for your machine.

---

### TC-P1 — Unit Tests

**Goal:** All pipeline unit tests pass without errors.

**Run:**

```bash
.venv/bin/pytest pipeline/tests/ -v
```

**Expected:** every test in `pipeline/tests/test_*.py` shows `PASSED`; no
`FAILED` or `ERROR` entries. (Don't check against a fixed count — the suite
grows.)

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError` | Virtualenv not activated or incomplete install | `.venv/bin/pip install -e "pipeline/[gui]"` |
| `ImportError: cannot import name ...` | Outdated installed package | `.venv/bin/pip install -e "pipeline/[gui]" --upgrade` |
| Individual test `FAILED` | Step logic regression | Check the failing test and the corresponding step in `pipeline/steps/` |

---

### TC-P2 — Pipeline Config Smoke Tests

**Goal:** The sample pipeline YAML configs execute without Python errors on the test image.

**Run:**

```bash
.venv/bin/python pipeline/tests/run_all_pipeline_configs.py          # all configs
.venv/bin/python pipeline/tests/run_all_pipeline_configs.py --fast   # CPU-only, no downloads
```

**What this does:**

Each `*.yaml` under `pipeline/tests/pipeline_configs/` is loaded via
`PipelineRunner.from_yaml` and executed against `pipeline/input/testimage.png`.
Every step must complete without raising. Configs whose optional dependency is
missing (e.g. `diffusers`) are reported as *skipped*, not failed.

**Expected:** every config reports `OK` (or `~` skipped), none `X`:

```text
  [stylize_adaptive    ]  ... OK   ...
  [stylize_canny       ]  ... OK   ...
  [stylize_controlnet  ]  ... ~    skipped (missing dependency: ...)
  ...
  Results: N ok  M skipped  0 errors
```

> ⚠️ Without `--fast`, the NN configs (`stylize_hed`, `stylize_dexined`,
> `stylize_lineart`, `stylize_informative`) download model weights on first
> run (~0.1–0.4 GB each); the diffusion configs (`stylize_controlnet`,
> `stylize_img2img`) need the `[diffusers]` extra and are skipped without it.
> Use `--fast` for a quick check that needs no network.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Step not found in registry` | Step name typo or missing registry entry | Check `pipeline/core/registry.py` |
| `FileNotFoundError: testimage.png` | Test image missing | Confirm `pipeline/input/testimage.png` exists |
| NN model download fails | No internet / HuggingFace token required | Run `.venv/bin/get-hf-token` |

---

### TC-P3 — End-to-End G-code Generation

**Goal:** The full offline pipeline (sketch → vectorize → G-code) produces a valid `.gcode` file for a real input image.

**Run:**

```bash
.venv/bin/pipeline-run \
    --config pipeline/examples/standard_pipeline.yaml \
    --input  pipeline/input/testimage.png \
    --output /tmp/test_output.gcode \
    --verbose
```

**Expected:**

1. Pipeline runs without errors; the log ends with `Pipeline completed.`
2. `/tmp/test_output.gcode` is created and non-empty.
3. It is valid G-code: starts with `G21` / `G90`, contains `G1` moves and `M3`/`M5` pen commands, and ends on `M5`.

**Quick validation:**

```bash
head -6 /tmp/test_output.gcode          # G21, G90, G1 F3000, M3 S1000, ...
grep -c "^G1 " /tmp/test_output.gcode   # should be > 0
tail -3 /tmp/test_output.gcode          # should contain a final M5
```

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Pipeline aborts with a traceback | A step raised an exception | Re-run with `--verbose` and read the failing step |
| Output file empty / only header+footer | Vectorization produced 0 paths | Lower `min_path_px` / `simplify_eps`, or raise `style_res`, or lower `threshold` in the `stylise_xdog` step |
| `ModuleNotFoundError` | Incomplete install | `.venv/bin/pip install -e "pipeline/[gui]"` |

---

## Phase 4 — Full System End-to-End Plot

This phase tests the complete system: host PC pipeline → USB serial → GRBL plotter.  
A real image is processed by the pipeline and the resulting G-code is streamed live to the connected plotter.

**Prerequisites — all of the following must be true before starting Phase 4:**

- [ ] Phase 1 passed (all hardware components verified)
- [ ] Phase 2 passed (GRBL firmware running, homing and axes verified)
- [ ] Phase 3 passed (pipeline software verified on test image)
- [ ] Plotter connected via USB and recognised by the OS
- [ ] Paper loaded into the paper bail
- [ ] Pen inserted into the carriage

### Phase 4 Prerequisites

**Find your serial port:**

```bash
# macOS
ls /dev/tty.usbmodem*

# Linux
ls /dev/ttyUSB* /dev/ttyACM*

# Windows
# Check Device Manager → Ports (COM & LPT)
```

Then set that port in `pipeline/configs/plotter.yaml` (the `send_gcode`
step's `port:` field). All Phase 4 tests use that config.

---

### TC-E1 — Dry-Run: Pipeline to Serial (no motion)

**Goal:** Verify the pipeline generates G-code and the serial connection to GRBL is established — without any physical motion.

**Step 1 — Put `plotter.yaml` in dry-run mode:**

In `pipeline/configs/plotter.yaml`, set the `send_gcode` step's
`dry_run: true`.

**Step 2 — Run:**

```bash
.venv/bin/pipeline-run \
    --config pipeline/configs/plotter.yaml \
    --input  pipeline/input/testimage.png \
    --verbose
```

**Expected:**

- Pipeline runs through all steps without error.
- Log shows the serial port opened successfully.
- Log shows G-code lines read/validated but **not** sent (`dry_run=true`).
- Plotter does **not** move.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `SerialException: could not open port` | Wrong port or driver missing | Check `ls /dev/tty.usbmodem*`; try replug USB |
| `ALARM:` in log | GRBL not homed | Connect with UGS and run `$H` first |
| Pipeline fails before `send_gcode` | Earlier step error | Fix TC-P2/TC-P3 failures first |

---

### TC-E2 — Live Plot: Simple Test Image

**Goal:** The plotter draws the full test image (`testimage.png`) without errors or mechanical faults.

**Step 1 — Switch `plotter.yaml` back to live mode:** set `dry_run: false`.

**Step 2 — Home the plotter first:**

Connect with UGS (or any G-code sender), send `$H`, and run **TC5b-G** if you
have not stored `$130` yet. Confirm homing completes without `ALARM:`. Then
close the G-code sender (only one process may hold the serial port).

**Step 3 — Run:**

```bash
.venv/bin/pipeline-run \
    --config pipeline/configs/plotter.yaml \
    --input  pipeline/input/testimage.png \
    --verbose
```

**Observe during the plot:**

| Checkpoint | Expected |
|-----------|----------|
| Start | `M3 S1000` — solenoid energizes, pen lifts, carriage moves to the origin |
| First draw move | `M5` — pen lowers (de-energized), carriage starts drawing |
| Travel moves | Pen raises (`M3`) between strokes, no dragging marks on paper |
| Paper feed | Y-axis advances paper smoothly |
| Plot completion | Final `M5` (pen down / solenoid off), paper advances to the sheet end; console prints `✓ Pipeline OK` (exit 0) |

**Expected result:** A recognisable line drawing of the test image on the
paper, with no skipped lines, no crash alarms, and no solenoid misfires.

If GRBL reports an `error:`/`ALARM:` mid-stream, the device disconnects, or
GRBL is not back in `Idle` at the end, the run **fails** — `✗ Pipeline
FAILED: send_gcode failed: …` and a non-zero exit code (the GUI marks the
job `error`).

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ALARM:1` during plot | X hard limit — drawing wider than the taught `$130` | Re-run TC5b-G; reduce `target_width_mm` in `plotter.yaml` |
| `ALARM:2` | Soft limit — move outside `$130`/`$131` | Same as above; check the drawing fits A4 |
| Pen drags during travel | Pen lift not working | Re-run TC4/TC9-G; check the D11 wiring and `$30=1000` |
| Pen too faint / not touching | Solenoid stuck energized, or spring too strong | Check `M5` de-energizes; check the return spring |
| Solenoid hot after the plot | Long travels keep it energized | Confirm the file ends on `M5`; consider the holding-current change (see electronics.md) |
| Paper slips or jams | Roller tension too low | Adjust paper bail spring; check paper is straight |
| Serial timeout | GRBL not responding within `completion_timeout` | Raise `completion_timeout`; check USB cable / baud |

---

### TC-E3 — Live Plot: Custom Image

**Goal:** Confirm the full workflow with a user-supplied photograph produces a clean plot on paper.

**Step 1 — Prepare a test photograph:**

Use any clear subject photograph (portrait, object, landscape). A high-contrast image with distinct edges works best.

**Step 2 — Preview the G-code first** (recommended):

```bash
.venv/bin/pipeline-run \
    --config pipeline/examples/standard_pipeline.yaml \
    --input  /path/to/your/photo.jpg \
    --output /tmp/tc_e3_custom.gcode
grep -c "^M3 " /tmp/tc_e3_custom.gcode   # pen-up events (≈ travel moves)
```

A reasonable plot has 50–2000 pen-up events. If it is very high (> 5000),
raise `min_path_px` / `simplify_eps` in `standard_pipeline.yaml` — long plots
also mean more solenoid-energized time.

**Step 3 — Home ($H, run TC5b-G if needed), close UGS, then plot:**

```bash
.venv/bin/pipeline-run \
    --config pipeline/configs/plotter.yaml \
    --input  /path/to/your/photo.jpg \
    --verbose
```

**Expected result:** Recognisable pen drawing of the photograph, clean lines, no mechanical errors.

**Tuning hints:**

| Issue | Config key to adjust | Direction |
|-------|---------------------|-----------|
| Too many fine lines / long plot time | `min_path_px` (vectorise) | Increase (e.g. 15–30) |
| Lines too jagged | `simplify_eps` (vectorise) | Increase (e.g. 2.0–3.0) |
| Drawing too small on paper | `target_width_mm` / `target_height_mm` (gcode_from_svg) | Increase toward A4 limits |
| Drawing clipped / off the paper | `offset_x` / `offset_y` in `grbl_a4_pen.toml` | Increase the margins |
| Pen marks too faint | drawing feedrate in `grbl_a4_pen.toml` `segment_first` (`G1 F1500`) | Decrease (slower = more ink) |

---

## Test result log

Use this table to record results during commissioning:

| ID | Test | Phase 1 result | Phase 2 result | Notes |
|----|------|:--------------:|:--------------:|-------|
| TC1 / TC7-G | X-Axis Movement | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC2 / TC6-G | X-Axis Endstops | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC3 / TC8-G | Y-Axis Movement | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC4 / TC9-G | Pen Lift | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| — / TC5-G | Initialisation & Homing | — | ☐ PASS / ☐ FAIL | |

| ID | Test | Result | Notes |
|----|------|:------:|-------|
| TC-P1 | Unit Tests (`pytest pipeline/tests/`) | ☐ PASS / ☐ FAIL | |
| TC-P2 | Pipeline Config Smoke Tests | ☐ PASS / ☐ FAIL | |
| TC-P3 | End-to-End G-code Generation | ☐ PASS / ☐ FAIL | |

| ID | Test | Result | Notes |
|----|------|:------:|-------|
| TC-E1 | Dry-Run: Pipeline to Serial | ☐ PASS / ☐ FAIL | |
| TC-E2 | Live Plot: Test Image | ☐ PASS / ☐ FAIL | |
| TC-E3 | Live Plot: Custom Image | ☐ PASS / ☐ FAIL | |
