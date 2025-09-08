import pyvisa as visa
from io_helpers.find_device import find_visa_port
import os
import yaml

# Load VID and PID from config
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["multimeter"]["VID"])
TARGET_PID = int(config["multimeter"]["PID"])

class DriverMultimeter:
    def __init__(self):
        self.multimeter = None
        self.initialize_multimeter()

    def initialize_multimeter(self):
        """Initialize Rigol Multimeter Communication with error handling."""
        try:
            #print("[INFO] Connecting to Rigol Multimeter...")
            rm = visa.ResourceManager()
            current_port = find_visa_port(TARGET_VID, TARGET_PID)

            if not current_port:
                raise ConnectionError("No valid VISA device found.")
            
            self.multimeter = rm.open_resource(current_port, timeout=5000)

            # Reset device to clear any previous states
            #self.multimeter.write("*RST")

            # Wait for device to be ready after reset
            self.wait_for_ready()

            # Query device identity
            device_id = self.query("*IDN?")
            if not device_id:
                print("[ERROR] Failed to retrieve device ID.")

        except visa.VisaIOError as e:
            print(f"[ERROR] VISA communication error: {e}")
            self.multimeter = None  
        except ConnectionError as e:
            print(f"[ERROR] Multimeter not found: {e}")
            self.multimeter = None
        except Exception as e:
            print(f"[ERROR] Unexpected error in Multimeter initialization: {e}")

        if not self.multimeter:
            raise RuntimeError("Multimeter failed to initialize.")

    def wait_for_ready(self):
        """Poll the device until it becomes responsive."""
        if self.multimeter:
            for attempt in range(20):  # Try up to 20 times before giving up
                try:
                    response = self.query("*OPC?")  # Operation Complete query
                    if response == "1":
                        return  # Exit function if device is ready
                except visa.VisaIOError:
                    pass  # Ignore the error and keep trying
        else:
            print("[ERROR] Multimeter is not connected.")

    def query(self, command):
        """Send a command to the multimeter and return the response."""
        if self.multimeter:
            try:
                response = self.multimeter.query(command + "\n")
                response = response.strip()  # Remove whitespace/newlines
                return response
            except Exception as e:
                print(f"[ERROR] Failed to send query '{command}': {e}")
        else:
            print("[ERROR] Multimeter is not connected.")
            return None

    def measure_voltage(self, retries=3):
        """Measure Voltage (DC or AC) with status checking."""
        #self.wait_for_ready()

        for attempt in range(retries):
            response = self.query(":MEASure:VOLTage:DC?")
            
            if response:
                value = float(response)
                return value
        
        print("[ERROR] Failed to get a valid measurement after retries.")
        return None

    def close_multimeter(self):
        """Safely close the multimeter connection."""
        if self.multimeter:
            try:
                self.multimeter.close()
                #print("[INFO] Multimeter connection closed.")
            except Exception as e:
                print(f"[ERROR] Failed to close Multimeter: {e}")
