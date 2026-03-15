# Electronics Guide

This document covers the controller setup, wiring, pin mapping, and component details for the G-code Pen Plotter.
For firmware and GRBL configuration see [grbl.md](grbl.md).

## Table of contents
- [Controller and shield](#controller-and-shield)
- [Stepper drivers](#stepper-drivers)
- [Power supply](#power-supply)
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
- Use a supply rated for the **combined peak current** of both stepper motors and the solenoid (typically 3-5 A is sufficient)
- The Arduino is powered separately via USB during flashing; under normal operation the CNC Shield's power jack supplies everything


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

Install **all three MS jumpers** (MS1, MS2, MS3) under each stepper driver on the CNC Shield for **1/16 microstepping**.
This matches `DEFAULT_X/Y_STEPS_PER_MM = 80` in `firmware/src/config.h`.

| MS1 | MS2 | MS3 | Mode |
|-----|-----|-----|------|
| - | - | - | Full step |
| x | - | - | 1/2 |
| - | x | - | 1/4 |
| x | x | - | 1/8 |
| x | x | x | **1/16** <- use this |


## Wiring steps

1. Stack the CNC Shield v3 onto the Arduino Uno.
2. Set the microstepping jumpers (see above).
3. Insert the A4988 stepper drivers for the X and Y slots; leave Z and A empty.
4. Attach heat sinks to the drivers.
5. Route stepper motor and endstop cables through the frame openings into the enclosure.
6. Connect stepper motors to the X and Y terminals on the shield.
7. Connect the optical endstops to the **X-** and **Y-** endstop headers (3-pin: GND / 5 V / Signal).
8. Connect the solenoid MOSFET circuit to **D11** (see solenoid section below).
9. Secure all cables with cable ties and cable management clips to avoid interference with moving parts.
10. Screw the Arduino/Shield assembly onto the PCB holder, slide it onto the rods, and attach the housing.
11. Make sure the USB port and power jack remain accessible.


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

G-code pen control (see [grbl.md](grbl.md) for full GRBL reference):

| G-code | Action |
|--------|--------|
| `M3 S1000` | Solenoid ON -> pen down |
| `M5` | Solenoid OFF -> pen up (spring return) |



## Hardware verification before flashing GRBL

Before flashing GRBL, verify each hardware subsystem independently using the standalone test sketches in `firmware/test/`.
They require no GRBL knowledge and give clear PASS / FAIL feedback via the serial monitor.
**Work through them in order** -- each test builds on the previous one being confirmed working.

| Step | Test sketch | What is verified |
|------|-------------|-----------------|
| 1 | `tc1_x_axis` | X stepper turns, carriage moves in the correct direction |
| 2 | `tc2_x_endstops` | Both X optical endstops fire at the right ends of the rail |
| 3 | `tc3_y_axis` | Y stepper turns, paper feed moves in the correct direction |
| 4 | `tc4_pen_lift` | Solenoid actuates and pen returns to UP on every cycle |

Flash a test sketch with PlatformIO (no GRBL is needed):

```
pio run -e tc1_x_axis -t upload
```

Open the serial monitor at 115 200 baud and follow the on-screen prompts.
See [testing.md](testing.md) for full test documentation including expected results and failure hints.

Only proceed to flashing GRBL once all four tests pass.

