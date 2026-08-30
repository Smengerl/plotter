/*
  SPDX-License-Identifier: GPL-3.0-or-later
  Copyright (c) 2026 Simon Gerlach

  TC4 – Pen Lift (Solenoid) Test
  ================================
  Standalone Arduino sketch – NO GRBL required.
  Flash with:  pio run -e tc4_pen_lift -t upload

  Purpose
  -------
  Cycles the pen-lift solenoid 4 times to verify:
    - The solenoid actuates (audible click / visible movement)
    - The pen returns to the UP position when de-energised
    - The MOSFET circuit is wired correctly

  Timing
  ------
  Each cycle: 1 s ON  →  3 s OFF
  This gives the solenoid coil time to cool between activations and
  prevents overheating during testing.

  Pins (CNC Shield v3 on Arduino Uno)
  ------------------------------------
    D11 – Spindle PWM / solenoid MOSFET gate   (SPINDLE_PWM_BIT in cpu_map.h)

  Safety notes
  ------------
  - Do NOT run the solenoid ON continuously for more than ~2 s; the coil
    will overheat.  The 3 s cool-down between pulses is the minimum.
  - Ensure the flyback diode is installed across the solenoid coil before
    powering up (see electronics.md).
  - If the solenoid feels very hot after this test, increase SOLENOID_OFF_MS
    before re-running.
*/

#include <Arduino.h>
#include "../plotter_pins.h" // pin numbers derived from GRBL cpu_map.h

// ── Timing ─────────────────────────────────────────────────────────────────
static constexpr uint16_t SOLENOID_ON_MS = 1000;  // 1 s active
static constexpr uint16_t SOLENOID_OFF_MS = 3000; // 3 s cool-down
static constexpr uint8_t CYCLES = 4;

// ── Helpers ────────────────────────────────────────────────────────────────
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

// ── Setup / loop ──────────────────────────────────────────────────────────
void setup()
{
    Serial.begin(115200);
    while (!Serial)
    {
    }

    pinMode(PIN_SOLENOID, OUTPUT);
    digitalWrite(PIN_SOLENOID, LOW); // ensure solenoid is OFF at start

    Serial.println(F("============================================"));
    Serial.println(F("  TC4 – Pen Lift (Solenoid) Test"));
    Serial.println(F("============================================"));
    Serial.println(F("Cycles the pen-lift solenoid 4 times."));
    Serial.println(F("Timing per cycle: 1 s ON / 3 s OFF (cool-down)."));
    Serial.println(F(""));
    Serial.println(F("SAFETY: Make sure the flyback diode is installed"));
    Serial.println(F("        across the solenoid coil before continuing."));

    waitForEnter("Confirm flyback diode is installed and 12 V supply is ON. "
                 "Mount the pen carriage so you can observe the pen movement.");

    for (uint8_t cycle = 1; cycle <= CYCLES; cycle++)
    {
        Serial.println();
        Serial.print(F("[TC4] Cycle "));
        Serial.print(cycle);
        Serial.print(F(" / "));
        Serial.print(CYCLES);
        Serial.println(F(" -- Solenoid ON (pen UP)"));

        digitalWrite(PIN_SOLENOID, HIGH);
        delay(SOLENOID_ON_MS);

        Serial.println(F("[TC4] Solenoid OFF (pen DOWN / spring return)"));
        digitalWrite(PIN_SOLENOID, LOW);

        if (cycle < CYCLES)
        {
            Serial.print(F("[TC4] Cooling down for "));
            Serial.print(SOLENOID_OFF_MS / 1000);
            Serial.println(F(" s..."));
            delay(SOLENOID_OFF_MS);
        }
    }

    // Final safety off
    digitalWrite(PIN_SOLENOID, LOW);

    Serial.println(F("\n[TC4] Sequence complete. Solenoid is OFF."));

    bool actuated = askYesNo(
        "Did the solenoid actuate clearly on every cycle "
        "(click sound / visible pen movement UP)?");

    bool returnOk = askYesNo(
        "Did the pen return fully to the DOWN position after each cycle "
        "(spring return working)?");

    // ── Result ──────────────────────────────────────────────────────────────
    Serial.println(F("\n============================================"));
    Serial.println(F("  TC4 RESULT"));
    Serial.println(F("============================================"));
    Serial.print(F("  Solenoid actuated on all cycles : "));
    Serial.println(actuated ? F("PASS") : F("FAIL"));
    Serial.print(F("  Pen returns DOWN after each cycle : "));
    Serial.println(returnOk ? F("PASS") : F("FAIL"));

    bool allPass = actuated && returnOk;
    Serial.println(allPass ? F("\n  Overall: PASS") : F("\n  Overall: FAIL"));

    if (!allPass)
    {
        Serial.println(F("\n  Hints:"));
        if (!actuated)
        {
            Serial.println(F("  - No actuation: check MOSFET gate wiring to D11,"));
            Serial.println(F("    verify 12 V supply is present, check solenoid"));
            Serial.println(F("    continuity with a multimeter."));
            Serial.println(F("  - Weak actuation: solenoid may need more voltage or"));
            Serial.println(F("    the MOSFET Vgs threshold is too high (use logic-level FET)."));
        }
        if (!returnOk)
        {
            Serial.println(F("  - Pen not returning: check / replace the return spring."));
            Serial.println(F("    Make sure the solenoid slider moves freely."));
        }
    }
    Serial.println(F("============================================"));
}

void loop() {}
