#!/usr/bin/env python3
"""Interactive helper to set recommended GRBL EEPROM settings.

This script connects to a GRBL controller over a serial port and can
optionally apply a list of recommended $-settings (EEPROM) used by the
plotter project. It is interactive by default and asks for confirmation
before writing each value. Use --yes to apply all settings without prompts.

Requirements:
  pip install pyserial

Usage example:
  python3 firmware/tools/set_grbl_eeprom.py --port /dev/tty.usbmodem14101
  python3 firmware/tools/set_grbl_eeprom.py --port /dev/ttyUSB0 --baud 115200 --yes

The script prints the current `$$` settings, shows the planned changes
and applies them one-by-one, then re-prints `$$` to verify the result.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Dict

try:
    import serial
except Exception as exc:  # pragma: no cover - runtime dependency
    print("Missing dependency: pyserial. Install with: pip install pyserial")
    raise


FALLBACK_DEFAULTS: Dict[str, str] = {
    "$100": "5",     # X steps/mm
    "$101": "5",     # Y steps/mm
    "$110": "3000",  # X max rate (mm/min)
    "$111": "3000",  # Y max rate (mm/min)
    "$120": "200",   # X acceleration (mm/s^2)
    "$121": "200",   # Y acceleration (mm/s^2)
    "$130": "220",   # X max travel (mm)
    "$131": "300",   # Y max travel (mm)
    "$20": "0",      # Soft limits OFF
    "$21": "0",      # Hard limits OFF
    "$22": "1",      # Homing cycle ON
    "$23": "0",      # Homing dir: toward MIN
    "$24": "50",     # Homing feed rate (mm/min)
    "$25": "800",    # Homing seek rate (mm/min)
    "$27": "5",      # Homing pull-off (mm)
    # Spindle settings: ensure M3 S1000 works with this mapping
    "$30": "1000",   # max spindle speed (must be >=1000 if profile uses M3 S1000)
    "$31": "0",      # min spindle speed
}


def parse_config_h(path: str) -> dict[str, str]:
    """Parse firmware/src/config.h for DEFAULT_* values and map them to $ settings.

    Returns a dict mapping GRBL $-keys (as strings) to values (as strings).
    If parsing fails, returns an empty dict.
    """
    import re
    mapping = {
        'DEFAULT_X_STEPS_PER_MM': '$100',
        'DEFAULT_Y_STEPS_PER_MM': '$101',
        'DEFAULT_X_MAX_RATE': '$110',
        'DEFAULT_Y_MAX_RATE': '$111',
        'DEFAULT_X_ACCELERATION': '$120',
        'DEFAULT_Y_ACCELERATION': '$121',
        'DEFAULT_X_MAX_TRAVEL': '$130',
        'DEFAULT_Y_MAX_TRAVEL': '$131',
        'DEFAULT_SOFT_LIMIT_ENABLE': '$20',
        'DEFAULT_HARD_LIMIT_ENABLE': '$21',
        'DEFAULT_HOMING_ENABLE': '$22',
        'DEFAULT_HOMING_DIR_MASK': '$23',
        'DEFAULT_HOMING_FEED_RATE': '$24',
        'DEFAULT_HOMING_SEEK_RATE': '$25',
        'DEFAULT_HOMING_PULLOFF': '$27',
        'DEFAULT_SPINDLE_RPM_MAX': '$30',
        'DEFAULT_SPINDLE_RPM_MIN': '$31',
    }

    # First try to use the C preprocessor (gcc/clang/cpp) to dump macros.
    import shutil, subprocess, os

    def try_cpp_extract(p: str) -> dict:
        exe = None
        for candidate in ("gcc", "clang", "cpp"):
            exe = shutil.which(candidate)
            if exe:
                break
        if not exe:
            return {}
        # Build include paths relative to repo root (script is in firmware/tools)
        script_dir = os.path.dirname(__file__)
        repo_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
        incs = [os.path.join(repo_root, 'firmware', 'src'), os.path.join(repo_root, 'grbl'), os.path.join(repo_root, 'grbl', 'src')]
        cmd = [exe, '-E', '-dM']
        for inc in incs:
            cmd += ['-I', inc]
        cmd.append(p)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            return {}
        if proc.returncode != 0:
            return {}
        out = proc.stdout
        defines_local = {}
        for line in out.splitlines():
            line = line.strip()
            m = re.match(r"#define\s+(DEFAULT_[A-Z0-9_]+)\s+(.*)$", line)
            if m:
                name = m.group(1)
                val = m.group(2).strip()
                # strip comments
                val = re.sub(r"//.*$", "", val).strip()
                defines_local[name] = val
        return defines_local

    defines = try_cpp_extract(path)
    if not defines:
        # Fallback: simple file parse (best-effort)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            return {}
        for m in re.finditer(r"#define\s+(DEFAULT_[A-Z0-9_]+)\s+(.+)", text):
            name = m.group(1)
            val = m.group(2).strip()
            # strip trailing comments
            val = re.sub(r"//.*$", "", val).strip()
            val = re.sub(r"/\*.*?\*/", "", val, flags=re.S).strip()
            defines[name] = val

    results: dict[str, str] = {}
    for define_name, dollar in mapping.items():
        raw = defines.get(define_name)
        if raw is None:
            continue
        # Attempt to evaluate simple numeric expressions safely
        # allow only digits, operators, parentheses and dots and spaces
        safe = re.sub(r"[^0-9\.\+\-\*/() ]", "", raw)
        try:
            # If safe string is empty fallback to raw extraction of first number
            if safe:
                val = eval(safe, { })  # safe contains only numeric chars/operators
            else:
                # try to extract a float from raw
                nm = re.search(r"([-+]?[0-9]*\.?[0-9]+)", raw)
                val = float(nm.group(1)) if nm else None
        except Exception:
            val = None

        if val is None:
            continue

        # Special handling: config.h acceleration may be specified in mm/min^2
        # (e.g. 200.0 * 60.0 * 60.0). GRBL $120/$121 expect mm/s^2 (e.g. 200).
        if define_name in ('DEFAULT_X_ACCELERATION', 'DEFAULT_Y_ACCELERATION'):
            # If value is large (>10000), assume mm/min^2 and convert
            try:
                fval = float(val)
                if fval > 10000:
                    fval = fval / 3600.0
            except Exception:
                fval = val
            # format as integer if integral
            results[dollar] = str(int(fval) if float(fval).is_integer() else f"{fval:g}")
            continue

        # format integers without trailing .0
        try:
            fv = float(val)
            results[dollar] = str(int(fv) if fv.is_integer() else f"{fv:g}")
        except Exception:
            # fallback: use raw text
            results[dollar] = raw

    return results


def open_serial(port: str, baud: int, timeout: float = 1.0) -> serial.Serial:
    """Open and return a configured serial.Serial object."""
    s = serial.Serial(port=port, baudrate=baud, timeout=timeout)
    # Give GRBL time to reset/banner
    time.sleep(2.0)
    # flush any initial data
    s.reset_input_buffer()
    s.reset_output_buffer()
    return s


def send_line(ser: serial.Serial, line: str, read_timeout: float = 0.5) -> str:
    """Send a line to GRBL and return the collected reply lines as a string."""
    if not line.endswith("\n"):
        line = line + "\n"
    ser.write(line.encode("ascii"))
    ser.flush()
    # Read responses for a short period
    end = time.time() + read_timeout
    lines = []
    while time.time() < end:
        try:
            raw = ser.readline()
        except Exception:
            break
        if not raw:
            continue
        try:
            text = raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if text:
            lines.append(text)
        # GRBL replies with 'ok' or error lines; stop early on ok
        if text.lower().startswith("ok") or text.lower().startswith("error"):
            break
    return "\n".join(lines)


def print_settings(ser: serial.Serial) -> None:
    """Request and print `$$` settings from GRBL."""
    print("\n--- Current GRBL settings ($$) ---")
    reply = send_line(ser, "$$", read_timeout=1.0)
    print(reply)
    print("----------------------------------\n")


def apply_settings(ser: serial.Serial, settings: Dict[str, str], auto: bool = False) -> None:
    """Apply the provided key=value settings to GRBL (interactive unless auto=True)."""
    print("Planned settings to apply:")
    for k, v in settings.items():
        print(f"  {k} = {v}")

    if not auto:
        ans = input("Apply these settings? (y/N): ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborting — no changes applied.")
            return

    for k, v in settings.items():
        cmd = f"{k}={v}"
        print(f"Setting {cmd} ...", end=" ")
        resp = send_line(ser, cmd, read_timeout=1.0)
        if resp:
            print("->", resp.replace("\n", " | "))
        else:
            print("(no reply)")
        time.sleep(0.1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Set recommended GRBL EEPROM settings for the plotter.")
    p.add_argument("--port", required=True, help="Serial port (e.g. /dev/tty.usbmodemXXXX)")
    p.add_argument("--baud", type=int, default=115200, help="Serial baud rate (default: 115200)")
    p.add_argument("--config", default="firmware/src/config.h", help="Path to firmware config.h to parse defaults from")
    p.add_argument("--yes", action="store_true", help="Apply all settings without confirmation")
    p.add_argument("--dry-run", action="store_true", help="Show planned settings without writing them to the device")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ser = open_serial(args.port, args.baud, timeout=1.0)
    except Exception as exc:
        print(f"Failed to open serial port {args.port}: {exc}")
        return 2

    try:
        # Print banner/welcome lines
        print_settings(ser)

        # Build settings from firmware config.h if possible
        parsed = parse_config_h(args.config)
        # Merge: parsed values take precedence, fall back to FALLBACK_DEFAULTS
        settings = FALLBACK_DEFAULTS.copy()
        settings.update(parsed)

        # Show planned changes. If --dry-run is set, only print the planned settings
        # and do not write to the device. Otherwise, apply (interactive unless --yes).
        if getattr(args, 'dry_run', False):
            print("Dry run: planned settings (no writes):")
            for k, v in settings.items():
                print(f"  {k} = {v}")
        else:
            apply_settings(ser, settings, auto=args.yes)

        # Final verification
        print_settings(ser)

    finally:
        try:
            ser.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
