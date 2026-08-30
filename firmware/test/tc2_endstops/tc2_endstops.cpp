/*
  SPDX-License-Identifier: GPL-3.0-or-later
  Copyright (c) 2026 Simon Gerlach

  TC2 – Endstop Test
  ==================
  Standalone Arduino sketch – NO GRBL required.
  Flash with:  pio run -e tc2_endstops -t upload

  Purpose
  -------
  This machine has TWO optical endstops, BOTH on the X axis (X_MIN and
  X_MAX), wired in parallel onto the single X_LIMIT pin (D9). GRBL — and
  this sketch — cannot tell them apart in software; it only sees "X limit
  active". The operator confirms which physical end was reached.
  Y has no endstop.

  Sequence
  --------
    1. Operator centres the carriage. Sketch checks D9 reads "open".
    2. Drive slowly toward X_MIN until D9 goes active; stop; back off.
       Operator confirms: front/left end?
    3. Drive slowly toward X_MAX until D9 goes active; stop; back off.
       Operator confirms: back/right end?
    4. PASS / FAIL.

  Pins (CNC Shield v3 on Arduino Uno)
  ------------------------------------
    D2  – X_STEP   (X_STEP_BIT)
    D5  – X_DIR    (X_DIRECTION_BIT)
    D8  – ENABLE   (STEPPERS_DISABLE_BIT, active LOW)
    D9  – X_LIMIT  (X_LIMIT_BIT) — both X switch signals combined here

  Endstop polarity
  ----------------
  This sketch assumes the optical modules read HIGH when the beam is open
  and LOW when blocked (so "triggered" == LOW). If the idle check below
  reports LOW with the carriage centred, your modules are the other way
  round — invert TRIGGERED_LEVEL here AND set GRBL `$5` accordingly
  (see electronics.md → Endstops).
*/

#include <Arduino.h>
#include "../plotter_pins.h" // pin numbers derived from GRBL cpu_map.h

#define PIN_X_LIMIT PIN_X_MIN // D9 – both X switches (X_MIN + X_MAX) in parallel

// ── Config ────────────────────────────────────────────────────────────────
static constexpr int TRIGGERED_LEVEL = LOW;      // optical: LOW = beam blocked
static constexpr uint16_t STEP_DELAY_US = 800;   // slow creep toward the switch
static constexpr uint8_t STEP_PULSE_US = 10;
static constexpr uint32_t MAX_STEPS = 1500UL;    // safety limit (~300 mm @ 5 steps/mm)
static constexpr uint16_t BACKOFF_STEPS = 25;    // ~5 mm pull-off after a hit

// ── Helpers ───────────────────────────────────────────────────────────────
static bool limitActive()
{
    return digitalRead(PIN_X_LIMIT) == TRIGGERED_LEVEL;
}

static void step(bool dirHigh)
{
    digitalWrite(PIN_X_DIR, dirHigh ? HIGH : LOW);
    delayMicroseconds(5);
    digitalWrite(PIN_X_STEP, HIGH);
    delayMicroseconds(STEP_PULSE_US);
    digitalWrite(PIN_X_STEP, LOW);
    delayMicroseconds(STEP_DELAY_US);
}

static void waitForEnter(const char *prompt)
{
    Serial.println();
    Serial.print(F(">>> "));
    Serial.println(prompt);
    Serial.println(F("    Press ENTER to continue..."));
    while (true)
    {
        if (Serial.available())
        {
            char c = Serial.read();
            if (c == '\n' || c == '\r')
                break;
        }
    }
}

static bool askYesNo(const char *question)
{
    Serial.println();
    Serial.print(F(">>> "));
    Serial.println(question);
    Serial.println(F("    Type 'y' or 'n' and press ENTER."));
    String input = "";
    while (true)
    {
        if (Serial.available())
        {
            char c = Serial.read();
            if (c == '\n' || c == '\r')
            {
                input.trim();
                if (input.equalsIgnoreCase("y"))
                    return true;
                if (input.equalsIgnoreCase("n"))
                    return false;
                Serial.println(F("    Please type 'y' or 'n'."));
                input = "";
            }
            else
            {
                input += c;
            }
        }
    }
}

// Drive until the limit goes active or maxSteps is reached.
static bool driveUntilLimit(bool dirHigh, uint32_t maxSteps)
{
    for (uint32_t i = 0; i < maxSteps; i++)
    {
        if (limitActive())
            return true;
        step(dirHigh);
    }
    return limitActive();
}

