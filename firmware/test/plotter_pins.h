/*
  plotter_pins.h
  ==============
  Translate GRBL pin definitions (AVR port bit numbers from cpu_map.h)
  to Arduino pin numbers.

  GRBL stores pins as bit positions within AVR I/O ports:
    PORTD bit N  →  Arduino digital pin N       (D0 – D7)
    PORTB bit N  →  Arduino digital pin N + 8   (D8 – D13)
    PORTC bit N  →  Arduino analog pin N = A0+N (A0 – A5)

  This file must be included AFTER CPU_MAP_ATMEGA328P is defined
  (set via -DCPU_MAP_ATMEGA328P in the build flags in platformio.ini)
  so that cpu_map.h activates the correct pin block.

  Usage in test sketches:
    #include "../plotter_pins.h"
*/

#pragma once

// cpu_map.h contains all bit definitions for CPU_MAP_ATMEGA328P.
// CPU_MAP_ATMEGA328P must be defined before this include
// (set via -DCPU_MAP_ATMEGA328P in the build flags of the test environments).
#include "cpu_map.h"

// ── Stepper pins (step / direction) ───────────────────────────────────────
// Bit definitions in cpu_map.h: X_STEP_BIT, Y_STEP_BIT, … on PORTD
// PORTD bit N → Arduino pin N (direct mapping for D0–D7)

#define PIN_X_STEP (X_STEP_BIT)     // PORTD bit 2 → D2
#define PIN_Y_STEP (Y_STEP_BIT)     // PORTD bit 3 → D3
#define PIN_X_DIR (X_DIRECTION_BIT) // PORTD bit 5 → D5
#define PIN_Y_DIR (Y_DIRECTION_BIT) // PORTD bit 6 → D6

// ── Enable pin (shared by all axes, active LOW) ───────────────────────────
// STEPPERS_DISABLE_BIT is on PORTB → Arduino pin = bit + 8

#define PIN_ENABLE (STEPPERS_DISABLE_BIT + 8) // PORTB bit 0 → D8

// ── Endstop pins ──────────────────────────────────────────────────────────
// X_LIMIT_BIT / Y_LIMIT_BIT are on PORTB → Arduino pin = bit + 8

#define PIN_X_MIN (X_LIMIT_BIT + 8) // PORTB bit 1 → D9
#define PIN_Y_MIN (Y_LIMIT_BIT + 8) // PORTB bit 2 → D10

// ── Solenoid / spindle PWM pin ────────────────────────────────────────────
// SPINDLE_PWM_BIT is on PORTB → Arduino pin = bit + 8

#define PIN_SOLENOID (SPINDLE_PWM_BIT + 8) // PORTB bit 3 → D11
