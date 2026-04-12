/*
  TC3 – Y-Axis Movement Test
  ==========================
  Standalone Arduino sketch – NO GRBL required.
  Flash with:  pio run -e tc3_y_axis -t upload

  Purpose
  -------
  Drives the Y stepper (paper feed) in both directions so the operator
  can verify:
    - The correct motor moves  (Y = paper feed, not the carriage)
    - Paper is pulled IN  when driving one direction
    - Paper is pushed OUT when driving the other direction

  Pins (CNC Shield v3 on Arduino Uno)
  ------------------------------------
    D3  – Y_STEP   (Y_STEP_BIT in cpu_map.h)
    D6  – Y_DIR    (Y_DIRECTION_BIT in cpu_map.h)
    D8  – ENABLE   (STEPPERS_DISABLE_BIT in cpu_map.h, active LOW)

  Note
  ----
  The Y axis has no endstops in this design, so this test is purely
  operator-confirmed.
*/

#include <Arduino.h>
#include "../plotter_pins.h" // pin numbers derived from GRBL cpu_map.h

// ── Motion parameters ──────────────────────────────────────────────────────
// 5 steps/mm @ full step (no MS jumpers) → 100 steps = 20 mm (enough to see clear paper movement)
static constexpr uint16_t STEPS_PER_MOVE = 100;
static constexpr uint16_t STEP_DELAY_US = 500;
static constexpr uint8_t STEP_PULSE_US = 10;

// ── Helpers ────────────────────────────────────────────────────────────────
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
    digitalWrite(PIN_Y_DIR, dirHigh ? HIGH : LOW);
    delayMicroseconds(5);
    for (uint16_t i = 0; i < steps; i++)
    {
        digitalWrite(PIN_Y_STEP, HIGH);
        delayMicroseconds(STEP_PULSE_US);
        digitalWrite(PIN_Y_STEP, LOW);
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

    pinMode(PIN_Y_STEP, OUTPUT);
    pinMode(PIN_Y_DIR, OUTPUT);
    pinMode(PIN_ENABLE, OUTPUT);
    digitalWrite(PIN_Y_STEP, LOW);
    digitalWrite(PIN_Y_DIR, LOW);
    digitalWrite(PIN_ENABLE, HIGH);

    Serial.println(F("============================================"));
    Serial.println(F("  TC3 – Y-Axis Movement Test"));
    Serial.println(F("============================================"));
    Serial.println(F("Tests whether the Y stepper (paper feed) moves"));
    Serial.println(F("correctly in both directions."));

    waitForEnter("Insert a sheet of paper into the paper bail so the "
                 "feed rollers can grip it.  Make sure ~5 cm of paper "
                 "protrudes at the back so you can see movement.");

    Serial.println(F("\n[TC3] Enabling stepper drivers..."));
    digitalWrite(PIN_ENABLE, LOW);
    delay(100);

    // ── Feed IN (DIR=HIGH) ──────────────────────────────────────────────────
    Serial.print(F("\n[TC3] Driving Y axis IN direction (DIR=HIGH), "));
    Serial.print(STEPS_PER_MOVE);
    Serial.println(F(" steps (~20 mm)..."));
    moveSteps(STEPS_PER_MOVE, HIGH);
    Serial.println(F("[TC3] Done."));

    bool inOk = askYesNo("Was the paper pulled INTO the plotter (feed-in)?");

    // ── Feed OUT (DIR=LOW) ──────────────────────────────────────────────────
    Serial.print(F("\n[TC3] Driving Y axis OUT direction (DIR=LOW), "));
    Serial.print(STEPS_PER_MOVE);
    Serial.println(F(" steps (~20 mm, back to start)..."));
    moveSteps(STEPS_PER_MOVE, LOW);
    Serial.println(F("[TC3] Done."));

    bool outOk = askYesNo("Was the paper pushed OUT / ejected from the plotter?");

    // ── Result ──────────────────────────────────────────────────────────────
    digitalWrite(PIN_ENABLE, HIGH);

    Serial.println(F("\n============================================"));
    Serial.println(F("  TC3 RESULT"));
    Serial.println(F("============================================"));
    Serial.print(F("  Paper feed IN  (DIR=HIGH): "));
    Serial.println(inOk ? F("PASS") : F("FAIL  <-- check DEFAULT_DIRECTION_INVERT_MASK bit 1"));
    Serial.print(F("  Paper feed OUT (DIR=LOW) : "));
    Serial.println(outOk ? F("PASS") : F("FAIL  <-- check DEFAULT_DIRECTION_INVERT_MASK bit 1"));

    bool allPass = inOk && outOk;
    Serial.println(allPass ? F("\n  Overall: PASS") : F("\n  Overall: FAIL"));

    if (!allPass)
    {
        Serial.println(F("\n  Hints:"));
        Serial.println(F("  - If directions are swapped, toggle bit 1 of"));
        Serial.println(F("    DEFAULT_DIRECTION_INVERT_MASK in config.h."));
        Serial.println(F("  - If the carriage moved instead: X and Y motor"));
        Serial.println(F("    cables are swapped on the CNC Shield."));
        Serial.println(F("  - If motor makes noise but paper doesn't move:"));
        Serial.println(F("    check that the feed roller is properly tensioned."));
    }
    Serial.println(F("============================================"));
}

void loop() {}
