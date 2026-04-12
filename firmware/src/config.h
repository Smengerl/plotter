/*
  config.h  —  Plotter-specific GRBL compile-time configuration
  ---------------------------------------------------------------
  This file REPLACES grbl/grbl/config.h for this build.
  PlatformIO adds firmware/src/ first in the include search path, so
  this header is found before the one inside the GRBL submodule.

  Hardware:
    - Arduino Uno (ATmega328P)
    - Arduino CNC Shield v3
    - 2× NEMA 17 stepper motors (X = carriage, Y = paper feed)
    - 2× Optical endstops (X_MIN / Y_MIN on the CNC shield)
    - Solenoid pen-lift on the spindle PWM output (D11 on CNC Shield)
    - 12 V power supply

  Key design decisions:
    - Z axis is DISABLED (only X and Y are used for a 2-axis plotter)
    - Spindle PWM output (D11) drives the pen-lift solenoid via a MOSFET
    - Homing enabled on X and Y; home position = front-left corner
    - Soft limits enabled once work area is measured
    - Steps/mm tuned for 2GT belt + 20T pulley + A4988 @ full-step (no MS jumpers)
*/

#ifndef config_h
#define config_h
#include "grbl.h" // required for Arduino IDE / PlatformIO compatibility

// ── CPU / pin map ─────────────────────────────────────────────────────────────
#define CPU_MAP_ATMEGA328P // Arduino Uno — official GRBL target

// ── Default machine settings ──────────────────────────────────────────────────
// We define our own defaults block instead of using DEFAULTS_GENERIC so we
// never have to edit the submodule sources.
// NOTE: All values can be permanently overridden at runtime via $xx= commands
//       and are stored in EEPROM.  These are only the power-up defaults.

// Steps/mm calculation:
//   Motor:       200 full steps/rev
//   Microstepping: none (full step) →  200 steps/rev
//   Pulley:      20 teeth × 2 mm pitch = 40 mm/rev
//   → 200 / 40 = 5 steps/mm
#define DEFAULT_X_STEPS_PER_MM 5.0
#define DEFAULT_Y_STEPS_PER_MM 5.0
#define DEFAULT_Z_STEPS_PER_MM 5.0 // Z unused but must be defined

// Feed rates (mm/min)
#define DEFAULT_X_MAX_RATE 3000.0
#define DEFAULT_Y_MAX_RATE 3000.0
#define DEFAULT_Z_MAX_RATE 500.0 // unused

// Acceleration (mm/min²) — conservative start value; tune upward as needed
#define DEFAULT_X_ACCELERATION (200.0 * 60.0 * 60.0)
#define DEFAULT_Y_ACCELERATION (200.0 * 60.0 * 60.0)
#define DEFAULT_Z_ACCELERATION (10.0 * 60.0 * 60.0) // unused

// Work area — A4 paper (210 × 297 mm) with a small safety margin
#define DEFAULT_X_MAX_TRAVEL 220.0 // mm
#define DEFAULT_Y_MAX_TRAVEL 300.0 // mm
#define DEFAULT_Z_MAX_TRAVEL 5.0   // mm (unused, keep small)

// Spindle — repurposed as solenoid (pen up/down via M3/M5 or S0/S1000)
#define DEFAULT_SPINDLE_RPM_MAX 1000.0
#define DEFAULT_SPINDLE_RPM_MIN 0.0

// Step pulse width
#define DEFAULT_STEP_PULSE_MICROSECONDS 10

// Direction inversion mask
// Bit 0 = X, Bit 1 = Y, Bit 2 = Z
// Set to invert an axis if your carriage moves the wrong way (try 0, 1, 2, or 3)
#define DEFAULT_STEPPING_INVERT_MASK 0
#define DEFAULT_DIRECTION_INVERT_MASK 0

// Stepper idle lock: keep motors energised 250 ms after last move, then disable
#define DEFAULT_STEPPER_IDLE_LOCK_TIME 25 // ms (255 = always on)

// Status report: include machine position
#define DEFAULT_STATUS_REPORT_MASK 1

// Path blending
#define DEFAULT_JUNCTION_DEVIATION 0.01 // mm
#define DEFAULT_ARC_TOLERANCE 0.002     // mm

// Reporting
#define DEFAULT_REPORT_INCHES 0 // metric

