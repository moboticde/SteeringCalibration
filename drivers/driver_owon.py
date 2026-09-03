from __future__ import annotations

from dataclasses import dataclass
import glob
import os
from pathlib import Path
import select
import time

import serial
from serial import SerialException
import serial.tools.list_ports
import yaml


CONFIG_PATH = Path(__file__).resolve().parent.parent / "resources" / "config.yaml"
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT_S = 1.0
DEFAULT_VOLTAGE_V = 24.0
DEFAULT_CURRENT_A = 5.0
DEFAULT_OFF_SECONDS = 3.0
DEFAULT_ON_SETTLE_SECONDS = 3.0
OWON_USB_SERIAL_IDS = {
    (0x1A86, 0x7523),  # QinHeng CH340 used by the OWON SPE6053 USB serial port.
}


@dataclass(frozen=True)
class OwonPowerSupplyConfig:
    enabled: bool = True
    backend: str = "auto"
    port: str | None = None
    visa_resource: str | None = None
    vid: int | None = None
    pid: int | None = None
    baudrate: int = DEFAULT_BAUDRATE
    timeout_s: float = DEFAULT_TIMEOUT_S
    voltage_v: float = DEFAULT_VOLTAGE_V
    current_a: float = DEFAULT_CURRENT_A
    off_seconds: float = DEFAULT_OFF_SECONDS
    on_settle_seconds: float = DEFAULT_ON_SETTLE_SECONDS


def _parse_optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def load_owon_power_supply_config() -> OwonPowerSupplyConfig:
    data = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f) or {}

    section = data.get("power_supply", {}) or {}
    port = (
        os.environ.get("OWON_SPE6053_PORT")
        or section.get("serial_port")
        or section.get("port")
        or None
    )
    visa_resource = (
        os.environ.get("OWON_SPE6053_RESOURCE")
        or section.get("visa_resource")
        or section.get("resource")
        or None
    )
    return OwonPowerSupplyConfig(
        enabled=bool(section.get("enabled", True)),
        backend=str(section.get("backend", "auto")).lower(),
        port=port,
        visa_resource=visa_resource,
        vid=_parse_optional_int(section.get("VID", section.get("vid"))),
        pid=_parse_optional_int(section.get("PID", section.get("pid"))),
        baudrate=int(section.get("BITRATE", section.get("baudrate", DEFAULT_BAUDRATE))),
        timeout_s=float(section.get("timeout_s", DEFAULT_TIMEOUT_S)),
        voltage_v=float(section.get("voltage_v", DEFAULT_VOLTAGE_V)),
        current_a=float(section.get("current_a", DEFAULT_CURRENT_A)),
        off_seconds=float(section.get("power_cycle_off_seconds", DEFAULT_OFF_SECONDS)),
        on_settle_seconds=float(section.get("power_on_settle_seconds", DEFAULT_ON_SETTLE_SECONDS)),
    )


