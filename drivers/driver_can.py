
import canopen
import os, time
import yaml

# Load VID and PID from config
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["can"]["VID"])
TARGET_PID = int(config["can"]["PID"])

class DriverCan:
    def __init__(self, can_bitrate, interface=None, channel=None):
        self.can_bitrate = can_bitrate * 1000
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
        self.initialize_canopen()


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