// Pin logic
#define DEFAULT_INVERT_ST_ENABLE 0  // A4988: LOW = enabled (correct default)
#define DEFAULT_INVERT_LIMIT_PINS 1 // Optical endstops are HIGH when open,
                                    // LOW when triggered → invert so GRBL
                                    // sees active-high as "triggered"
// Limits
#define DEFAULT_SOFT_LIMIT_ENABLE 0 // Enable after confirming work area
#define DEFAULT_HARD_LIMIT_ENABLE 0 // Enable after wiring is verified

// Probe
#define DEFAULT_INVERT_PROBE_PIN 0

// Spindle as solenoid → not laser mode
#define DEFAULT_LASER_MODE 0

// ── Homing ────────────────────────────────────────────────────────────────────
// Home both axes in a single cycle (2-axis machine, no Z homing needed)
#define DEFAULT_HOMING_ENABLE 1
#define DEFAULT_HOMING_DIR_MASK 0         // Both axes home toward MIN switches
#define DEFAULT_HOMING_FEED_RATE 50.0     // mm/min (slow locate pass)
#define DEFAULT_HOMING_SEEK_RATE 800.0    // mm/min (fast search pass)
#define DEFAULT_HOMING_DEBOUNCE_DELAY 250 // ms
#define DEFAULT_HOMING_PULLOFF 5.0        // mm (back off after homing)

// Force alarm on power-up until homing cycle completes
#define HOMING_INIT_LOCK

// Homing cycle: home X and Y simultaneously (no Z axis)
#define HOMING_CYCLE_0 ((1 << X_AXIS) | (1 << Y_AXIS))
// Leave HOMING_CYCLE_1 / HOMING_CYCLE_2 undefined (no Z homing)

// ── GRBL behaviour ────────────────────────────────────────────────────────────
// Baud rate
#define BAUD_RATE 115200

// Real-time commands (keep GRBL defaults)
#define CMD_RESET 0x18 // Ctrl-X
#define CMD_STATUS_REPORT '?'
#define CMD_CYCLE_START '~'
#define CMD_FEED_HOLD '!'

#define CMD_SAFETY_DOOR 0x84
#define CMD_JOG_CANCEL 0x85
#define CMD_DEBUG_REPORT 0x86
#define CMD_FEED_OVR_RESET 0x90
#define CMD_FEED_OVR_COARSE_PLUS 0x91
#define CMD_FEED_OVR_COARSE_MINUS 0x92
#define CMD_FEED_OVR_FINE_PLUS 0x93
#define CMD_FEED_OVR_FINE_MINUS 0x94
#define CMD_RAPID_OVR_RESET 0x95
#define CMD_RAPID_OVR_MEDIUM 0x96
#define CMD_RAPID_OVR_LOW 0x97
#define CMD_SPINDLE_OVR_RESET 0x99
#define CMD_SPINDLE_OVR_COARSE_PLUS 0x9A
#define CMD_SPINDLE_OVR_COARSE_MINUS 0x9B
#define CMD_SPINDLE_OVR_FINE_PLUS 0x9C
#define CMD_SPINDLE_OVR_FINE_MINUS 0x9D
#define CMD_SPINDLE_OVR_STOP 0x9E
#define CMD_COOLANT_FLOOD_OVR_TOGGLE 0xA0
#define CMD_COOLANT_MIST_OVR_TOGGLE 0xA1

// Number of startup lines stored in EEPROM
#define N_STARTUP_LINE 2

// Decimal places in status reports
#define N_DECIMAL_COORDVALUE_INCH 4
#define N_DECIMAL_COORDVALUE_MM 3
#define N_DECIMAL_RATEVALUE_INCH 1
#define N_DECIMAL_RATEVALUE_MM 0
#define N_DECIMAL_SETTINGVALUE 3
#define N_DECIMAL_RPMVALUE 0

// Probe coordinate report after successful probe cycle
#define MESSAGE_PROBE_COORDINATES

// Safety door / flood coolant delays
#define SAFETY_DOOR_SPINDLE_DELAY 4.0 // s
#define SAFETY_DOOR_COOLANT_DELAY 1.0 // s

// Homing locate cycles (1 is fine for optical switches)
#define N_HOMING_LOCATE_CYCLE 1

#endif // config_h
