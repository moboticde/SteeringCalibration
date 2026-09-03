#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import yaml
from serial.tools import list_ports

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "resources" / "config.yaml"
DEFAULT_CHANNEL = "can0"
DEFAULT_SLCAND_BITRATE_CODE = "s4"  # 125 kbit/s for slcan/canable firmware.


def _int_config(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def load_can_config() -> dict[str, int]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    can_config = config.get("can") or {}
    return {
        "vid": _int_config(can_config["VID"]),
        "pid": _int_config(can_config["PID"]),
        "serial_bitrate": int(can_config.get("BITRATE", 115200)),
    }


def find_can_serial_device(vid: int, pid: int) -> str:
    override = os.getenv("ST_CAN_SERIAL")
    if override:
        return override

    matches = [
        port
        for port in list_ports.comports()
        if port.vid == vid and port.pid == pid
    ]
    if not matches:
        available = ", ".join(
            f"{port.device}({port.vid!r}:{port.pid!r} {port.description})"
            for port in list_ports.comports()
        ) or "none"
        raise RuntimeError(
            f"No CAN adapter found for VID:PID {vid:04X}:{pid:04X}. "
            f"Available serial ports: {available}"
        )
    matches.sort(key=lambda port: port.device)
    return matches[0].device


def build_slcand_command(device: str, channel: str, serial_bitrate: int) -> list[str]:
    return [
        "/usr/bin/slcand",
        "-F",
        "-o",
        "-c",
        "-f",
        DEFAULT_SLCAND_BITRATE_CODE,
        "-S",
        str(serial_bitrate),
        device,
        channel,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start slcand for the ST calibration CAN adapter.")
    parser.add_argument("--channel", default=os.getenv("ST_CAN_CHANNEL", DEFAULT_CHANNEL))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    can_config = load_can_config()
    device = find_can_serial_device(can_config["vid"], can_config["pid"])
    command = build_slcand_command(device, args.channel, can_config["serial_bitrate"])
    print("[INFO] Starting SocketCAN bridge:", " ".join(command), flush=True)
    if args.dry_run:
        return 0
    os.execv(command[0], command)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
