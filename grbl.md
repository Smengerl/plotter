
# GRBL firmware moved

The detailed GRBL firmware documentation has been moved to the `firmware` folder.
Please consult `firmware/README.md` for build, flash and configuration instructions.

Path: `firmware/README.md`

## Build and flash

```bash
cd firmware

# Build only (no board required)
pio run

# Build AND flash (board must be connected via USB)
pio run -t upload

# Override the serial port if auto-detection fails:
pio run -t upload --upload-port /dev/tty.usbmodem*   # macOS
pio run -t upload --upload-port /dev/ttyUSB0          # Linux
pio run -t upload --upload-port COM3                   # Windows
```

## Serial monitor / GRBL console

```bash
cd firmware
pio device monitor   # 115200 baud, 8N1
```

After reset you should see the GRBL welcome banner:

```
Grbl 1.1h ['$' for help]
```

Type `$` to list all available commands, or `$$` to print current parameter values.

## Key GRBL settings (first-run checklist)

After flashing, connect to the serial monitor and verify/set the following parameters.  
All values are stored persistently in EEPROM.

```gcode
$100=5       ; X steps/mm
$101=5       ; Y steps/mm
$110=3000    ; X max rate (mm/min)
$111=3000    ; Y max rate (mm/min)
$120=200     ; X acceleration (mm/s²)
$121=200     ; Y acceleration (mm/s²)
$130=220     ; X max travel (mm) — A4 width + margin
$131=300     ; Y max travel (mm) — A4 height + margin
$20=0        ; Soft limits OFF (enable to 1 after homing is verified)
$21=0        ; Hard limits OFF (enable to 1 after wiring is verified)
$22=1        ; Homing cycle ON
$23=0        ; Homing direction: toward MIN switches
$24=50       ; Homing feed rate (mm/min)
$25=800      ; Homing seek rate (mm/min)
$27=5        ; Homing pull-off (mm)
```

Perform a homing cycle with `$H` after the settings are saved.

### Steps/mm calculation

```
steps/mm = (200 steps/rev × 1 full step) / (20 teeth × 2 mm/tooth) = 5
```

No MS jumpers are installed on the CNC Shield — the A4988 operates in full-step mode.  
Adjust `$100` / `$101` if you change the pulley tooth count or enable microstepping.

### Pen lift G-code

The solenoid is controlled via the GRBL spindle output (see [electronics.md](electronics.md) for wiring details):

- `M3 S1000` — Solenoid ON → pen UP (lift)
- `M5`       — Solenoid OFF → pen DOWN (spring return)

## GRBL integration tests

