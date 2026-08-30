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

6. Python 3.13 and the project virtualenv installed — see
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
| Both directions reversed | Direction invert wrong | Toggle bit 0 of `DEFAULT_DIRECTION_INVERT_MASK` in `config.h` |
| Motor buzzes, no movement | Current limit too low or motor coil pairs swapped | Re-adjust A4988 trimmer; check motor wiring order |

---

### TC2 — X-Axis Endstops

> **TODO** ([TODO.md](TODO.md)): this test assumes **two endstops on the X axis**
> (`D9 = X_MIN`, `D10 = X_MAX`). `firmware/src/config.h`, `BOM.md` and
> `electronics.md` §Endstops instead describe **one endstop per axis**
> (`D9 = X_MIN`, `D10 = Y_MIN`, both axes home). Resolve the real wiring before
> trusting this step.

**Goal:** Verify both X-axis optical endstops are wired to the correct pins and fire at the correct ends.

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

**Endstop logic:** Optical endstops are HIGH when beam is open, LOW when triggered.  
This matches `DEFAULT_INVERT_LIMIT_PINS 1` in `config.h`.

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
| Both directions reversed | Direction invert wrong | Toggle bit 1 of `DEFAULT_DIRECTION_INVERT_MASK` in `config.h` |
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

**Expected sequence:**

1. Carriage accelerates toward X_MIN.
2. Slows down and touches X_MIN.
3. Backs off by `$27` (5 mm pull-off).
4. GRBL responds with `ok`; machine position is set to X=0, Y=0.

| Response | Meaning |
|----------|---------|
| `ok` | Homing successful |
| `ALARM:8` | Endstop not reached within travel limit — check endstop wiring |
| `ALARM:9` | Endstop still triggered after pull-off — check sensor alignment |

---

### TC6-G — Endstop Signals in Idle State

**Goal:** Confirm both endstops read as open when the carriage is clear of all switches, and that each can be detected individually.

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
Block the X_MAX optical sensor — confirm `Pn:X` appears, then disappears when released.

> **TODO** ([TODO.md](TODO.md)): depends on the unresolved endstop-wiring
> question (see TC2). If `D10` is the Y limit pin, blocking that sensor shows
> `Pn:Y`, not `Pn:X`, and this step needs rewriting.

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

Insert a sheet of paper into the paper bail first.

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

