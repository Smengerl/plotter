"""
pipeline/tests/test_send_gcode_step.py - Unit tests for SendGcodeStep

Focus: the success / failure signalling added on top of pygrbl_streamer
(which never raises on a GRBL error / alarm itself).
"""

from __future__ import annotations

import sys
import types

import pytest

from pipeline.core.base import ImageContext
from pipeline.steps.send_gcode_step import SendGcodeStep


def _ctx(lines: list[str]) -> ImageContext:
    return ImageContext(intermediates={"gcode_lines": lines})


# ---------------------------------------------------------------------------
# dry-run never touches a port
# ---------------------------------------------------------------------------

def test_dry_run_returns_ok_without_serial():
    step = SendGcodeStep({"dry_run": True})
    out = step.process(_ctx(["G21", "G90", "M5"]))
    assert out.intermediates["gcode_lines"] == ["G21", "G90", "M5"]


# ---------------------------------------------------------------------------
# fake pygrbl_streamer for the real path
# ---------------------------------------------------------------------------

class _FakeStreamerBase:
    """Stand-in for pygrbl_streamer.GrblStreamer.

    Subclasses (the step's _LoggingStreamer) override *_callback methods.
    `scenario` decides what send_file simulates.
    """

    scenario = "ok"
    idle_response = "<Idle|MPos:0.000,0.000,0.000|FS:0,0>"

    def __init__(self, port: str = "", baudrate: int = 115200) -> None:
        self.port = port

    def open(self) -> None:  # noqa: D401
        pass

    def close(self) -> None:
        pass

    def send_file(self, path: str, completion_timeout: int = 300) -> None:
        if self.scenario == "alarm":
            self.alarm_callback("ALARM:1")
        elif self.scenario == "error":
            self.error_callback("error:9")
        elif self.scenario == "disconnect":
            self.error_callback("DEVICE_DISCONNECTED")

    def write_line(self, line: str) -> None:
        pass

    def read_line_blocking(self):
        return self.idle_response


@pytest.fixture
def fake_streamer(monkeypatch):
    """Install a fake `pygrbl_streamer` module and return its base class."""
    _FakeStreamerBase.scenario = "ok"
    _FakeStreamerBase.idle_response = "<Idle|MPos:0.000,0.000,0.000|FS:0,0>"
    mod = types.ModuleType("pygrbl_streamer")
    mod.GrblStreamer = _FakeStreamerBase
    monkeypatch.setitem(sys.modules, "pygrbl_streamer", mod)
    return _FakeStreamerBase


def test_success_when_grbl_reaches_idle(fake_streamer):
    fake_streamer.scenario = "ok"
    SendGcodeStep({"port": "x"}).process(_ctx(["G21", "M5"]))  # no raise


@pytest.mark.parametrize("scenario", ["alarm", "error", "disconnect"])
def test_raises_on_grbl_problem(fake_streamer, scenario):
    fake_streamer.scenario = scenario
    with pytest.raises(RuntimeError, match="send_gcode failed"):
        SendGcodeStep({"port": "x"}).process(_ctx(["G21", "M5"]))


def test_raises_when_not_idle_afterwards(fake_streamer):
    # send_file runs clean, but the ? status query never shows Idle
    fake_streamer.idle_response = "<Run|MPos:1.0,2.0,3.0>"
    with pytest.raises(RuntimeError, match="did not report Idle"):
        SendGcodeStep({"port": "x"}).process(_ctx(["G21", "M5"]))