static void backOff(bool dirHigh)
{
    for (uint16_t i = 0; i < BACKOFF_STEPS; i++)
        step(dirHigh);
}

// ── Setup / loop ──────────────────────────────────────────────────────────
void setup()
{
    Serial.begin(115200);
    while (!Serial)
    {
    }

    pinMode(PIN_X_STEP, OUTPUT);
    pinMode(PIN_X_DIR, OUTPUT);
    pinMode(PIN_ENABLE, OUTPUT);
    pinMode(PIN_X_LIMIT, INPUT); // no pull-up; optical module has its own supply
    digitalWrite(PIN_X_STEP, LOW);
    digitalWrite(PIN_X_DIR, LOW);
    digitalWrite(PIN_ENABLE, HIGH); // drivers disabled

    Serial.println(F("============================================"));
    Serial.println(F("  TC2 – Endstop Test  (X_MIN + X_MAX on D9)"));
    Serial.println(F("============================================"));

    // ── Step 1: idle check ────────────────────────────────────────────────
    waitForEnter("Place the carriage roughly in the CENTRE of the X rail "
                 "(clear of both endstops).");

    Serial.print(F("\n[TC2] X_LIMIT (D9) idle = "));
    Serial.println(digitalRead(PIN_X_LIMIT) == HIGH ? F("HIGH") : F("LOW"));
    bool idleOk = !limitActive();
    if (!idleOk)
    {
        Serial.println(F("[TC2] ERROR: limit reads ACTIVE with the carriage centred."));
        Serial.println(F("  Either a switch is blocked, the wiring is shorted, or the"));
        Serial.println(F("  module polarity is inverted (flip TRIGGERED_LEVEL and $5)."));
        Serial.println(F("  Test ABORTED."));
        return;
    }
    Serial.println(F("[TC2] Idle state OK (limit open)."));

    digitalWrite(PIN_ENABLE, LOW); // enable drivers
    delay(100);

    // ── Step 2: toward X_MIN ──────────────────────────────────────────────
    Serial.println(F("\n[TC2] Driving toward X_MIN (DIR=LOW)..."));
    bool minFired = driveUntilLimit(/*dirHigh=*/false, MAX_STEPS);
    Serial.println(minFired ? F("[TC2] Limit fired -- stopped.")
                            : F("[TC2] WARNING: step limit reached, no trigger!"));
    if (minFired)
        backOff(/*dirHigh=*/true); // move away from the MIN switch
    bool minCorrect = minFired &&
                      askYesNo("Did the carriage stop at the FRONT/LEFT end (X_MIN)?");

    // Make sure we cleared the switch before the next drive.
    while (limitActive())
        backOff(/*dirHigh=*/true);

    // ── Step 3: toward X_MAX ──────────────────────────────────────────────
    Serial.println(F("\n[TC2] Driving toward X_MAX (DIR=HIGH)..."));
    bool maxFired = driveUntilLimit(/*dirHigh=*/true, MAX_STEPS);
    Serial.println(maxFired ? F("[TC2] Limit fired -- stopped.")
                            : F("[TC2] WARNING: step limit reached, no trigger!"));
    if (maxFired)
        backOff(/*dirHigh=*/false); // move away from the MAX switch
    bool maxCorrect = maxFired &&
                      askYesNo("Did the carriage stop at the BACK/RIGHT end (X_MAX)?");

    digitalWrite(PIN_ENABLE, HIGH); // disable drivers

    // ── Result ───────────────────────────────────────────────────────────
    bool allPass = idleOk && minCorrect && maxCorrect;
    Serial.println(F("\n============================================"));
    Serial.print(F("  Idle open        : "));
    Serial.println(idleOk ? F("PASS") : F("FAIL"));
    Serial.print(F("  X_MIN end        : "));
    Serial.println(minCorrect ? F("PASS") : F("FAIL"));
    Serial.print(F("  X_MAX end        : "));
    Serial.println(maxCorrect ? F("PASS") : F("FAIL"));
    Serial.println(allPass ? F("\n  Overall: PASS") : F("\n  Overall: FAIL"));
    if (!allPass)
    {
        Serial.println(F("\n  Hints:"));
        Serial.println(F("  - No trigger at an end: check the 3-pin wiring (GND/5V/SIG)"));
        Serial.println(F("    and that the optical beam is actually blocked there."));
        Serial.println(F("  - Idle reads active: module polarity inverted -> flip"));
        Serial.println(F("    TRIGGERED_LEVEL and set GRBL $5 the other way."));
    }
    Serial.println(F("============================================"));
}

void loop() {}
