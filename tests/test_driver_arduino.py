from __future__ import annotations

import pytest

from drivers import driver_arduino


class FakeSerial:
    instances: list["FakeSerial"] = []

    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.close_called = False
        FakeSerial.instances.append(self)

    def setDTR(self, value):
        pass

    def setRTS(self, value):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        self.close_called = True
        self.is_open = False


@pytest.fixture(autouse=True)
def reset_shared_serial(monkeypatch):
    FakeSerial.instances.clear()
    driver_arduino._shared_serial = None
    driver_arduino._shared_len_mode = 2
    monkeypatch.setattr(
        driver_arduino,
        "find_serial_port",
        lambda _vid, _pid: [("/dev/ttyACM1", "Arduino Due", "USB VID:PID=2341:003E")],
    )
    monkeypatch.setattr(driver_arduino, "Serial", FakeSerial)
    monkeypatch.setattr(driver_arduino.time, "sleep", lambda _seconds: None)
    yield
    if driver_arduino._shared_serial is not None:
        driver_arduino._shared_serial.close()
    driver_arduino._shared_serial = None
    driver_arduino._shared_len_mode = 2


def test_probe_failure_closes_opened_serial(monkeypatch):
    monkeypatch.setattr(driver_arduino.DriverArduino, "_simple_probe", lambda self: False)

    with pytest.raises(RuntimeError, match="did not answer the EOL binary protocol probe"):
        driver_arduino.DriverArduino()

    assert FakeSerial.instances
    assert FakeSerial.instances[0].close_called is True
    assert driver_arduino._shared_serial is None


def test_shared_serial_reuses_detected_length_mode(monkeypatch):
    def fake_probe(self):
        self._len_mode = 1
        return True

    monkeypatch.setattr(driver_arduino.DriverArduino, "_simple_probe", fake_probe)

    first = driver_arduino.DriverArduino()
    second = driver_arduino.DriverArduino()

    assert second.arduino is first.arduino
    assert second._len_mode == 1
