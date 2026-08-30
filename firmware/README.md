# GRBL Firmware

> ⚠️ **Work in progress** — see [../TODO.md](../TODO.md) for known open issues
> (endstop wiring, GRBL banner text).

This document describes the GRBL setup for the G-code Pen Plotter.  
GRBL v1.1 runs on the Arduino Uno via the Arduino CNC Shield v3.  
All firmware sources live in the `firmware/` directory. GRBL itself is included as a Git submodule under `grbl/`.

This file is **firmware reference only** (layout, build, flash, GRBL
parameters). The hardware and firmware **test procedure** lives in
[../testing.md](../testing.md).

## Table of contents
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [First-time setup](#first-time-setup)
- [Build and flash](#build-and-flash)
- [Serial monitor / GRBL console](#serial-monitor--grbl-console)
- [Key GRBL settings](#key-grbl-settings-first-run-checklist)
- [Hardware & firmware tests](#hardware--firmware-tests) — pointer to `testing.md`


## Repository layout

```
firmware/
├── platformio.ini        ← PlatformIO project (build & flash config)
└── src/
    ├── config.h          ← Plotter-specific GRBL settings (overrides grbl/grbl/config.h)
    ├── main.cpp          ← Arduino-framework entry point (calls grbl_main)
    └── grbl_main_shim.c  ← Bridges GRBL's main() to grbl_main() to avoid linker conflict
└── grbl/                 ← Git submodule: gnea/grbl (do not edit)
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

### Pen lift G-code

The solenoid is controlled via the GRBL spindle output (see [electronics.md](../electronics.md) for wiring details).

Note: this repository's G-code profile (`pipeline/configs/grbl_a4_pen.toml`) is configured for an "inverted" solenoid mounting where the solenoid being ENERGIZED = pen UP (lift). That means:

- `M3 S1000` → energize solenoid → pen UP (repo default)
- `M5`        → de-energize solenoid → pen DOWN (spring return)

If your hardware is wired the other way (energized = pen DOWN), swap the M3/M5 commands in the G-code profile or rewire the solenoid/MOSFET accordingly.


## Hardware & firmware tests

The full test procedure — standalone hardware sketches and GRBL integration
tests — lives in **[../testing.md](../testing.md)**:

| Phase | Content | Precondition |
| --- | --- | --- |
| [Phase 1](../testing.md#phase-1--standalone-arduino-tests-no-grbl) | Standalone sketches TC1–TC4 (no GRBL) | Wiring complete |
| [Phase 2](../testing.md#phase-2--grbl-integration-tests) | GRBL integration tests TC5-G–TC9-G | Phase 1 passed, GRBL flashed |

Run Phase 1 first, then flash GRBL (see [Build and flash](#build-and-flash)),
then Phase 2.

The Phase 1 sketches live in `firmware/test/`; the PlatformIO env names match
the TC numbers:

```bash
cd firmware
pio run -e tc1_x_axis     -t upload   # TC1 — X-axis movement
pio run -e tc2_x_endstops -t upload   # TC2 — X-axis endstops
pio run -e tc3_y_axis     -t upload   # TC3 — Y-axis movement
pio run -e tc4_pen_lift   -t upload   # TC4 — pen lift (solenoid)
pio device monitor                    # 115200 baud
```

## See also

- Generating G-code from images (this project's pipeline) and third-party
  SVG→G-code / G-code sender tools: [../pipeline/README.md](../pipeline/README.md).

## License

The firmware in `src/` and `test/` is licensed **GPL-3.0-or-later**
([LICENSE](LICENSE)) — it is a derivative of and is compiled/linked together
with [GRBL](https://github.com/gnea/grbl) (GPLv3), so it inherits GRBL's
copyleft. `src/grbl_main_shim.c` is copied from GRBL's `main.c`. The
`grbl/` submodule is upstream GRBL, unchanged (`grbl/COPYING`). See the
[project-wide licensing table](../README.md#license).
