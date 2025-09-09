from io_helpers.find_device import find_pcan_port
import canopen
import os
import yaml

# Load VID and PID from config
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["can"]["VID"])
TARGET_PID = int(config["can"]["PID"])

class DriverCan:
    def __init__(self, can_bitrate):
        self.can_bitrate = can_bitrate * 1000
        self.can_network = canopen.Network()
        self.initialize_canopen()

    #It shouldnt crash. Connected/notConnected
    def initialize_canopen(self):
        """Initialize or reconnect to CANopen communication with error handling."""
        try:
            if self.can_network is None:
                self.can_network = canopen.Network()

            current_port = find_pcan_port(TARGET_VID, TARGET_PID)

            if self.can_network.bus is None:  # Check if the network was not previously connected
                self.can_network.connect(interface='pcan', channel = 'PCAN_PCIBUS2', bitrate=self.can_bitrate)
                print("[SUCCESS] CANopen network connected!")
            else:
                # Disconnect and reconnect the network
                try:
                    self.can_network.disconnect()
                    self.can_network.connect(bustype='pcan', channel='PCAN_PCIBUS2', bitrate=self.can_bitrate)
                    print("[SUCCESS] Reconnected to CANopen network.")
                except Exception as e:
                    print(f"[ERROR] Failed to reconnect: {e}")

        except Exception as e:
            print(f"[ERROR] Error in CANopen initialization: {e}")
            raise RuntimeError("CAN device failed to initialize.")
    
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
