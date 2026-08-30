/*
  SPDX-License-Identifier: GPL-3.0-or-later
  Copyright (c) 2026 Simon Gerlach

  TC1 – X-Axis Movement Test
  ==========================
  Standalone Arduino sketch – NO GRBL required.
  Flash with:  pio run -e tc1_x_axis -t upload

  Purpose
  -------
  Drives the X stepper a fixed number of steps in both directions so the
  operator can verify:
    - The correct motor moves  (X = carriage, not the paper feed)
    - The carriage moves in the expected direction for each DIR level

  Pins (CNC Shield v3 on Arduino Uno)
  ------------------------------------
    D2  – X_STEP   (X_STEP_BIT in cpu_map.h)
    D5  – X_DIR    (X_DIRECTION_BIT in cpu_map.h)
    D8  – ENABLE   (STEPPERS_DISABLE_BIT in cpu_map.h, active LOW)

  Expected behaviour
  ------------------
  1. Serial prompt asks operator to centre the carriage.
  2. After confirmation the carriage moves RIGHT (DIR HIGH) 25 steps (~5 mm).
  3. Serial prompt asks operator to confirm direction.
  4. Carriage moves LEFT (DIR LOW) 50 steps (~10 mm, back past centre).
  5. Serial prompt asks operator to confirm direction.
  6. Test ends with PASS / FAIL summary.
*/

#include <Arduino.h>
#include "../plotter_pins.h" // pin numbers derived from GRBL cpu_map.h

// ── Motion parameters ─────────────────────────────────────────────────────
// 5 steps/mm @ full step (no MS jumpers) → 25 steps = 5 mm
static constexpr uint16_t STEPS_PER_MOVE = 25; // steps per single move
static constexpr uint16_t STEP_DELAY_US = 500; // µs between step pulses (≈ slow/safe)
static constexpr uint8_t STEP_PULSE_US = 10;   // µs pulse width

// ── Helpers ───────────────────────────────────────────────────────────────
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

static void moveSteps(uint16_t steps, bool dirHigh)
{
    digitalWrite(PIN_X_DIR, dirHigh ? HIGH : LOW);
    delayMicroseconds(5); // DIR setup time
    for (uint16_t i = 0; i < steps; i++)
    {
        digitalWrite(PIN_X_STEP, HIGH);
        delayMicroseconds(STEP_PULSE_US);
        digitalWrite(PIN_X_STEP, LOW);
        delayMicroseconds(STEP_DELAY_US);
    }
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
    digitalWrite(PIN_X_STEP, LOW);
    digitalWrite(PIN_X_DIR, LOW);
    digitalWrite(PIN_ENABLE, HIGH); // disable drivers initially

    Serial.println(F("============================================"));
    Serial.println(F("  TC1 – X-Axis Movement Test"));
    Serial.println(F("============================================"));
    Serial.println(F("Tests whether the X stepper (carriage) moves"));
    Serial.println(F("correctly in both directions."));

    // ── Step 1: operator setup ──────────────────────────────────────────────
    waitForEnter("Place the carriage roughly in the CENTRE of the X rail, "
                 "so it has room to move ~5 mm in each direction.");

    Serial.println(F("\n[TC1] Enabling stepper drivers..."));
    digitalWrite(PIN_ENABLE, LOW); // enable
    delay(100);

    // ── Step 2: move RIGHT ──────────────────────────────────────────────────
    Serial.print(F("\n[TC1] Moving X axis RIGHT (DIR=HIGH), "));
    Serial.print(STEPS_PER_MOVE);
    Serial.println(F(" steps (~5 mm)..."));
    moveSteps(STEPS_PER_MOVE, HIGH);
    Serial.println(F("[TC1] Done."));

    bool rightOk = askYesNo("Did the CARRIAGE (X axis) move to the RIGHT?");

    // ── Step 3: move LEFT ───────────────────────────────────────────────────
    Serial.print(F("\n[TC1] Moving X axis LEFT (DIR=LOW), "));
    Serial.print(STEPS_PER_MOVE * 2);
    Serial.println(F(" steps (~10 mm, past centre)..."));
    moveSteps(STEPS_PER_MOVE * 2, LOW);
    Serial.println(F("[TC1] Done."));

    bool leftOk = askYesNo("Did the CARRIAGE (X axis) move to the LEFT?");

    // ── Result ──────────────────────────────────────────────────────────────
    digitalWrite(PIN_ENABLE, HIGH); // disable drivers

    Serial.println(F("\n============================================"));
    Serial.println(F("  TC1 RESULT"));
    Serial.println(F("============================================"));
    Serial.print(F("  Move RIGHT  (DIR=HIGH): "));
    Serial.println(rightOk ? F("PASS") : F("FAIL  <-- check DEFAULT_DIRECTION_INVERT_MASK in config.h"));
    Serial.print(F("  Move LEFT   (DIR=LOW) : "));
    Serial.println(leftOk ? F("PASS") : F("FAIL  <-- check DEFAULT_DIRECTION_INVERT_MASK in config.h"));

    if (rightOk && leftOk)
    {
        Serial.println(F("\n  Overall: PASS"));
    }
    else
    {
        Serial.println(F("\n  Overall: FAIL"));
        Serial.println(F("  Hint: if both directions are swapped, toggle bit 0"));
        Serial.println(F("        of DEFAULT_DIRECTION_INVERT_MASK in config.h."));
        Serial.println(F("  Hint: if the wrong motor moved, check motor wiring"));
        Serial.println(F("        on the CNC Shield (X vs Y slot)."));
    }
    Serial.println(F("============================================"));
}

void loop() {}
