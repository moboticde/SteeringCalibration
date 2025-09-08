import serial.tools.list_ports
from serial import Serial, SerialException
from io_helpers.find_device import find_serial_port
import os
import yaml

# Load VID and PID from config
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["arduino"]["VID"])
TARGET_PID = int(config["arduino"]["PID"])
BITRATE = int(config["arduino"]["BITRATE"])


class DriverArduino:

    def __init__(self):
        self.arduino = None
        self.initialize_arduino()

    def initialize_arduino(self):
        """Initialize Arduino Serial Communication with error handling."""
        try:
            current_port = find_serial_port(TARGET_VID,TARGET_PID)
            self.arduino = serial.Serial(current_port, BITRATE, timeout=10)
            #print("[SUCCESS] Arduino connected!")
        except SerialException as e:
            print(f"[ERROR] Arduino connection failed: {e}")
            self.arduino = None  # Prevent further usage
        except Exception as e:
            print(f"[ERROR] Unexpected error in Arduino initialization: {e}")
        
        if not self.arduino:
            raise RuntimeError("Arduino failed to initialize.")

    def set_relay_state(self, command: str):
        """Send a command to control the relay (e.g., "q1=1,q2=0")"""
        try:
            if not self.arduino.isOpen():
                print("[ERROR] Serial connection is closed.")
                return False
            
            self.arduino.flushInput()  # Clear any previous data
            self.arduino.write(str.encode(command))
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send relay command: {e}")
            return False
        
    def get_state(self, *value):
        """
        Read the response from the Arduino and return structured data.
        If 'S' is requested, returns a dictionary of relay states directly.
        """
        try:
            self.arduino.write(str.encode('S'))  # Request status from Arduino
            response = self.arduino.readline().decode().strip()

            parts = response.split('|')

            if len(parts) < 3:
                return None

            relay_status, resistance_status, current_status = parts[0], parts[1], parts[2]
            relay_states = {f"q{n+1}": int(state) for n, state in enumerate(relay_status)}

            if not value:  # If no specific value requested, return full response
                return {'relay_states': relay_states, 'resistance': resistance_status, 'current': current_status}

            key = value[0].upper()

            if key == 'R':
                return resistance_status
            elif key == 'I':
                return current_status
            elif key == 'S':
                return relay_states
            else:  # Return specific relay states if requested
                requested_states = {f"q{num}": relay_states.get(f"q{num}", "Unknown") for num in value}
                return requested_states

        except Exception as e:
            print(f"[ERROR] Failed to read or parse relay response: {e}")
            return None
    
    def send_and_confirm_relay_state(self, command, max_attempts = 1, confirm_attempts = 3):
        """
        Sends relay command and confirms that relays have reached the expected state.
        The command itself is the expected state, verified through feedback.
        Returns True if successful, otherwise False.
        """
        # Parse the command into a dictionary of expected states
        expected_states = {item.split('=')[0]: int(item.split('=')[1]) for item in command.split(',')}
        
        for attempt in range(1, max_attempts + 1):

            self.set_relay_state(command)

            if command is None:
                print("[ERROR] Wrong Command")
                return False
            
            # Confirmation flag to ensure the state is stable
            confirmation_count = 0

            while confirmation_count < confirm_attempts:
                relay_states = self.get_state('S')

                if relay_states is None:
                    continue  # Retry if no valid data is received

                if not isinstance(relay_states, dict):
                    continue  # Retry if the response is malformed

                # Compare only the relevant states (ignoring others)
                relevant_states = {key: relay_states.get(key, 0) for key in expected_states.keys()}

                if relevant_states == expected_states:  # Compare expected states with actual states
                    confirmation_count += 1  # Increment confirmation count if states match
                    if confirmation_count == confirm_attempts:  # Confirmed enough times
                        #print(f"[INFO] Relay states confirmed successfully on attempt {attempt}.")
                        return True
                else:
                    confirmation_count = 0  # Reset if states do not match

        print("[ERROR] Maximum attempts reached, relay states may not be stable.")
        return False  # Failed to confirm relay states

    def close_arduino(self):
        """Close arduino"""
        #print("\n[INFO] Shutting down Arduino")
        if self.arduino:
            try:
                command = 'q1=0,q2=0,q3=0,q4=0,q5=0,q6=0,q7=0,q8=0,q9=0,q10=0,q11=0,q12=0'
                self.arduino.write(str.encode(command))
                self.arduino.close()
                #print("[INFO] Arduino connection closed.")
            except Exception as e:
                print(f"[ERROR] Failed to close Arduino connection: {e}")

         
