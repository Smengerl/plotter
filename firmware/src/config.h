/*
  SPDX-License-Identifier: GPL-3.0-or-later
  Copyright (c) 2026 Simon Gerlach

  config.h  —  Plotter-specific GRBL compile-time overrides
  --------------------------------------------------------------------------
  Force-included into every translation unit via `-include src/config.h` in
  platformio.ini. It pulls in the *complete* stock grbl/grbl/config.h and
  then applies the few overrides this machine needs. The GRBL submodule is
  left untouched.

  Only compile-time settings live here. Everything that GRBL exposes as a
  `$` setting (steps/mm, feed rates, acceleration, travel, limit inversion,
  homing enable/direction/rates) is stored in EEPROM on the board — set it
  there, see firmware/README.md "Key GRBL settings", not here.

  Machine summary (canonical table: electronics.md "Machine configuration"):
    - Arduino Uno + CNC Shield v3, GRBL 1.1
    - X = carriage, Y = paper feed, Z disabled
    - 2 optical endstops, BOTH on X (X_MIN + X_MAX), parallel on X_LIMIT (D9);
      Y has no endstop
    - Homing: X only, toward X_MIN. X_MAX is a hard-limit backstop; the usable
      X length is taught into $130 (testing.md "TC5b-G")
    - Solenoid pen-lift on the spindle PWM output (D11); de-energized = pen
      down (drawing), energized = pen up. Relies on VARIABLE_SPINDLE.
*/

#ifndef PLOTTER_CONFIG_H
#define PLOTTER_CONFIG_H

// Pull in the stock GRBL config (CPU map, DEFAULTS_GENERIC, VARIABLE_SPINDLE,
// every feature toggle). `#define grbl_h` around the include suppresses the
// recursive `#include "grbl.h"` inside stock config.h — that would otherwise
// process grbl.h (and cpu_map.h) before CPU_MAP_ATMEGA328P is defined. The
// real grbl.h include (from grbl_main_shim.c) runs normally afterwards.
#define grbl_h
#include "../grbl/grbl/config.h"
#undef grbl_h

// ── Plotter overrides — applied AFTER stock config.h ─────────────────────

// VARIABLE_SPINDLE (stock: enabled by default) puts the spindle PWM on D11 —
// the pin the solenoid MOSFET is wired to — and relocates the unused Z_LIMIT
// to D12. Fail the build if a future upstream change ever drops it.
#ifndef VARIABLE_SPINDLE
#error "VARIABLE_SPINDLE must stay enabled: the pen-lift solenoid is on D11"
#endif

// Homing cycle: X axis only. Y has no endstop; Z is disabled. GRBL cannot
// tell X_MIN from X_MAX (they share the X_LIMIT pin), so $H homes to X_MIN.
#undef  HOMING_CYCLE_0
#define HOMING_CYCLE_0 (1 << X_AXIS)
#ifdef  HOMING_CYCLE_1
#undef  HOMING_CYCLE_1   // stock: (X|Y) — not wanted, Y is not homed
#endif

// ── $-settings to apply on the board after flashing ─────────────────────
// (power-up defaults come from stock DEFAULTS_GENERIC and are generic; the
//  values below live in EEPROM — see firmware/README.md)
//   $100=5   $101=5           steps/mm  (2GT 20T pulley, A4988 full-step)
//   $110=3000 $111=3000       max rate (mm/min)
//   $120=200  $121=200        acceleration (mm/s^2)
//   $130=<taught> $131=300    max travel (X via TC5b-G)
//   $5=?                      invert limit pins — UNVERIFIED, see TODO.md
//   $20=0 $21=0 $22=1 $23=0 $24=50 $25=800 $27=5
//   $30=1000 $31=0            spindle range -> S1000 = full solenoid drive

#endif // PLOTTER_CONFIG_H
