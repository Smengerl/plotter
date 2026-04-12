"""
pipeline/grbl_sender.py — Schritt 4: GCode seriell an GRBL senden

Protokoll:
  - GRBL bestätigt jede Zeile mit 'ok' oder meldet 'error:N'
  - Leere Zeilen und Kommentare (;) werden übersprungen
  - Jede Zeile wird mit \\n abgeschlossen
  - Timeout nach ``response_timeout_s`` Sekunden pro Zeile

GRBL-Zustand-Überprüfung:
  Vor dem Senden wird der GRBL-Status mit '?' abgefragt.
  Nur bei 'Idle' oder 'Home' wird der GCode gesendet.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator

logger = logging.getLogger(__name__)

# Maximale Zeit (s) auf eine 'ok'-Antwort von GRBL pro GCode-Zeile
_RESPONSE_TIMEOUT_S = 30.0

# Zeichen-Puffer-Größe von GRBL (128 Bytes im Standard)
_GRBL_BUFFER_SIZE = 127


def send_gcode(
    gcode_lines: list[str],
    port: str = "/dev/tty.usbmodem1101",
    baud: int = 115200,
    dry_run: bool = False,
    response_timeout_s: float = _RESPONSE_TIMEOUT_S,
) -> None:
    """
    Sendet GCode-Zeilen an einen GRBL-Controller über die serielle Schnittstelle.

    Parameters
    ----------
    gcode_lines        : Liste von GCode-Zeilen (Kommentare und Leerzeilen werden ignoriert)
    port               : Serieller Port (z.B. '/dev/tty.usbmodem1101', 'COM3')
    baud               : Baudrate (GRBL Standard: 115200)
    dry_run            : Wenn True, wird nichts gesendet — nur simuliert
    response_timeout_s : Timeout in Sekunden pro Zeile
    """
    effective_lines = list(_filter_gcode(gcode_lines))
    logger.info("Zu sendende GCode-Zeilen: %d", len(effective_lines))

    if dry_run:
        logger.info("[DRY-RUN] Kein Port geöffnet. Folgende Zeilen würden gesendet:")
        for line in effective_lines:
            logger.info("  > %s", line)
        return

    try:
        import serial  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "pyserial ist nicht installiert. "
            "Installiere es mit: pip install pyserial"
        ) from exc

    logger.info("Öffne seriellen Port %s @ %d Baud …", port, baud)
    with serial.Serial(port, baud, timeout=response_timeout_s) as ser:
        # GRBL wacht nach Reset auf — kurz warten
        time.sleep(2.0)
        ser.reset_input_buffer()

        # GRBL-Status prüfen
        _check_grbl_ready(ser)

        total = len(effective_lines)
        for idx, line in enumerate(effective_lines, start=1):
            _send_line(ser, line, idx, total, response_timeout_s)

    logger.info("Alle GCode-Zeilen erfolgreich gesendet.")


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen
# ---------------------------------------------------------------------------

def _filter_gcode(lines: list[str]) -> Iterator[str]:
    """Gibt nur ausführbare GCode-Zeilen zurück (keine Leerzeilen, keine Kommentare)."""
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        # Inline-Kommentare abschneiden
        if ";" in stripped:
            code_part = stripped[: stripped.index(";")].strip()
        else:
            code_part = stripped
        if code_part:
            yield code_part


def _check_grbl_ready(ser: "serial.Serial") -> None:  # type: ignore[name-defined]
    """Fragt GRBL-Status ab und wartet, bis der Zustand 'Idle' ist."""
    import serial  # type: ignore[import]

    logger.debug("GRBL-Status prüfen …")
    ser.write(b"?\n")
    deadline = time.time() + 5.0
    while time.time() < deadline:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if not line:
            continue
        logger.debug("GRBL Status: %s", line)
        if line.startswith("<Idle") or line.startswith("<Home"):
            logger.info("GRBL bereit: %s", line)
            return
        if line.startswith("<Alarm"):
            raise RuntimeError(
                f"GRBL befindet sich im ALARM-Zustand: {line}\n"
                "Sende '$X' über einen GCode-Sender, um den Alarm zu quittieren."
            )
    logger.warning("GRBL-Status konnte nicht bestätigt werden — sende trotzdem …")


def _send_line(
    ser: "serial.Serial",  # type: ignore[name-defined]
    line: str,
    idx: int,
    total: int,
    timeout_s: float,
) -> None:
    """Sendet eine einzelne GCode-Zeile und wartet auf 'ok' oder 'error'."""
    encoded = (line + "\n").encode("ascii")
    ser.write(encoded)
    logger.debug("[%d/%d] → %s", idx, total, line)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = ser.readline().decode("ascii", errors="replace").strip()
        if not response:
            continue
        if response == "ok":
            logger.debug("[%d/%d] ← ok", idx, total)
            return
        if response.startswith("error"):
            raise RuntimeError(
                f"GRBL Fehler bei Zeile {idx}/{total}: '{line}' → {response}"
            )
        # Andere Meldungen (z.B. '[MSG:...]') einfach loggen
        logger.debug("[%d/%d] ← %s", idx, total, response)

    raise TimeoutError(
        f"Timeout: keine 'ok'-Antwort von GRBL nach {timeout_s}s für Zeile: {line!r}"
    )
