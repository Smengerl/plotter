# GRBL settings & calibration

Every `$` setting below lives in the Arduino's EEPROM. Set one with
`$<n>=<value>`, list them all with `$$`. They survive re-flashing the
firmware; a fresh chip starts from GRBL's generic defaults, so run the
[first-run checklist](README.md#key-grbl-settings-first-run-checklist) once.

Back up your tuned values by saving the `$$` output somewhere.

Compile-time options (`HOMING_CYCLE_0`, `VARIABLE_SPINDLE`, CPU map) are **not**
`$` settings — they live in [`src/config.h`](src/config.h).

---

## Full settings table

Values in the "Plotter" column are this machine's targets. `—` = leave at the
GRBL default.

| `$n` | Meaning | Unit | Plotter | Notes |
|-----|---------|------|---------|-------|
| `$0` | Step pulse time | µs | 10 | |
| `$1` | Step idle delay | ms | 25 | 255 = never disable (holds torque) |
| `$2` | Step port invert mask | bitmask | 0 | bit 0/1/2 = X/Y/Z |
| `$3` | Direction port invert mask | bitmask | 0 | flip a bit if an axis runs backwards (see calibration) |
| `$4` | Step enable invert | bool | 0 | A4988: 0 is correct |
| `$5` | Limit pins invert | bool | **?** | **UNVERIFIED** — `$5=1`: pin HIGH = triggered; `$5=0`: LOW = triggered. Measure your optical modules. |
| `$6` | Probe pin invert | bool | 0 | no probe |
| `$10` | Status report mask | bitmask | 1 | 1 = machine position |
| `$11` | Junction deviation | mm | 0.01 | |
| `$12` | Arc tolerance | mm | 0.002 | |
| `$13` | Report in inches | bool | 0 | metric |
| `$20` | Soft limits | bool | 0 → 1 | enable **only after `$130` is taught** |
| `$21` | Hard limits | bool | 0 → 1 | enable after the endstop wiring is verified (TC6-G/TC7-G) |
| `$22` | Homing cycle | bool | 1 | |
| `$23` | Homing dir invert mask | bitmask | 0 | X homes toward MIN |
| `$24` | Homing feed rate | mm/min | 50 | slow locate pass |
| `$25` | Homing seek rate | mm/min | 800 | fast search pass |
| `$26` | Homing debounce | ms | 250 | |
| `$27` | Homing pull-off | mm | 5 | must clear the switch |
| `$30` | Max spindle speed | "RPM" | 1000 | maps `S1000` → 100 % solenoid PWM |
| `$31` | Min spindle speed | "RPM" | 0 | |
| `$32` | Laser mode | bool | 0 | solenoid is not a laser |
| `$100` | X steps/mm | steps/mm | 5 | 2GT 20T pulley, A4988 full-step (see calibration) |
| `$101` | Y steps/mm | steps/mm | 5 | paper feed roller — measure and adjust |
| `$102` | Z steps/mm | steps/mm | — | Z disabled |
| `$110` | X max rate | mm/min | 3000 | |
| `$111` | Y max rate | mm/min | 3000 | |
| `$112` | Z max rate | mm/min | — | |
| `$120` | X acceleration | mm/s² | 200 | raise cautiously (see calibration) |
| `$121` | Y acceleration | mm/s² | 200 | |
| `$122` | Z acceleration | mm/s² | — | |
| `$130` | X max travel | mm | **taught** | measure it — see below / testing.md TC5b-G |
| `$131` | Y max travel | mm | 300 | no endstop; only bounds soft limits |
| `$132` | Z max travel | mm | — | |

---

## Calibration

### Direction (`$3`)

Run TC1 (X) and TC3 (Y), or TC7-G / TC8-G under GRBL. If an axis moves the
wrong way, flip its bit in `$3`:

| `$3` | inverted |
|------|----------|
| 0 | none |
| 1 | X |
| 2 | Y |
| 3 | X and Y |

### Steps/mm (`$100` / `$101`)

The belt axis (X) is deterministic: `(200 steps/rev × microsteps) / (pulley
teeth × belt pitch)` = `(200 × 1) / (20 × 2)` = **5**. Verify it:

```gcode
G91
G1 X100 F1000     ; command 100 mm
G90
```

Measure the actual carriage travel `d`. Corrected value:
`$100_new = $100_old × 100 / d`. Repeat until it matches.

The **Y (paper feed) axis is not deterministic** — it depends on the roller
diameter and paper grip. Command `G1 Y100`, measure the paper advance, and
set `$101` the same way. Re-check with the paper you actually plot on.

### X-axis length (`$130`)

GRBL homes X against X_MIN only; X_MAX shares the pin. Measure the usable
length once and store it — full procedure in
[testing.md → TC5b-G](../testing.md#tc5b-g--teach-the-x-axis-length):

```gcode
$21=1                ; hard limits on, so X_MAX stops the jog
$H                   ; home X_MIN → X = 0
$J=G91 X20 F500      ; repeat until ALARM:1 (X_MAX)
?                    ; read MPos:X → usable length
$X
$130=<that minus ~3 mm>
$20=1                ; soft limits on
```

### Acceleration (`$120` / `$121`)

Start at 200 mm/s². Raise in ~100 mm/s² steps and run a fast move; if the
motor stalls or loses steps (drawing shifts), drop back one step. Higher
acceleration = faster plots but more vibration/ringing in the lines.

### Squaring / skew

If plotted rectangles come out as parallelograms, the X rail and the paper
feed are not perpendicular — that is mechanical, not a `$` setting. Check the
frame assembly and that the paper is fed straight.

### Solenoid (`$30` / `$31`)

`$30=1000` makes `S1000` = full PWM. The G-code profile
(`pipeline/configs/grbl_a4_pen.toml`) then uses `S1000` to pull the pen up
and `S350` to hold it — tune the hold value on the machine
(see [electronics.md → Solenoid pen lift](../electronics.md#solenoid-pen-lift)).
