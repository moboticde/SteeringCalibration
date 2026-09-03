
import canopen
import os, time
import re
import subprocess
import yaml

# Load VID and PID from config
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["can"]["VID"])
TARGET_PID = int(config["can"]["PID"])

class DriverCan:
    def __init__(self, can_bitrate, interface=None, channel=None):
        self.can_bitrate_kbit = int(float(can_bitrate))
        self.can_bitrate = self.can_bitrate_kbit * 1000
        self.interface = (
            interface if interface is not None else os.getenv("ST_CAN_INTERFACE", "socketcan")
        )
        self.channel = channel if channel is not None else os.getenv("ST_CAN_CHANNEL", "can0")
        self._connect_kwargs = {
            "interface": self.interface,
            "channel": self.channel,
        }
        if self.interface != "socketcan":
            self._connect_kwargs.update(
                {
                    "bitrate": self.can_bitrate,
                    "auto_reset": True,
                }
            )
        self.can_network = canopen.Network()

        time.sleep(3)  # Allow time for the CAN interface to stabilize
        if self.interface == "socketcan":
            self.ensure_socketcan_bitrate()
        self.initialize_canopen()

    def _run_ip(self, *args):
        return subprocess.run(
            ["ip", *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def _socketcan_status(self):
        result = self._run_ip("-details", "link", "show", self.channel)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            if "does not exist" in detail:
                detail = (
                    f"{detail}. SocketCAN interface {self.channel} is missing; "
                    "connect the CAN adapter, load its kernel driver, or set "
                    "ST_CAN_CHANNEL to the actual CAN interface name."
                )
            raise RuntimeError(
                f"Could not inspect CAN interface {self.channel}: "
                f"{detail}"
            )
        return result.stdout

    def _socketcan_link_is_up(self, status):
        first_line = status.splitlines()[0] if status.splitlines() else ""
        flags_match = re.search(r"<([^>]*)>", first_line)
        flags = set(flags_match.group(1).split(",")) if flags_match else set()
        return "UP" in flags or re.search(r"\bstate\s+UP\b", first_line) is not None

    def ensure_socketcan_bitrate(self):
        """Ensure socketcan is configured to the requested bitrate before CANopen starts."""
        status = self._socketcan_status()
        match = re.search(r"\bbitrate\s+(\d+)\b", status)
        current_bitrate = int(match.group(1)) if match else None
        if current_bitrate == 0 and "clock 0" in status:
            return
        if current_bitrate == self.can_bitrate:
            if self._socketcan_link_is_up(status):
                return
            result = self._run_ip("link", "set", self.channel, "up")
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(
                    f"CAN interface {self.channel} bitrate is {current_bitrate}, "
                    "but the link is down. Could not bring it up automatically: "
                    f"{detail or 'unknown error'}. "
                    f"Run: sudo ip link set {self.channel} up"
                )
            status = self._socketcan_status()
            if self._socketcan_link_is_up(status):
                return
            raise RuntimeError(
                f"CAN interface {self.channel} bitrate is {current_bitrate}, "
                "but the link is still down after attempting to bring it up."
            )

        for args in (
            ("link", "set", self.channel, "down"),
            ("link", "set", self.channel, "type", "can", "bitrate", str(self.can_bitrate)),
            ("link", "set", self.channel, "up"),
        ):
            result = self._run_ip(*args)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(
                    f"CAN interface {self.channel} bitrate is {current_bitrate}, "
                    f"expected {self.can_bitrate}. Could not configure it automatically: {detail}. "
                    f"Run: sudo ip link set {self.channel} down && "
                    f"sudo ip link set {self.channel} type can bitrate {self.can_bitrate} && "
                    f"sudo ip link set {self.channel} up"
                )

        status = self._socketcan_status()
        match = re.search(r"\bbitrate\s+(\d+)\b", status)
        configured_bitrate = int(match.group(1)) if match else None
        if configured_bitrate != self.can_bitrate:
            raise RuntimeError(
                f"CAN interface {self.channel} bitrate is {configured_bitrate}, "
                f"expected {self.can_bitrate}."
            )

    def initialize_canopen(self):
        """Initialize or reconnect to CANopen communication with error handling."""
        try:
            if self.can_network is None:
                self.can_network = canopen.Network()

            if self.can_network.bus is None:  # Check if the network was not previously connected
                self.can_network.connect(**self._connect_kwargs)
                #print("[SUCCESS] CANopen network connected!")
            else:
                # Disconnect and reconnect the network
                try:
                    self.can_network.disconnect()
                    self.can_network.connect(**self._connect_kwargs)
                    #print("[SUCCESS] Reconnected to CANopen network.")
                except Exception as e:
                    print(f"[ERROR] Failed to reconnect: {e}")

        except Exception as e:
            print(f"[ERROR] Error in CANopen initialization: {e}")
            raise RuntimeError("CAN device failed to initialize.")      

    def reset_bus(self, delay_seconds: float = 0.5) -> bool:
        """Disconnect and reconnect the CAN network after a bus-off event."""
        try:
            if self.can_network:
                self.can_network.disconnect()
        except Exception as e:
            print(f"[WARN] CAN disconnect during reset failed: {e}")

        time.sleep(delay_seconds)
        self.can_network = canopen.Network()
        try:
            self.initialize_canopen()
            return True
        except Exception as e:
            print(f"[ERROR] CAN reset failed: {e}")
            return False
        
    # Clear Errors on Node
    def clear_errors(self, motor_node, high_voltage):
        """Clears error codes on the specified node."""
        try:
            if high_voltage:
                motor_node.sdo.download(0x3000, 0, b'\x01\x00')
                motor_node.sdo.download(0x6040, 0, b'\x80\x00\x00\x00')
            else:
                motor_node.sdo.download(0x3000, 0, b'\x01\x00')
            #print("[INFO] Error codes cleared.")
        except Exception as e:
            print(f"[ERROR] Failed to clear errors: {e}")

    def close_can(self):
        if self.can_network:
            try:
                self.can_network.disconnect()
                #print("[INFO] CANopen network disconnected.")
            except Exception as e:
                print(f"[ERROR] Failed to disconnect CANopen: {e}")
