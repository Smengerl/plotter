````markdown
# GRBL Firmware

This document describes the GRBL setup for the G-code Pen Plotter.  
GRBL v1.1 runs on the Arduino Uno via the Arduino CNC Shield v3.  
All firmware sources live in the `firmware/` directory. GRBL itself is included as a Git submodule under `grbl/`.

## Table of contents
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [First-time setup](#first-time-setup)
- [Build and flash](#build-and-flash)
- [Serial monitor / GRBL console](#serial-monitor--grbl-console)
- [Key GRBL settings](#key-grbl-settings-first-run-checklist)
- [GRBL integration tests](#grbl-integration-tests)
- [Converting SVG to G-code](#converting-svgvector-graphics-to-g-code)
- [Sending G-code to the plotter](#sending-g-code-to-the-plotter)


## Repository layout

```
firmware/
├── platformio.ini        ← PlatformIO project (build & flash config)
└── src/
    ├── config.h          ← Plotter-specific GRBL settings (overrides grbl/grbl/config.h)
    ├── main.cpp          ← Arduino-framework entry point (calls grbl_main)
    └── grbl_main_shim.c  ← Bridges GRBL's main() to grbl_main() to avoid linker conflict
firmware/grbl/            ← Git submodule: gnea/grbl (do not edit)
```


## Prerequisites

| Tool | Purpose |
|------|---------|
| [PlatformIO CLI](https://platformio.org/install/cli) or [PlatformIO IDE (VS Code extension)](https://platformio.org/install/ide?install=vscode) | Build and flash |
| USB cable (USB-A ↔ USB-B) | Connect Arduino Uno to PC |

No additional toolchain setup is needed — PlatformIO downloads the AVR toolchain automatically on first build.


## First-time setup

```bash
# 1. Clone the repository with the GRBL submodule
git clone --recurse-submodules https://github.com/Smengerl/plotter.git
cd plotter

# If you already cloned without --recurse-submodules:
git submodule update --init --recursive
```


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

#### Pen lift G-code

The solenoid is controlled via the GRBL spindle output (see [electronics.md](../electronics.md) for wiring details).

Note: this repository's G-code profile (`pipeline/configs/grbl_a4_pen.toml`) is configured for an "inverted" solenoid mounting where the solenoid being ENERGIZED = pen UP (lift). That means:

- `M3 S1000` → energize solenoid → pen UP (repo default)
- `M5`        → de-energize solenoid → pen DOWN (spring return)

If your hardware is wired the other way (energized = pen DOWN), swap the M3/M5 commands in the G-code profile or rewire the solenoid/MOSFET accordingly.


## GRBL integration tests

After flashing GRBL, run the following tests **in order** to verify the complete system via G-code before the first real plot.  
Each test is sent via the MDI console of a G-code sender (e.g. [UGS](https://universalgcodesender.com/)) at **115200 baud**.

Phase 1 — Standalone Arduino tests (TC1–TC4)

Before running the GRBL integration tests you should run the Phase 1 standalone Arduino sketches. The sketch filenames and PlatformIO env names correspond directly to the TC numbers below (the numbering in the source tree matches the TC number shown here):

```
firmware/test/
├── tc1_x_axis/       tc1_x_axis.cpp      # TC1 — X-Axis Movement
├── tc2_x_endstops/   tc2_x_endstops.cpp  # TC2 — X-Axis Endstops
├── tc3_y_axis/       tc3_y_axis.cpp      # TC3 — Y-Axis Movement
└── tc4_pen_lift/     tc4_pen_lift.cpp    # TC4 — Pen Lift (Solenoid)
```

Flash / run each test with PlatformIO (open serial monitor at 115200 baud after upload):

```bash
cd firmware
pio run -e tc1_x_axis     -t upload   # flash TC1
pio run -e tc2_x_endstops -t upload   # flash TC2
pio run -e tc3_y_axis     -t upload   # flash TC3
pio run -e tc4_pen_lift   -t upload   # flash TC4
pio device monitor
```

**Prerequisite:** all Phase 1 standalone tests (TC1–TC4) must have passed first.  
See [testing.md](../testing.md) for the full test documentation.


Additionally, a host-side helper to write recommended GRBL `$` settings is provided as a commissioning testcase (TC5) and is intended to be run on the commissioning PC after the Phase 1 standalone sketches and before the Phase 2 G-code integration tests.

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

### TC7-G — X-axis movement

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
M3 S1000
G4 P1
M5
```

**Expected:**
1. `M3 S1000` — solenoid fires immediately, pen moves **up** (lift).
2. `G4 P1` — 1-second dwell; pen stays up.
3. `M5` — solenoid de-energises, pen returns **down** via spring.

> If the solenoid does not fire: run `$$` and verify `$30=1000` (max spindle speed) and `$31=0` (min spindle speed).

---

See [testing.md](../testing.md) for the complete Phase 2 procedure including failure hints and a result log table.


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

````
