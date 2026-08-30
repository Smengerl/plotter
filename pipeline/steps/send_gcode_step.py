"""
pipeline/steps/send_gcode_step.py - GRBL transmission via pygrbl_streamer

Uses the ``pygrbl_streamer`` library (GrblStreamer) for
communication with GRBL firmware.

Advantages over manual pyserial implementation:
  - Intelligent buffer management (127-byte GRBL limit)
  - Automatic alarm recovery ($X)
  - Progress callbacks
  - Disconnect detection

Installation:
  pip install git+https://github.com/offerrall/PyGrbl_Streamer.git

Data transport via ImageContext
--------------------------------
Reads   ctx.intermediates["gcode_lines"] - List of GCode lines
Writes  nothing - pure side effect (serial port / dry-run log)
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from pipeline.core.base import ImageContext, PipelineStep
# filter_gcode logically lives in gcode_gen_step; re-exported for backward compatibility
from pipeline.steps.gcode_gen_step import filter_gcode as _filter_gcode  # noqa: F401

logger = logging.getLogger(__name__)

_INSTALL_HINT = (
    "pygrbl_streamer is not installed.\n"
    "Install it with:\n"
    "  pip install git+https://github.com/offerrall/PyGrbl_Streamer.git"
)


class SendGcodeStep(PipelineStep):
    """
    GRBL transmission step via pygrbl_streamer - GCode lines → serial port.

    Pure side effect: writes nothing back to ctx.

    How it works:
      - GCode lines are written to a temporary file
      - pygrbl_streamer opens the port, initializes GRBL, and sends
        the file with intelligent buffer management (127-byte limit)
      - Progress is output via logger

    Success / failure
    -----------------
    ``pygrbl_streamer`` never raises on a GRBL ``error:``/``ALARM:`` — it
    logs them and (for ALARM) auto-sends ``$X`` and continues. This step
    watches those callbacks and **raises ``RuntimeError`` after streaming**
    if any alarm / error / disconnect occurred, or if GRBL is not back in
    ``Idle`` afterwards. The runner then aborts and the failure propagates
    to the CLI / GUI like any other step error.

    config keys                 Default                   Corresponds to CLI flag
    ---------------------------------------------------------------------------
    port                        "/dev/tty.usbmodem1101"   --port
    baud                        115200                     --baud
    dry_run                     False                      --dry-run
    completion_timeout          300                        (internal, seconds)
    """

    name = "Send G-code to plotter"

    def requires(self) -> list[str]:
        return ["intermediates.gcode_lines"]

    def process(self, ctx: ImageContext) -> ImageContext:
        c = self.config
        port: str = str(c.get("port", "/dev/tty.usbmodem1101"))
        baud: int = int(c.get("baud", 115200))
        dry_run: bool = bool(c.get("dry_run", False))
        completion_timeout: int = int(c.get("completion_timeout", 300))
        logger.info("SendGCodeStep — port=%s, baud=%d, dry_run=%s", port, baud, dry_run)

        gcode_lines: list[str] = ctx.intermediates["gcode_lines"]
        logger.info("GCode lines to send: %d", len(gcode_lines))

        if dry_run:
            logger.info("[DRY-RUN] No port opened. Following lines would be sent:")
            for line in gcode_lines:
                logger.info("  > %s", line)
            return ctx

        try:
            from pygrbl_streamer import GrblStreamer  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(_INSTALL_HINT) from exc

        # Write GCode to temporary file - GrblStreamer expects a file path
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gcode", delete=False, encoding="ascii"
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write("\n".join(gcode_lines))

        logger.info("Opening serial port %s @ %d baud …", port, baud)

        alarms: list[str] = []
        errors: list[str] = []
        disconnects: list[str] = []

        class _LoggingStreamer(GrblStreamer):
            """GrblStreamer subclass: log callbacks and record problems."""

            def progress_callback(self, percent: int, command: str) -> None:
                logger.info("[GRBL] Progress: %d%%  — %s", percent, command)

            def alarm_callback(self, line: str) -> None:
                alarms.append(line)
                logger.error("[GRBL] ALARM (streamer auto-sent $X): %s", line)

            def error_callback(self, line: str) -> None:
                if "DEVICE_DISCONNECTED" in line:
                    disconnects.append(line)
                    logger.error("[GRBL] Connection to device lost: %s", line)
                else:
                    errors.append(line)
                    logger.error("[GRBL] Error: %s", line)

        streamer = _LoggingStreamer(port=port, baudrate=baud)
        try:
            streamer.open()
            logger.info("Connection opened - sending %d GCode lines …", len(gcode_lines))
            t0 = time.monotonic()
            streamer.send_file(str(tmp_path), completion_timeout=completion_timeout)
            elapsed = time.monotonic() - t0

            problems: list[str] = []
            if alarms:
                problems.append(f"{len(alarms)} GRBL alarm(s), last: {alarms[-1]!r}")
            if errors:
                problems.append(f"{len(errors)} GRBL error(s), last: {errors[-1]!r}")
            if disconnects:
                problems.append("device disconnected during streaming")
            if not problems and not _grbl_reached_idle(streamer):
                problems.append(
                    f"GRBL did not report Idle after streaming "
                    f"(completion_timeout={completion_timeout}s) — the plot may be incomplete"
                )

            if problems:
                raise RuntimeError("send_gcode failed: " + "; ".join(problems))

            logger.info("GCode sent successfully (%d lines, %.0fs).",
                        len(gcode_lines), elapsed)
        finally:
            streamer.close()
            tmp_path.unlink(missing_ok=True)

        return ctx


def _grbl_reached_idle(streamer: "object", tries: int = 3) -> bool:
    """Return True if a ``?`` status query shows GRBL back in ``Idle``.

    ``send_file`` already polls for ``Idle`` but silently gives up on
    timeout, so re-check here. A missing / unparseable response is treated
    as "not Idle" only after ``tries`` attempts.
    """
    for _ in range(tries):
        try:
            streamer.write_line("?")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return False
        for _ in range(6):
            line = streamer.read_line_blocking()  # type: ignore[attr-defined]
            if line is None:
                break
            if line.startswith("<"):
                return "Idle" in line
    return False