class OwonSPE6053:
    """Minimal serial SCPI driver for an OWON SPE6053 bench supply."""

    def __init__(self, config: OwonPowerSupplyConfig | None = None) -> None:
        self.config = config or load_owon_power_supply_config()
        self.backend = self._resolve_backend()
        self.resource_name = self._resolve_resource_name()
        self.serial = None
        self.visa_resource = None
        self.visa_manager = None
        self.usbtmc_fd = None

        if self.backend == "visa":
            self._open_visa()
        elif self.backend == "usbtmc":
            self._open_usbtmc()
        else:
            self._open_serial()

    def __enter__(self) -> "OwonSPE6053":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def close(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
        if self.visa_resource is not None:
            self.visa_resource.close()
        if self.visa_manager is not None:
            self.visa_manager.close()
        if self.usbtmc_fd is not None:
            os.close(self.usbtmc_fd)
            self.usbtmc_fd = None

    def write(self, command: str, *, log: bool = True) -> None:
        if log:
            print(f"[DEBUG] OWON <- {command}")
        if self.backend == "visa":
            self.visa_resource.write(command)
        elif self.backend == "usbtmc":
            os.write(self.usbtmc_fd, f"{command}\n".encode("ascii"))
        else:
            self.serial.write(f"{command}\r\n".encode("ascii"))
            self.serial.flush()
        time.sleep(0.05)

    def write_batch(self, description: str, commands) -> None:
        commands = tuple(commands)
        print(f"[DEBUG] OWON <- {description} ({len(commands)} command variants)")
        for command in commands:
            self.write(command, log=False)

    def query(self, command: str) -> str:
        if self.backend == "visa":
            print(f"[DEBUG] OWON ?  {command}")
            return str(self.visa_resource.query(command)).strip()
        if self.backend == "usbtmc":
            print(f"[DEBUG] OWON ?  {command}")
            os.write(self.usbtmc_fd, f"{command}\n".encode("ascii"))
            ready, _write_ready, _errors = select.select(
                [self.usbtmc_fd],
                [],
                [self.usbtmc_fd],
                self.config.timeout_s,
            )
            if not ready:
                return ""
            return os.read(self.usbtmc_fd, 4096).decode(errors="replace").strip()
        self.serial.reset_input_buffer()
        self.write(command)
        return self.serial.readline().decode(errors="replace").strip()

    def identify(self) -> str:
        try:
            return self.query("*IDN?")
        except Exception:
            return ""

    def configure_output(self, voltage_v: float, current_a: float) -> None:
        self.write_batch(
            f"configure output {voltage_v:.3f} V, {current_a:.3f} A",
            (
                f"VOLT {voltage_v:.3f}",
                f"VOLTage {voltage_v:.3f}",
                f":VOLTage {voltage_v:.3f}",
                f"CURR {current_a:.3f}",
                f"CURRent {current_a:.3f}",
                f":CURRent {current_a:.3f}",
                f"VSET1:{voltage_v:.3f}",
                f"ISET1:{current_a:.3f}",
            ),
        )

    def set_output(self, enabled: bool) -> None:
        state = "ON" if enabled else "OFF"
        numeric_state = "1" if enabled else "0"
        self.write_batch(
            f"set output {state}",
            (
                f"OUT{numeric_state}",
                f"OUTP {state}",
                f"OUTPut {state}",
                f":OUTPut {state}",
                f"OUTP:STAT {state}",
                f"OUTP:STAT {numeric_state}",
                f":OUTPut:STATe {state}",
                f":OUTPut:STATe {numeric_state}",
            ),
        )

    def power_cycle(
        self,
        off_seconds: float | None = None,
        voltage_v: float | None = None,
        current_a: float | None = None,
        on_settle_seconds: float | None = None,
    ) -> None:
        voltage = self.config.voltage_v if voltage_v is None else float(voltage_v)
        current = self.config.current_a if current_a is None else float(current_a)
        off_delay = self.config.off_seconds if off_seconds is None else float(off_seconds)
        on_delay = (
            self.config.on_settle_seconds
            if on_settle_seconds is None
            else float(on_settle_seconds)
        )

        self.configure_output(voltage, current)
        self.set_output(False)
        time.sleep(max(0.0, off_delay))
        try:
            self.configure_output(voltage, current)
            self.set_output(True)
        finally:
            if on_delay > 0:
                time.sleep(on_delay)

    def _resolve_backend(self) -> str:
        if self.config.backend in {"serial", "visa", "usbtmc"}:
            return self.config.backend
        if self.config.visa_resource:
            return "visa"
        if self.config.port and str(self.config.port).startswith("/dev/usbtmc"):
            return "usbtmc"
        if glob.glob("/dev/usbtmc*"):
            return "usbtmc"
        return "serial"

    def _resolve_resource_name(self) -> str:
        if self.backend == "visa":
            return self.config.visa_resource or self._find_visa_resource()
        if self.backend == "usbtmc":
            return self.config.port or self._find_usbtmc_device()
        return self.config.port or self._find_port()

    def _open_serial(self) -> None:
        print(
            "[INFO] Opening OWON SPE6053 serial connection: "
            f"port={self.resource_name} baudrate={self.config.baudrate}"
        )
        try:
            self.serial = serial.Serial(
                self.resource_name,
                self.config.baudrate,
                timeout=self.config.timeout_s,
                write_timeout=self.config.timeout_s,
            )
        except (PermissionError, SerialException) as exc:
            if getattr(exc, "errno", None) == 13 or "Permission denied" in str(exc):
                raise RuntimeError(
                    f"Permission denied opening {self.resource_name}. "
                    "Add the current user to the serial device group, usually with "
                    "`sudo usermod -a -G dialout $USER`, then log out/in; or for a "
                    "temporary test run `sudo chmod a+rw "
                    f"{self.resource_name}`."
                ) from exc
            raise

    def _open_visa(self) -> None:
        try:
            import pyvisa
        except Exception as exc:
            raise RuntimeError(
                "OWON VISA backend requested but pyvisa is not installed. "
                "Install pyvisa/pyvisa-py or set power_supply.backend: serial."
            ) from exc

        print(f"[INFO] Opening OWON SPE6053 VISA resource: {self.resource_name}")
        self.visa_manager = pyvisa.ResourceManager()
        self.visa_resource = self.visa_manager.open_resource(
            self.resource_name,
            timeout=int(self.config.timeout_s * 1000),
        )
        self.visa_resource.write_termination = "\n"
        self.visa_resource.read_termination = "\n"

    def _open_usbtmc(self) -> None:
        print(f"[INFO] Opening OWON SPE6053 USBTMC device: {self.resource_name}")
        self.usbtmc_fd = os.open(self.resource_name, os.O_RDWR | os.O_NONBLOCK)

    def _find_port(self) -> str:
        ports = list(serial.tools.list_ports.comports())
        configured_matches = [
            port
            for port in ports
            if (self.config.vid is None or port.vid == self.config.vid)
            and (self.config.pid is None or port.pid == self.config.pid)
        ]
        candidates = configured_matches if (self.config.vid or self.config.pid) else [
            port for port in ports if _looks_like_owon_port(port)
        ]
        if not candidates:
            tty_candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
            if len(tty_candidates) == 1:
                print(
                    "[WARN] OWON serial metadata was not detected; using only "
                    f"available tty candidate: {tty_candidates[0]}"
                )
                return tty_candidates[0]
            seen_ports = "; ".join(
                f"{port.device} ({port.description or port.hwid or 'no description'})"
                for port in ports
            ) or "none"
            seen_tty = ", ".join(tty_candidates) or "none"
            raise RuntimeError(
                "Could not find an OWON SPE6053 serial port. Set power_supply.port "
                "in resources/config.yaml or OWON_SPE6053_PORT. "
                f"Serial ports seen: {seen_ports}; tty candidates: {seen_tty}"
            )
        return candidates[0].device

    def _find_usbtmc_device(self) -> str:
        candidates = sorted(glob.glob("/dev/usbtmc*"))
        if not candidates:
            raise RuntimeError(
                "Could not find an OWON SPE6053 USBTMC device. Set "
                "power_supply.port to /dev/usbtmcX, or set backend: serial "
                "with power_supply.port /dev/ttyUSBX or /dev/ttyACMX."
            )
        if len(candidates) > 1:
            raise RuntimeError(
                "Multiple USBTMC devices found. Set power_supply.port explicitly. "
                f"USBTMC devices seen: {', '.join(candidates)}"
            )
        return candidates[0]

    def _find_visa_resource(self) -> str:
        try:
            import pyvisa
        except Exception as exc:
            raise RuntimeError(
                "Could not auto-detect an OWON VISA resource because pyvisa is not installed."
            ) from exc

        manager = pyvisa.ResourceManager()
        resources = list(manager.list_resources())
        manager.close()
        candidates = []
        for resource in resources:
            resource_upper = resource.upper()
            vid_ok = self.config.vid is None or f"{self.config.vid:04X}" in resource_upper
            pid_ok = self.config.pid is None or f"{self.config.pid:04X}" in resource_upper
            text_ok = "OWON" in resource_upper or "SPE" in resource_upper
            if (self.config.vid or self.config.pid) and vid_ok and pid_ok:
                candidates.append(resource)
            elif text_ok:
                candidates.append(resource)
        if not candidates:
            seen_resources = ", ".join(resources) or "none"
            raise RuntimeError(
                "Could not find an OWON SPE6053 VISA resource. Set "
                "power_supply.visa_resource in resources/config.yaml or "
                "OWON_SPE6053_RESOURCE. "
                f"VISA resources seen: {seen_resources}"
            )
        return candidates[0]


def _looks_like_owon_port(port) -> bool:
    if (port.vid, port.pid) in OWON_USB_SERIAL_IDS:
        return True
    text = " ".join(
        str(value or "")
        for value in (
            port.manufacturer,
            port.product,
            port.description,
            port.hwid,
        )
    ).upper()
    return "OWON" in text or "SPE6053" in text or "SPE" in text


def power_cycle_owon_spe6053(
    off_seconds: float | None = None,
    voltage_v: float | None = None,
    current_a: float | None = None,
    on_settle_seconds: float | None = None,
    required: bool = False,
) -> bool:
    config = load_owon_power_supply_config()
    if not config.enabled:
        print("[INFO] OWON power supply restart is disabled in resources/config.yaml.")
        return False

    try:
        with OwonSPE6053(config) as supply:
            print(
                "[INFO] OWON power supply connection ready: "
                f"backend={supply.backend} resource={supply.resource_name}"
            )
            identity = supply.identify()
            if identity:
                print(f"[INFO] Connected power supply: {identity}")
            print(
                "[STATUS] Power-cycling OWON SPE6053 output: "
                f"{voltage_v if voltage_v is not None else config.voltage_v:.1f} V, "
                f"{current_a if current_a is not None else config.current_a:.1f} A, "
                f"off for {off_seconds if off_seconds is not None else config.off_seconds:.1f}s."
            )
            supply.power_cycle(
                off_seconds=off_seconds,
                voltage_v=voltage_v,
                current_a=current_a,
                on_settle_seconds=on_settle_seconds,
            )
        print("[INFO] OWON power supply output is back on.")
        return True
    except Exception as exc:
        message = f"OWON SPE6053 power cycle failed: {exc}"
        if required:
            raise RuntimeError(message) from exc
        print(f"[WARN] {message}")
        return False


def set_owon_spe6053_output(
    enabled: bool,
    voltage_v: float | None = None,
    current_a: float | None = None,
    on_settle_seconds: float | None = None,
    required: bool = False,
) -> bool:
    config = load_owon_power_supply_config()
    if not config.enabled:
        print("[INFO] OWON power supply control is disabled in resources/config.yaml.")
        return False

    try:
        with OwonSPE6053(config) as supply:
            print(
                "[INFO] OWON power supply connection ready: "
                f"backend={supply.backend} resource={supply.resource_name}"
            )
            identity = supply.identify()
            if identity:
                print(f"[INFO] Connected power supply: {identity}")

            if enabled:
                voltage = config.voltage_v if voltage_v is None else float(voltage_v)
                current = config.current_a if current_a is None else float(current_a)
                settle = (
                    config.on_settle_seconds
                    if on_settle_seconds is None
                    else float(on_settle_seconds)
                )
                print(
                    "[STATUS] Turning OWON SPE6053 output ON: "
                    f"{voltage:.1f} V, {current:.1f} A."
                )
                supply.configure_output(voltage, current)
                supply.set_output(True)
                if settle > 0:
                    time.sleep(settle)
            else:
                print("[STATUS] Turning OWON SPE6053 output OFF.")
                supply.set_output(False)

        print(f"[INFO] OWON power supply output is {'ON' if enabled else 'OFF'}.")
        return True
    except Exception as exc:
        message = f"OWON SPE6053 output {'ON' if enabled else 'OFF'} failed: {exc}"
        if required:
            raise RuntimeError(message) from exc
        print(f"[WARN] {message}")
        return False
