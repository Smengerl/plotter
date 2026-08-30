/*
  SPDX-License-Identifier: GPL-3.0-or-later
  Copyright (c) 2026 Simon Gerlach

  TC2 – X-Axis Endstop Test
  ==========================
  Standalone Arduino sketch – NO GRBL required.
  Flash with:  pio run -e tc2_x_endstops -t upload

  Purpose
  -------
  Verifies both X-axis optical endstops:
    - Neither fires when the carriage is in the middle
    - MIN endstop fires when the carriage reaches the MIN end
    - MAX endstop fires when the carriage reaches the MAX end
  The sketch drives the carriage slowly until an endstop signal changes
  state, then stops and asks the operator for confirmation.

  Pins (CNC Shield v3 on Arduino Uno)
  ------------------------------------
    D2  – X_STEP   (X_STEP_BIT in cpu_map.h)
    D5  – X_DIR    (X_DIRECTION_BIT in cpu_map.h)
    D8  – ENABLE   (STEPPERS_DISABLE_BIT in cpu_map.h, active LOW)
    D9  – X_MIN endstop (X_LIMIT_BIT in cpu_map.h, optical: HIGH=open, LOW=triggered)
    D10 – X_MAX endstop (Y_LIMIT_BIT in cpu_map.h, wired as second X endstop on CNC Shield)

  Note on endstop logic
  ---------------------
  Optical endstops are HIGH when the beam is unbroken (open) and LOW
  when the beam is blocked (triggered).  This matches the GRBL setting
  DEFAULT_INVERT_LIMIT_PINS 1 in config.h.  This sketch reads the raw
  pin level directly, so "triggered" == LOW.
*/

#include <Arduino.h>
#include "../plotter_pins.h" // pin numbers derived from GRBL cpu_map.h

// PIN_X_MAX: the CNC Shield wires the Y_LIMIT pin (D10) as the second X endstop.
// Y_LIMIT_BIT is on PORTB → Arduino pin = Y_LIMIT_BIT + 8 = D10.
// This matches the PIN_Y_MIN definition in plotter_pins.h;
// here it is used semantically as the X_MAX endstop.
#define PIN_X_MAX PIN_Y_MIN // D10 – wired as X_MAX on the CNC Shield

// ── Motion parameters ──────────────────────────────────────────────────────
static constexpr uint16_t STEP_DELAY_US = 800; // slow creep toward endstop
static constexpr uint8_t STEP_PULSE_US = 10;
static constexpr uint32_t MAX_STEPS = 1500UL; // safety limit (~300 mm @ 5 steps/mm full step)

