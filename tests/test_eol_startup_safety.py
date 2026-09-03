from __future__ import annotations

from types import SimpleNamespace

import pytest

from io_helpers.find_device import find_serial_port
from utils.utils import error_prompt, safe_execute


def test_find_serial_port_returns_sortable_candidate_tuples(monkeypatch):
    ports = [
        SimpleNamespace(
            vid=0x2341,
            pid=0x003E,
            device="/dev/ttyACM1",
            description="Arduino Due",
            hwid="USB VID:PID=2341:003E",
        ),
        SimpleNamespace(
            vid=0x16D0,
            pid=0x117E,
            device="/dev/ttyACM0",
            description="CANable2",
            hwid="USB VID:PID=16D0:117E",
        ),
    ]
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: ports)

    candidates = find_serial_port(0x2341, 0x003E)

    assert candidates == [("/dev/ttyACM1", "Arduino Due", "USB VID:PID=2341:003E")]
    candidates.sort(key=lambda t: t[0])


def test_error_prompt_raises_immediately_when_noninteractive(monkeypatch):
    monkeypatch.setenv("ST_NONINTERACTIVE", "1")

    with pytest.raises(RuntimeError, match="boom"):
        error_prompt("boom")


def test_safe_execute_reraises_original_error_when_noninteractive(monkeypatch):
    monkeypatch.setenv("ST_NONINTERACTIVE", "1")

    with pytest.raises(ValueError, match="original"):
        safe_execute(lambda: (_ for _ in ()).throw(ValueError("original")))
