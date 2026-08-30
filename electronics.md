# Electronics Guide

> ⚠️ **Work in progress** — see [TODO.md](TODO.md) for known open issues
> (optical-endstop polarity / `$5`, and the not-yet-implemented reduced
> solenoid holding current).

This document covers the controller setup, wiring, pin mapping, and component details for the G-code Pen Plotter.
For firmware and GRBL configuration see [firmware/README.md](firmware/README.md).
For the hardware test procedure see [testing.md](testing.md).

## Table of contents

- [Machine configuration (canonical)](#machine-configuration-canonical)
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

## Machine configuration (canonical)

**Single source of truth for the electrical build.** `firmware/src/config.h`,
the standalone test sketches (`firmware/test/`) and `testing.md` must all
match this table.

### Axes & endstops

| Axis | Function    | Endstops                      | Homes?           |
|------|-------------|-------------------------------|------------------|
| X    | Carriage    | 2 × optical: **X_MIN + X_MAX** | yes → toward MIN |
| Y    | Paper feed  | **none**                      | no               |
| Z    | (unused)    | none                          | no               |

- **Both X switches are wired in parallel onto the X_LIMIT pin (D9).** GRBL
  1.1 on the Uno has only one limit pin per axis, so it cannot tell X_MIN
  from X_MAX — it only ever reports "X limit tripped".
- `$H` homes X toward X_MIN. X_MAX is therefore only a hard-limit backstop.
  The usable X length must be **measured once and stored in `$130`** — see
  [testing.md → TC5b-G "Teach the X-axis length"](testing.md#tc5b-g--teach-the-x-axis-length).
- **Y has no reference.** `Y = 0` is wherever the axis sits at power-up or
  after `$X`. Load the paper, then treat that as the origin.
- Firmware: `HOMING_CYCLE_0 = (1 << X_AXIS)` (X only).

### Solenoid polarity

- **De-energized = pen DOWN (drawing).** This is the safe resting state — no
  coil current, no heat.
- **Energized (`M3`) = pen UP.** Never leave it energized: keep travel moves
  short and make sure every plot ends on `M5`
  (see `pipeline/configs/grbl_a4_pen.toml`).
- A **reduced holding current** during pen-up (pull in at `S1000`, then hold
  at ~`S350`) is planned but **not yet implemented** — see the
  [Solenoid pen lift](#solenoid-pen-lift) section and [TODO.md](TODO.md).

## Controller and shield

- **Arduino Uno** (ATmega328P) running GRBL v1.1
- **Arduino CNC Shield v3** stacked on top of the Uno

Only **2 of the 4 possible axes** on the CNC Shield are used:

- **X axis** -- carriage movement via timing belt, with X_MIN + X_MAX optical endstops
- **Y axis** -- paper feed (no endstop)

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
| Optical endstops (× 2, both on X) | +5 V, GND |
| MOSFET gate circuit | GND (gate pull-down) |
| Button / switch strip (if fitted) | +5 V, GND |

The CNC Shield exposes only a limited number of 5 V and GND pins on its headers, which is not enough for all consumers at once.
The recommended solution is a small **stripboard / perfboard distribution board**.
> Keep the total current draw of 5 V consumers well below 500 mA — the Arduino's on-board regulator (when powered from 12 V via the shield) can supply roughly 300–400 mA at 5 V before thermal throttling. Optical endstops typically draw < 20 mA each, so two endstops + a MOSFET pull-down are well within budget.

## Pin mapping (CNC Shield v3 -> Arduino Uno)

| Function | CNC Shield label | Arduino pin | Notes |
|----------|-----------------|-------------|-------|
| X Step | X.STEP | D2 | |
| X Direction | X.DIR | D5 | |
| Y Step | Y.STEP | D3 | |
| Y Direction | Y.DIR | D6 | |
| Z Step (unused) | Z.STEP | D4 | |
| Z Direction (unused) | Z.DIR | D7 | |
| Stepper Enable | EN | D8 | active LOW |
| X endstops **X_MIN + X_MAX** | X- | D9 | both switches in parallel on this one pin |
| Y endstop *(none)* | Y- | D10 | GRBL `Y_LIMIT` — **leave unconnected** |
| Pen-lift solenoid | *(see below)* | **D11** | GRBL `SPINDLE_PWM` (needs `VARIABLE_SPINDLE`). Not on the "SpnEn" header — that is **D12**. Tap D11 at the **Z-endstop header** (hard-wired to D11 on the shield) or solder to the D11 pin. |
| *(Z_LIMIT — unused)* | Z- | D12 | relocated here by `VARIABLE_SPINDLE`; leave unconnected |
| Abort / Reset | -- | A0 | optional |
| Feed Hold | -- | A1 | optional |
| Cycle Start | -- | A2 | optional |

Verify pin assignments against `firmware/src/config.h` and the
[canonical table](#machine-configuration-canonical) above.

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
8. Connect **both X optical endstops** (X_MIN and X_MAX) to the **X-** endstop header (3-pin: GND / 5 V / Signal), signal lines combined onto the one pin; take GND and 5 V from the distribution board. Leave the **Y-** header unconnected.
9. Connect the solenoid MOSFET gate circuit to **D11** (tap the Z-endstop header or solder the D11 pin — see [pin mapping](#pin-mapping-cnc-shield-v3--arduino-uno)); connect the gate pull-down GND to the distribution board (see solenoid section below).
10. Connect the 12 V supply to the **screw terminals on the CNC Shield** (not the Arduino barrel jack).
11. Secure all cables with cable ties and cable management clips to avoid interference with moving parts.
12. Screw the Arduino/Shield assembly onto the PCB holder, slide it onto the rods, and attach the housing.
13. Make sure the USB port and the CNC Shield power terminals remain accessible.

## Endstops

The design uses **two optical endstops, both on the X axis** — `X_MIN` at the
home end and `X_MAX` at the far end. **The Y axis (paper feed) has no
endstop.** See the [canonical table](#machine-configuration-canonical).

- Both X switch signal lines are combined onto the single **X-** header pin
  (Arduino D9 = GRBL `X_LIMIT`). GRBL cannot distinguish the two; it only
  reports "X limit tripped". `$H` homes to X_MIN; the X_MAX position is
  taught into `$130` (see [testing.md → TC5b-G](testing.md#tc5b-g--teach-the-x-axis-length)).
- The **Y-** header stays unconnected. If hard limits (`$21=1`) are enabled,
  make sure the unused `Y_LIMIT` (D10) and `Z_LIMIT` (D12) pins are not
  floating into a "triggered" state — GRBL's internal pull-ups plus the
  correct `$5` value should leave them reading "clear".
- Optical endstops need the +5 V supply pin; mechanical microswitches only need GND and Signal.
- Internal pull-ups are enabled by GRBL; no external resistors needed for the signal line.

> **TODO** ([TODO.md](TODO.md)): `DEFAULT_INVERT_LIMIT_PINS` (`$5`) is set to
> `1` with the rationale "optical endstops are HIGH when open, LOW when
> triggered" — but in GRBL 1.1 that polarity means `$5` should be `0`
> (`$5=1` → *HIGH* = triggered). The setting is **unverified**. Measure the
> real module output (beam clear vs. blocked), set `$5` accordingly, fix the
> comment in `firmware/src/config.h`, and confirm the two parallel X switches
> can share D9 without an output clash (open-collector / wired-OR).

## Solenoid pen lift

The solenoid is switched by the **GRBL spindle PWM output on D11** via an N-channel MOSFET.

**Which pin, and where to tap it.** GRBL's PWM/enable output is on **D11**
*only* when `VARIABLE_SPINDLE` is enabled in `firmware/src/config.h` (it is —
and it also moves the unused `Z_LIMIT` to D12). D11 is **not** the CNC Shield
"SpnEn" header (that pad is D12). Get D11 from:

- the **Z-endstop header** (`Z-` / `Z+`), which is hard-wired to D11 on the
  CNC Shield v3 — the same trick laser add-ons use; or
- a wire soldered directly to the Arduino D11 pin.

```
D11 --[100 Ohm]-- MOSFET gate
MOSFET drain     -- solenoid (-)
solenoid (+)     -- +12 V
Flyback diode    across solenoid coil (cathode -> +12 V)
MOSFET source    -- GND
gate --[10 kOhm]-- GND   (pull-down: MOSFET off at power-up)
```

- Use a logic-level N-channel MOSFET (e.g. IRLZ44N, 2N7000).
- The flyback diode (e.g. 1N4007) is **mandatory** to protect the MOSFET from inductive kick.
- Test the solenoid switching with a bench supply and current-limited setup before connecting to the full system.
- If you use an opto-isolated MOSFET *module* rather than a bare MOSFET, note
  that GRBL's spindle PWM carrier is ~1 kHz — fine at `S1000` (steady on), but
  a slow module may not pass a partial duty cycle cleanly (relevant only for
  the holding-current idea below).

### Polarity (this build)

**De-energized = pen DOWN (drawing).** No coil current in the resting state,
so no heat. Energized (`M3`) = pen UP. The solenoid **must not stay energized
for long** — the coil overheats.

| G-code | Solenoid | Pen |
|--------|----------|-----|
| `M3 S1000` | energized (PWM ~100 %) | UP |
| `M5` | de-energized | DOWN (drawing) |

The G-code templates in `pipeline/configs/grbl_a4_pen.toml` follow this: `M5`
before each drawn path, `M3 S1000` for travel moves, and every file ends on
`M5`. Keep travel moves short (path ordering / `linesort` is on by default).

### Planned: reduced holding current (not yet implemented)

A pull solenoid needs full current only to *move* the plunger; *holding* it
needs far less. With PWM on D11 this can be exploited to cut the pen-up heat
to roughly a third:

1. **Firmware / settings** — nothing to change; `VARIABLE_SPINDLE` already
   gives PWM, and `$30=1000` maps `S1000` → 100 % duty.
2. **G-code profile** — in `pipeline/configs/grbl_a4_pen.toml`, change the
   per-path pen-up template so it pulls in at full current, then drops to a
   hold level, e.g.:

   ```toml
   line_end = "M3 S1000\nG4 P0.05\nM3 S350\n"   # pull in, then hold at ~35 %
   ```

   Tune the hold value (`S250`–`S500`) to the lowest that reliably keeps the
   pen lifted. `document_start` would get the same treatment.
3. **Verify** — run a long plot and check the coil temperature by hand
   afterwards; it should be no more than warm.

Until this is done, the mitigation is purely "short travels + end on `M5`".

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