- Python 3.13 and the project virtualenv set up — see
  [pipeline/README.md → Installation](pipeline/README.md#installation).

  > **TODO** ([TODO.md](TODO.md)): older revisions of this guide referenced
  > `./pipeline/scripts/setup_pipeline.sh`, which no longer exists.

- All hardware tests (Phase 1 + Phase 2) should have passed before an end-to-end plot is attempted, but Phase 3 can be run independently at any time.

> **TODO** ([TODO.md](TODO.md)) — applies to all of Phase 3 & 4:
> - The test image is `pipeline/input/testimage.png` (not `pipeline/tests/testimage.png`).
> - Failure hints below still mention `requirements.txt` / `setup_pipeline.sh`, which no longer exist — use `pip install -e "pipeline/[gui]"` instead.
> - `pipeline/configs/standard_pipeline.yaml`, used as the example config, is itself stale (wrong name/description, legacy `gcode_gen` step). Once a clean plotter pipeline config exists, switch the examples to it.

---

### TC-P1 — Unit Tests

**Goal:** All pipeline unit tests pass without errors.

**Run:**

```bash
.venv/bin/pytest pipeline/tests/ -v
```

> **TODO** ([TODO.md](TODO.md)): the fixed count "62" quoted in older
> revisions is stale (the suite has ~109 test functions). Treat "all green"
> as the pass criterion.

**Expected:** every test in `pipeline/tests/test_*.py` shows `PASSED`; no
`FAILED` or `ERROR` entries.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError` | Virtualenv not activated or incomplete install | Re-run `./pipeline/scripts/setup_pipeline.sh` |
| `ImportError: cannot import name ...` | Outdated installed package | `pip install -r pipeline/requirements.txt --upgrade` |
| Individual test `FAILED` | Step logic regression | Check the failing test and the corresponding step in `pipeline/steps/` |

---

### TC-P2 — Pipeline Config Smoke Tests

**Goal:** All pipeline YAML configurations in `pipeline/configs/` execute without Python errors on the test image.

**Run:**

```bash
.venv/bin/python pipeline/tests/run_all_pipeline_configs.py
```

**What this does:**

Each YAML file under `pipeline/configs/` (excluding the TOML profile) is loaded and executed against `pipeline/tests/testimage.png`. The runner checks that every step completes without raising an exception.

**Expected:** All configs report `OK`. Example output:

```text
[OK] standard_pipeline.yaml
[OK] stylize_canny.yaml
[OK] stylize_xdog.yaml
...
```

> ⚠️ Configs that use neural-network stylizers (`stylize_controlnet.yaml`, `stylize_img2img.yaml`, etc.) will download model weights on the first run (~2–4 GB). Subsequent runs use the cached models.  
> Skip NN-heavy configs during initial testing with `--skip-stylizers` if needed.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Step not found in registry` | Step name typo or missing registry entry | Check `pipeline/core/registry.py` |
| `FileNotFoundError: testimage.png` | Test image missing | Confirm `pipeline/tests/testimage.png` exists |
| NN model download fails | No internet / HuggingFace token required | Run `./pipeline/core/setup_hf_token.py` or use `--skip-stylizers` |

---

### TC-P3 — End-to-End G-code Generation

**Goal:** The full pipeline (stylization → vectorization → G-code generation) produces a valid `.gcode` file for a real input image.

**Run:**

```bash
.venv/bin/python pipeline/core/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input pipeline/tests/testimage.png \
    --output /tmp/test_output.gcode \
    --verbose
```

**Expected:**

1. Pipeline runs without errors.
2. Output file `/tmp/test_output.gcode` is created and non-empty.
3. File contains valid G-code: starts with `G21` (millimeter mode) and includes `G00`/`G01` move commands.

**Quick validation:**

```bash
head -5 /tmp/test_output.gcode   # should show G21, G90, etc.
grep -c "G0" /tmp/test_output.gcode  # should be > 0
```

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `=== Complete ===` not reached | A step raised an exception | Run with `--verbose` and check the log |
| Output file empty or missing | GCode generation step not in config | Confirm `gcode_gen` step is present and enabled in the YAML |
| G-code contains only preamble, no moves | Vectorization produced 0 paths | Increase `style_res` or decrease `min_path_px` in config |

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

Note the port (e.g. `/dev/tty.usbmodem1101`) — you will need it in the YAML config below.

---

### TC-E1 — Dry-Run: Pipeline to Serial (no motion)

**Goal:** Verify the pipeline generates G-code and the serial connection to GRBL is established — without any physical motion.

**Step 1 — Enable `send_gcode` in dry-run mode:**

Edit `pipeline/configs/standard_pipeline.yaml`, set the `send_gcode` step:

```yaml
- step: send_gcode
  enabled: true
  config:
    port: /dev/tty.usbmodem1101   # ← your port here
    baud: 115200
    dry_run: true                  # true = connect and read, but do NOT send
    response_timeout_s: 30.0
```

**Step 2 — Run:**

```bash
.venv/bin/python pipeline/core/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input pipeline/tests/testimage.png \
    --output /tmp/tc_e1_dryrun.gcode \
    --verbose
```

**Expected:**

- Pipeline runs through all steps without error.
- Log shows serial port opened successfully.
- Log shows G-code lines read/validated but **not** sent (`dry_run=true`).
- Output file `/tmp/tc_e1_dryrun.gcode` is created and non-empty.
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

**Step 1 — Switch `send_gcode` to live mode:**

```yaml
- step: send_gcode
  enabled: true
  config:
    port: /dev/tty.usbmodem1101   # ← your port here
    baud: 115200
    dry_run: false                 # ← live send
    response_timeout_s: 30.0
```

**Step 2 — Home the plotter first:**

Connect with UGS (or any G-code sender) and send:

```gcode
$H
```

Confirm homing completes without `ALARM:`. Then close the G-code sender (only one process may hold the serial port at a time).

**Step 3 — Run:**

```bash
.venv/bin/python pipeline/core/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input pipeline/tests/testimage.png \
    --output /tmp/tc_e2_live.gcode \
    --verbose
```

**Observe during the plot:**

| Checkpoint | Expected |
|-----------|----------|
| Pen lift at start | Solenoid clicks, pen moves UP before first travel move |
| First draw move | Pen lowers, carriage starts drawing |
| Travel moves | Pen raises between strokes, no dragging marks on paper |
| Paper feed | Y-axis advances paper smoothly at each new line |
| Plot completion | Log shows `=== Complete ===`; plotter returns to origin |

**Expected result:** A recognisable line drawing of the test image on the paper, with no skipped lines, no crash alarms, and no solenoid misfires.

**Failure hints:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ALARM:1` during plot | Hard limit triggered — carriage overran endstop | Check `$130`/`$131` max travel; re-home with `$H` |
| `ALARM:3` / `ALARM:4` | Feed hold triggered | Check for mechanical obstruction; inspect belt tension |
| Pen drags during travel | Pen lift not working | Re-run TC4/TC9-G; check solenoid power and `$30`/`$31` |
| Paper slips or jams | Roller tension too low | Adjust paper bail spring; check paper is straight |
| Plot starts at wrong position | Homing not done before run | Always run `$H` before a plot |
| Serial timeout | GRBL not responding within `response_timeout_s` | Increase timeout; check USB cable; check baud rate |

---

### TC-E3 — Live Plot: Custom Image

**Goal:** Confirm the full workflow with a user-supplied photograph produces a clean plot on paper.

**Step 1 — Prepare a test photograph:**

Use any clear subject photograph (portrait, object, landscape). A high-contrast image with distinct edges works best.

**Step 2 — Run:**

```bash
.venv/bin/python pipeline/core/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input /path/to/your/photo.jpg \
    --output /tmp/tc_e3_custom.gcode \
    --verbose
```

**Step 3 — Verify the G-code before sending** (optional but recommended for large files):

```bash
wc -l /tmp/tc_e3_custom.gcode          # line count
grep -c "M3\|M5" /tmp/tc_e3_custom.gcode  # number of pen lift/lower events
```

A reasonable plot has 50–2000 pen events. If the count is very high (> 5000), consider increasing `min_path_px` or `simplify_eps` in the config.

**Step 4 — Home and run** (same as TC-E2):

```bash
# Home first via UGS:  $H
# Then close UGS and run:
.venv/bin/python pipeline/core/main.py \
    --config pipeline/configs/standard_pipeline.yaml \
    --input /path/to/your/photo.jpg \
    --output /tmp/tc_e3_custom.gcode \
    --verbose
```

**Expected result:** Recognisable pen drawing of the photograph, clean lines, no mechanical errors.

**Tuning hints:**

| Issue | Config key to adjust | Direction |
|-------|---------------------|-----------|
| Too many fine lines / long plot time | `min_path_px` | Increase (e.g. 15–30) |
| Lines too jagged | `simplify_eps` | Increase (e.g. 2.0–3.0) |
| Drawing too small on paper | `target_width_mm` / `target_height_mm` | Increase toward A4 limits |
| Drawing clipped or outside paper | `origin_x` / `origin_y` | Increase margins |
| Pen marks too faint | `feedrate_draw` | Decrease (slower = more ink) |

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
