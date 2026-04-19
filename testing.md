# Hardware Test Guide

This document describes the step-by-step test procedure to verify the correct function of the plotter hardware.

Tests are split into two phases:

| Phase | Firmware | TCs | Purpose |
|-------|----------|-----|---------|
| [Phase 1](#phase-1--standalone-arduino-tests-no-grbl) | Standalone sketch per test | TC1–TC4 | Test individual components directly, no GRBL involved |
| [Phase 2](#phase-2--grbl-integration-tests) | GRBL (production firmware) | TC5-G–TC9-G | Verify the full system through GRBL and G-code |

Run Phase 1 first — it is faster to flash and easier to debug individual signals.  
Only proceed to Phase 2 once all Phase 1 tests pass.

---

## Prerequisites

- Arduino Uno + CNC Shield v3 fully wired (see [electronics.md](electronics.md))
- 12 V power supply connected to the CNC Shield
- USB cable connected to the Arduino
- PlatformIO installed (`pio` CLI or VS Code extension)
- Serial monitor ready (PlatformIO: `pio device monitor`, or any 115200-baud terminal)

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

## Test result log

Use this table to record results during commissioning:

| ID | Test | Phase 1 result | Phase 2 result | Notes |
|----|------|:--------------:|:--------------:|-------|
| TC1 / TC7-G | X-Axis Movement | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC2 / TC6-G | X-Axis Endstops | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC3 / TC8-G | Y-Axis Movement | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| TC4 / TC9-G | Pen Lift | ☐ PASS / ☐ FAIL | ☐ PASS / ☐ FAIL | |
| — / TC5-G | Initialisation & Homing | — | ☐ PASS / ☐ FAIL | |