// ── Helpers ────────────────────────────────────────────────────────────────
static bool endstopTriggered(uint8_t pin)
{
    return digitalRead(pin) == LOW; // optical: LOW = triggered
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
    Serial.println(F("    Type 'y' (yes) or 'n' (no) and press ENTER."));
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

// Drive until the given endstop fires OR max_steps is reached.
// Returns true if the endstop fired before the step limit.
static bool driveUntilTriggered(uint8_t stopPin, bool dirHigh, uint32_t maxSteps)
{
    digitalWrite(PIN_X_DIR, dirHigh ? HIGH : LOW);
    delayMicroseconds(5);
    for (uint32_t i = 0; i < maxSteps; i++)
    {
        if (endstopTriggered(stopPin))
            return true;
        digitalWrite(PIN_X_STEP, HIGH);
        delayMicroseconds(STEP_PULSE_US);
        digitalWrite(PIN_X_STEP, LOW);
        delayMicroseconds(STEP_DELAY_US);
    }
    return endstopTriggered(stopPin); // last check
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
    pinMode(PIN_X_MIN, INPUT); // no internal pull-up; optical endstop has own supply
    pinMode(PIN_X_MAX, INPUT);
    digitalWrite(PIN_X_STEP, LOW);
    digitalWrite(PIN_X_DIR, LOW);
    digitalWrite(PIN_ENABLE, HIGH); // disabled

    Serial.println(F("============================================"));
    Serial.println(F("  TC2 – X-Axis Endstop Test"));
    Serial.println(F("============================================"));
    Serial.println(F("Verifies both X endstops (MIN and MAX)."));
    Serial.println(F("Optical endstop logic: HIGH = open, LOW = triggered."));

    // ── Step 1: idle check ──────────────────────────────────────────────────
    waitForEnter("Place the carriage roughly in the CENTRE of the X rail "
                 "(clear of both endstops).");

    bool minIdle = !endstopTriggered(PIN_X_MIN);
    bool maxIdle = !endstopTriggered(PIN_X_MAX);

    Serial.println(F("\n[TC2] Endstop idle state:"));
    Serial.print(F("  X_MIN (D9)  = "));
    Serial.println(digitalRead(PIN_X_MIN) == HIGH ? F("HIGH (open) -- OK") : F("LOW  (triggered!) -- CHECK WIRING"));
    Serial.print(F("  X_MAX (D10) = "));
    Serial.println(digitalRead(PIN_X_MAX) == HIGH ? F("HIGH (open) -- OK") : F("LOW  (triggered!) -- CHECK WIRING"));

    if (!minIdle || !maxIdle)
    {
        Serial.println(F("\n[TC2] ERROR: One or both endstops are already triggered."));
        Serial.println(F("  Check wiring and make sure the carriage is not at an end."));
        Serial.println(F("  Test ABORTED."));
        return;
    }
    Serial.println(F("  Both endstops open -- OK"));

    // ── Step 2: drive toward MIN ────────────────────────────────────────────
    Serial.println(F("\n[TC2] Enabling drivers. Driving toward X_MIN (DIR=LOW)..."));
    digitalWrite(PIN_ENABLE, LOW);
    delay(100);

    bool minFired = driveUntilTriggered(PIN_X_MIN, /*dirHigh=*/false, MAX_STEPS);

    if (minFired)
    {
        Serial.println(F("[TC2] X_MIN endstop fired -- carriage stopped."));
    }
    else
    {
        Serial.println(F("[TC2] WARNING: Reached step limit without X_MIN firing!"));
    }

    bool minCorrect = askYesNo("Did the carriage stop at the FRONT/LEFT end (X_MIN position)?");

    // ── Step 3: drive toward MAX ────────────────────────────────────────────
    Serial.println(F("\n[TC2] Driving toward X_MAX (DIR=HIGH)..."));

    bool maxFired = driveUntilTriggered(PIN_X_MAX, /*dirHigh=*/true, MAX_STEPS);

    if (maxFired)
    {
        Serial.println(F("[TC2] X_MAX endstop fired -- carriage stopped."));
    }
    else
    {
        Serial.println(F("[TC2] WARNING: Reached step limit without X_MAX firing!"));
    }

    bool maxCorrect = askYesNo("Did the carriage stop at the BACK/RIGHT end (X_MAX position)?");

    // ── Result ──────────────────────────────────────────────────────────────
    digitalWrite(PIN_ENABLE, HIGH);

    Serial.println(F("\n============================================"));
    Serial.println(F("  TC2 RESULT"));
    Serial.println(F("============================================"));
    Serial.print(F("  Idle state (no endstop triggered): "));
    Serial.println((minIdle && maxIdle) ? F("PASS") : F("FAIL"));
    Serial.print(F("  X_MIN fires at correct end       : "));
    Serial.println((minFired && minCorrect) ? F("PASS") : F("FAIL"));
    Serial.print(F("  X_MAX fires at correct end       : "));
    Serial.println((maxFired && maxCorrect) ? F("PASS") : F("FAIL"));

    bool allPass = minIdle && maxIdle && minFired && minCorrect && maxFired && maxCorrect;
    Serial.println(allPass ? F("\n  Overall: PASS") : F("\n  Overall: FAIL"));

    if (!allPass)
    {
        Serial.println(F("\n  Hints:"));
        Serial.println(F("  - Endstop not firing: check 3-pin wiring (GND/5V/SIG) and"));
        Serial.println(F("    confirm the optical beam is actually blocked at that end."));
        Serial.println(F("  - Wrong endstop fires: X_MIN and X_MAX cables may be swapped."));
        Serial.println(F("  - Both idle as LOW: check 5V supply on the endstop header."));
    }
    Serial.println(F("============================================"));
}

void loop() {}
