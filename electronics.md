# Electronics Guide

> ⚠️ **Work in progress** — see [TODO.md](TODO.md) for known open issues
> (notably how many endstops the machine has and how they are wired).

This document covers the controller setup, wiring, pin mapping, and component details for the G-code Pen Plotter.
For firmware and GRBL configuration see [firmware/README.md](firmware/README.md).
For the hardware test procedure see [testing.md](testing.md).

## Table of contents

- [Controller and shield](#controller-and-shield)
- [Stepper drivers](#stepper-drivers)
- [Power supply](#power-supply)
- [5 V / GND distribution board](#5-v--gnd-distribution-board)
- [Pin mapping](#pin-mapping-cnc-shield-v3--arduino-uno)
- [Microstepping jumpers](#microstepping-jumpers)
- [Wiring steps](#wiring-steps)
- [Hardware verification before flashing GRBL](#hardware-verification-before-flashing-grbl)
- [Endstops](#endstops)
- [Solenoid pen lift](#solenoid-pen-lift)

## Controller and shield

- **Arduino Uno** (ATmega328P) running GRBL v1.1
- **Arduino CNC Shield v3** stacked on top of the Uno

Only **2 of the 4 possible axes** on the CNC Shield are used:

- **X axis** -- carriage movement via timing belt, with optical endstop
- **Y axis** -- paper feed

## Stepper drivers

- **A4988** (or DRV8825 as drop-in replacement) for X and Y axes
- Attach heat sinks before first use
- Set the current limit via the trimmer pot **before** connecting motors under load -- set to ~70 % of your motor's rated current per phase

## Power supply

- **12 V DC** for NEMA 17 motors and solenoid
- Use a supply rated for the **combined peak current** of both stepper motors and the solenoid

### 12 V power supply

The 12 V supply connects to the **screw terminals on the CNC Shield** (labelled GND and V+), **not** to the Arduino's barrel jack.
From those terminals the voltage is passed through to the Arduino Uno's VIN pin via the shield's stacking header.
The Arduino's on-board voltage regulator converts VIN to the 5 V and 3.3 V rails used by the microcontroller and peripherals.
Use the 12 V supply to also power the MOSFET circuit power input as it will also drive the solenoid.

### USB and 12 V simultaneously

The Arduino Uno contains a power-path selector between the VIN from Stepper shield (and for its own barrel-jack) supply and the USB 5 V rail:

- **12 V via CNC Shield only** — the on-board regulator powers the Arduino; USB is not connected.
- **USB only (no 12 V via barrel jack/stepper shield)** — the Arduino runs from USB 5 V; the stepper drivers and solenoid are unpowered. Use this mode when flashing firmware without the motors connected.
- **Both 12 V and USB simultaneously** — this is the normal setup (UGS command sending from PC while the machine runs). The on-board Schottky diode prevents current from flowing back from the Arduino's 5 V rail into the host PC's USB port. No special precautions are needed.

## 5 V / GND distribution board

Several consumers need a regulated 5 V supply and a common GND:

| Consumer | Supply needed |
|----------|--------------|
| Optical endstops (× 2) | +5 V, GND |
| MOSFET gate circuit | GND (gate pull-down) |
| Button / switch strip (if fitted) | +5 V, GND |

The CNC Shield exposes only a limited number of 5 V and GND pins on its headers, which is not enough for all consumers at once.
The recommended solution is a small **stripboard / perfboard distribution board**.
> Keep the total current draw of 5 V consumers well below 500 mA — the Arduino's on-board regulator (when powered from 12 V via the shield) can supply roughly 300–400 mA at 5 V before thermal throttling. Optical endstops typically draw < 20 mA each, so two endstops + a MOSFET pull-down are well within budget.

## Pin mapping (CNC Shield v3 -> Arduino Uno)

| Function | CNC Shield label | Arduino pin |
|----------|-----------------|-------------|
| X Step | X.STEP | D2 |
| X Direction | X.DIR | D5 |
| Y Step | Y.STEP | D3 |
| Y Direction | Y.DIR | D6 |
| Z Step (unused) | Z.STEP | D4 |
| Z Direction (unused) | Z.DIR | D7 |
| Stepper Enable | EN | D8 (active LOW) |
| X min endstop | X- | D9 |
| Y min endstop | Y- | D10 |
| Pen-lift solenoid PWM | SpnEn / D11 | D11 |
| Abort / Reset | -- | A0 |
| Feed Hold | -- | A1 |
| Cycle Start | -- | A2 |

Verify pin assignments against `firmware/src/config.h`.

## Microstepping jumpers

**Leave all MS jumpers unpopulated** (MS1, MS2, MS3 all open) for **full-step operation**.
This matches `DEFAULT_X/Y_STEPS_PER_MM = 5` in `firmware/src/config.h`.

| MS1 | MS2 | MS3 | Mode |
|-----|-----|-----|------|
| - | - | - | **Full step ← use this** |
| x | - | - | 1/2 |
| - | x | - | 1/4 |
| x | x | - | 1/8 |
| x | x | x | 1/16 |

## Wiring steps

1. Stack the CNC Shield v3 onto the Arduino Uno.
2. Leave all MS jumpers **unpopulated** (full-step operation, no jumpers needed).
3. Insert the A4988 stepper drivers for the X and Y slots; leave Z and A empty.
4. Attach heat sinks to the drivers.
5. Build and mount the 5 V / GND distribution board (see section above); connect it to the Arduino's 5 V and GND pins.
6. Route stepper motor and endstop cables through the frame openings into the enclosure.
7. Connect stepper motors to the X and Y terminals on the shield.
8. Connect the optical endstops to the **X-** and **Y-** endstop headers (3-pin: GND / 5 V / Signal); take GND and 5 V from the distribution board.
9. Connect the solenoid MOSFET circuit to **D11**; connect the gate pull-down GND to the distribution board (see solenoid section below).
10. Connect the 12 V supply to the **screw terminals on the CNC Shield** (not the Arduino barrel jack).
11. Secure all cables with cable ties and cable management clips to avoid interference with moving parts.
12. Screw the Arduino/Shield assembly onto the PCB holder, slide it onto the rods, and attach the housing.
13. Make sure the USB port and the CNC Shield power terminals remain accessible.

## Endstops

The design uses **two optical endstops** -- one for the X axis (carriage home) and one for the Y axis (paper-feed home).

- Wire to the **X-** and **Y-** 3-pin headers on the CNC Shield (GND / +5 V / Signal).
- Optical endstops need the +5 V supply pin; mechanical microswitches only need GND and Signal.
- GRBL is configured with `DEFAULT_INVERT_LIMIT_PINS 1` in `firmware/src/config.h` because optical endstops are HIGH when open and LOW when triggered.
- Internal pull-ups are enabled by GRBL; no external resistors needed for the signal line.

## Solenoid pen lift

The solenoid is switched by the **GRBL spindle PWM output on D11** via an N-channel MOSFET:

```
D11 --[100 Ohm]-- MOSFET gate
MOSFET drain     -- solenoid (-)
solenoid (+)     -- +12 V
Flyback diode    across solenoid coil (cathode -> +12 V)
MOSFET source    -- GND
```

- Use a logic-level N-channel MOSFET (e.g. IRLZ44N, 2N7000).
- The flyback diode (e.g. 1N4007) is **mandatory** to protect the MOSFET from inductive kick.
- Add a 10 kOhm pull-down resistor between gate and source to ensure the MOSFET stays off at power-up.
- Test the solenoid switching with a bench supply and current-limited setup before connecting to the full system.

G-code pen control (see [firmware/README.md](firmware/README.md) for full GRBL reference):

Note: the repository default assumes an inverted solenoid mount where the solenoid being ENERGIZED = pen UP. The wiring and default G-code templates in `pipeline/configs/grbl_a4_pen.toml` follow this convention.

| G-code | Action (repo default) |
|--------|----------------------|
| `M3 S1000` | Solenoid ON → energized (repo default: pen UP) |
| `M5` | Solenoid OFF → de-energized (repo default: pen DOWN via spring) |

If your hardware uses the opposite mapping (energized = pen DOWN), either swap M3/M5 in the G-code templates or invert the solenoid wiring (safer to change the templates).

## Hardware verification before flashing GRBL

Once the wiring above is complete, verify each subsystem independently with the
standalone test sketches in `firmware/test/` (X axis, endstops, Y axis, pen
lift) **before** flashing GRBL. They need no GRBL knowledge and print
PASS / FAIL on the serial monitor.

→ Procedure, expected values and failure diagnosis:
**[testing.md → Phase 1](testing.md#phase-1--standalone-arduino-tests-no-grbl)**.

Only proceed to flashing GRBL once all Phase 1 tests pass.

> **TODO** ([TODO.md](TODO.md)): the pin map above lists one X endstop and one
> Y endstop, but the `tc2_x_endstops` sketch drives the carriage to both ends
> and expects two X endstops. This needs to be resolved.
