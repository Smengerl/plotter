/*
  main.cpp  —  PlatformIO entry point for GRBL on the G-code Pen Plotter
  -----------------------------------------------------------------------
  This file is the Arduino-framework wrapper that calls the standard GRBL
  main() function.  All real work happens inside the GRBL C sources that
  are compiled in via platformio.ini (build_src_filter).

  Hardware summary
  ────────────────
  Board         : Arduino Uno (ATmega328P)
  Shield        : Arduino CNC Shield v3
  Axes in use   : X (carriage / pen left-right)
                  Y (paper feed / pen up-down on sheet)
  Pen lift      : Solenoid on Spindle PWM output (D11 on CNC Shield)
                  → driven via N-channel MOSFET with flyback diode
                  → controlled via G-code M3 Sxxx / M5
  Endstops      : 2× optical, wired to X_MIN (D9) and Y_MIN (D10)

  GRBL pin mapping (CNC Shield v3 → Arduino Uno)
  ──────────────────────────────────────────────
  Function          Shield label   Arduino pin
  ────────────────────────────────────────────
  X Step            X.STEP         D2
  X Direction       X.DIR          D5
  Y Step            Y.STEP         D3
  Y Direction       Y.DIR          D6
  Z Step            Z.STEP         D4  (unused)
  Z Direction       Z.DIR          D7  (unused)
  Stepper Enable    EN             D8  (active LOW → A4988 enabled)
  X min endstop     X-             D9
  Y min endstop     Y-             D10
  Spindle PWM       SpnEn/D11      D11 → pen-lift solenoid MOSFET gate
  Abort / Reset     A0
  Feed Hold         A1
  Cycle Start       A2
  Coolant / Mist    A3 / A4        (unused)
  Probe             A5             (unused)

  Microstep jumpers (MS1/MS2/MS3 under each driver on the shield)
  ────────────────────────────────────────────────────────
  All three jumpers installed → 1/16 microstepping (default assumed)
  Match DEFAULT_X/Y_STEPS_PER_MM in config.h if you change this.

  Solenoid wiring
  ───────────────
  D11 (PWM) ──[100 Ω]── MOSFET gate
  MOSFET drain ── solenoid (−)
  solenoid (+) ── 12 V
  Flyback diode across solenoid coil (cathode to +12 V)
  MOSFET source ── GND

  Pen up/down G-code
  ──────────────────
  M3 S1000  → solenoid ON  → pen DOWN (or pen UP, depending on your mechanism)
  M5        → solenoid OFF → pen UP   (spring returns)
  Adjust polarity by swapping solenoid wires or inverting the MOSFET logic.
*/

extern "C"
{
    // GRBL is written in C; we declare its main() so C++ can call it.
    int grbl_main(void);
}

// The Arduino framework calls setup() once and then loop() forever.
// We never return from grbl_main(), so setup() is the whole program.
extern "C" void setup()
{
    grbl_main(); // never returns
}

extern "C" void loop()
{
    // grbl_main() contains its own infinite loop; this is never reached.
}