After flashing GRBL, run the following tests **in order** to verify the complete system via G-code before the first real plot.  
Each test is sent via the MDI console of a G-code sender (e.g. [UGS](https://universalgcodesender.com/)) at **115200 baud**.

> **Prerequisite:** all Phase 1 standalone tests (TC1–TC4) must have passed first.  
> See [testing.md](testing.md) for the full test documentation.

---

### TC5-G — Initialisation and homing

**Goal:** GRBL starts cleanly and the homing cycle completes without errors.

```gcode
$H
```

**Expected:**

1. Carriage accelerates toward the X_MIN endstop.
2. Touches X_MIN, backs off by 5 mm (pull-off `$27`).
3. GRBL responds with `ok` and sets machine position X=0, Y=0.

| Response | Meaning |
|----------|---------|
| `ok` | Homing successful |
| `ALARM:8` | Homing failed — endstop not reached within travel limit; check endstop wiring |
| `ALARM:9` | Homing failed — endstop stuck triggered after pull-off; check sensor alignment |

---

### TC6-G — Endstop signals in idle state

**Goal:** Confirm both endstops read as open (not triggered) when the carriage is clear of all switches, and that each one is detectable individually.

**Step 1 — Status report with carriage in the middle:**

```gcode
$X
?
```

The `Pn:` field must be **absent** (or show no flags):

```
<Idle|MPos:0.000,0.000,0.000|FS:0,0>
```

**Step 2 — Trigger X_MIN by hand:**  
Block the X_MIN optical sensor with a finger, then send:

```gcode
?
```

Expected: status line contains `Pn:X`.  Unblock the sensor and confirm `Pn:X` disappears.

**Step 3 — Trigger X_MAX by hand:**  
Block the X_MAX optical sensor and confirm `Pn:X` appears again, then disappears when released.

| Observation | Meaning |
|-------------|---------|
| `Pn:X` appears only when expected | Endstop wiring correct |
| `Pn:X` always present | Sensor continuously triggered or signal wire shorted to GND |
| `Pn:X` never appears | No 5 V on endstop header, broken signal wire, or sensor faulty |

---

### TC7-G — X-axis movement to endstop

**Goal:** GRBL drives the carriage in both directions and stops correctly at the X_MIN endstop.

**Step 1 — Move away from home:**

```gcode
$X
G91
G1 X50 F800
G90
```

> Confirm: carriage moved ~50 mm away from X_MIN.

**Step 2 — Drive toward X_MIN with hard limits enabled:**

```gcode
$21=1
G91
G1 X-200 F800
```

> Expected: GRBL stops as soon as X_MIN triggers and raises `ALARM:1` (hard limit).  
> The carriage must **not** crash into the mechanical stop.

```gcode
$21=0
$X
G90
```

> Re-disable hard limits and clear the alarm for the next test.

---

### TC8-G — Y-axis movement

**Goal:** Verify GRBL feeds paper in both directions at a controlled speed.

Insert a sheet of paper into the paper bail before running this test.

```gcode
$X
G91
G1 Y30 F500
```

> Confirm: paper is pulled **into** the plotter ~30 mm.

```gcode
G1 Y-30 F500
G90
```

> Confirm: paper is ejected ~30 mm.

**If direction is wrong:** send `$3=2` (invert Y) or `$3=3` (invert X and Y), then retry.

---

### TC9-G — Pen lift: 1 s down, then up

**Goal:** GRBL lowers and raises the pen on command with correct timing.

> ⚠️ Do not energise the solenoid for more than ~2 s continuously.

```gcode
M5
G4 P1
M3 S1000
```

**Expected:**

1. `M5` — solenoid de-energised, pen moves **down** (spring return retracted).
2. `G4 P1` — 1-second dwell.
3. `M3 S1000` — solenoid energised, pen moves **up** (lift).

> If the solenoid does not fire: run `$$` and verify `$30=1000` (max spindle speed) and `$31=0` (min spindle speed).

---

See [testing.md](testing.md) for the complete Phase 2 procedure including failure hints and a result log table.

### Helper: TC5 — Apply recommended EEPROM settings (host tool)

To make first-time setup easier, this repository now includes a commissioning
test (TC5) that runs on the commissioning PC and applies recommended GRBL
`$` settings. The test program and defaults live under:

```
firmware/test/tc5_set_grbl_eeprom/
    ├── tc5_set_grbl_eeprom.cpp        # Host-side tool (build with g++)
    └── grbl_eeprom_defaults.txt      # Planned $ settings (editable)
```

Build and run instructions are in `firmware/test/tc5_set_grbl_eeprom/README.md`.
Use this host tool instead of the previous Python helper when commissioning.

## Converting SVG/vector graphics to G-code

Recommended tools:

- **[Inkscape](https://inkscape.org/)** with the [InkscapeGcodeTools](https://github.com/cnc-club/gcodetools) extension
- **[vpype](https://github.com/abey79/vpype)** + **[vpype-gcode](https://github.com/plottertools/vpype-gcode)** plug-in
- **[svg2gcode](https://github.com/sameer/svg2gcode)** — simple CLI converter

Pen-up/pen-down: configure the tool to emit `M3 S1000` (pen UP) and `M5` (pen DOWN) at path boundaries, or insert them manually.

## Sending G-code to the plotter

- **[UGS (Universal G-code Sender)](https://universalgcodesender.com/)** — GUI, works on all platforms
- **[bCNC](https://github.com/vlachoudis/bCNC)** — Python-based, feature-rich
- **[CNCjs](https://cnc.js.org/)** — browser-based, runs as a Node.js server
