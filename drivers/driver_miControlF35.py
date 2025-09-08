import time
import os
class MicontrolF35_CAN: 
    def __init__(self, can, node):
        """
        Initialize MicontrolF35 CAN driver.
        Automatically adds nodes and clears errors.
        :param can: The CAN network instance.
        :param node: The node ID for the CAN network.
        """
        self.can = can
        self.node_id = node  # Store node ID separately
        self.eds = os.path.join(os.path.dirname(__file__), "..", "resources", "mcDSA-Exx.eds")
        self.added_node = self.add_nodes()  # Automatically add node

        #print("[INFO] Initializing MicontrolF35...")

        # Automatically clear errors
        self.clear_errors()

    def add_nodes(self):
        """Automatically adds nodes for MiControl CAN when the class is initialized."""
        if self.node_id is not None:
            node_value = int(self.node_id)  # Convert to int
            try:
                added_node = self.can.add_node(node_value, self.eds)
                
                # Verify node is responding
                if added_node.sdo.upload(0x1000, 0):  # Attempting to read device type (0x1000)
                    #print(f"[INFO] MiControlF35 - Successfully added and verified Node {node_value} with EDS {self.eds}")
                    return added_node
                else:
                    print(f"[ERROR] Node {node_value} did not respond to SDO request.")
                    return None
            except Exception as e:
                print(f"[ERROR] Failed to add node {node_value}: {e}")
                return None
        return None

    def clear_errors(self):
        """Automatically clears errors for MiControl CAN when the class is initialized."""
        if self.added_node:
            try:
                self.added_node.sdo.download(0x3000, 0, b'\x01\x00')
                self.added_node.sdo.download(0x3000, 0, b'\x01\x00')
                #print(f"[INFO] MiControlF35 - Cleared errors for node {self.node_id}")
            except Exception as e:
                print(f"[ERROR] MiControlF35 - Failed to clear errors on node {self.node_id}: {e}")
    
    # remove time sleep
    def get_extended_ssi(self):
        """Set Extended SSI mode on F35 and wait until error == -1092."""
        if not self.added_node:
            return False

        node = self.added_node

        # Step 1: Set standard SSI
        node.sdo.download(0x3971, 0x02, b'\x0c\x00\x00\x00')

        # Step 2: Wait briefly to allow mode change to take effect
        time.sleep(1)

        # Step 3: Read error
        try:
            read_error2 = node.sdo.upload(0x3001, 0)
            error_value = int.from_bytes(read_error2, byteorder='little', signed=True)
        except:
            return False

        # Step 4: Set extended (15-bit) SSI
        node.sdo.download(0x3971, 0x02, b'\x0f\x00\x00\x00')

        # Step 5: Give controller time to switch encoder config
        time.sleep(1)

        # Step 6: Clear error
        try:
            node.sdo.download(0x3000, 0, b'\x01\x00')
        except:
            return False

        return error_value == -1092



    def get_SW_version(self):
        """Retrieve Software Version."""
        if not self.added_node:
            return None
        script_version = self.added_node.sdo.upload(0x302E,0x02)
        sv = int.from_bytes(script_version, byteorder='little', signed=True)
        return sv/100 

    def get_Serial_number(self):
        """Retrieve Controller Serial Number"""
        if not self.added_node:
            return None
        controller_serial_number = self.added_node.sdo.upload(0x302D, 0x02)
        csn = int.from_bytes(controller_serial_number, byteorder='little', signed=True)
        return csn


    def get_HW_version(self):
        """Retrieve Hardware Version."""
        if not self.added_node:
            return None
        controller_HW = self.added_node.sdo.upload(0x302E, 0x01)
        return int.from_bytes(controller_HW, byteorder='little', signed=True)
    
    def get_Brake_count(self):
        """Retrieve Brake Count."""
        if not self.added_node:
            return None
        brake_count = self.added_node.sdo.upload(0x302F, 0x01)
        return int.from_bytes(brake_count, byteorder='little', signed=True)
    
    def get_Running_seconds(self):
        """Retrieve Running Seconds."""
        if not self.added_node:
            return None
        running_seconds = self.added_node.sdo.upload(0x302F, 0x02)
        return int.from_bytes(running_seconds, byteorder='little', signed=True)

    def get_MPU_version(self):
        """Retrieve MPU Version."""
        if not self.added_node:
            return None
        controller_MPUNr = self.added_node.sdo.upload(0x5101, 0x02)
        return int.from_bytes(controller_MPUNr, byteorder='little', signed=True)

    def set_velocity_mode(self):
        if self.added_node:
            try:
                self.added_node.sdo.download(0x3003,0, b'\x05\x00\x00\x00')
                #print(f"[INFO] Node {self.node_id}: Velocity mode enabled.")
            except Exception as e:
                print(f"[ERROR] Failed to set velocity mode for node {self.node_id}: {e}")

    def get_temperature(self):
        """Retrieve temperature from the controller."""
        if not self.added_node:
            return None
        temp_fb = self.added_node.sdo.upload(0x5101, 0x01)
        return int.from_bytes(temp_fb, byteorder='little', signed=True)

    def get_velocity(self):
        """Retrieve velocity from the controller."""
        if not self.added_node:
            return None
        velocity_fb = self.added_node.sdo.upload(0x3A04, 0x01)
        return int.from_bytes(velocity_fb, byteorder='little', signed=True)
    
    def get_steering_pos(self):
        """Retrieve position from the controller."""
        if not self.added_node:
            return None
        position_fb = self.added_node.sdo.upload(0x3A04, 0x01)
        return int.from_bytes(position_fb, byteorder='little', signed=True)


    def get_rms_current(self):
        """Retrieve RMS current from the controller."""
        if not self.added_node:
            return None
        rmscurrent_fb = self.added_node.sdo.upload(0x3113, 0x00)
        return int.from_bytes(rmscurrent_fb, byteorder='little', signed=True)
    
    def get_rms_current_steering(self):
        """Retrieve RMS current from the steering controller."""
        if not self.added_node:
            return None
        rmscurrent_fb = self.added_node.sdo.upload(0x3262, 0x01)
        return int.from_bytes(rmscurrent_fb, byteorder='little', signed=True)

    def enabled(self, status):
        """Enable or disable the device input."""
        if self.added_node:
            command = b'\x01\x00' if status else b'\x00\x00'
            self.added_node.sdo.download(0x3004, 0, command)

    def set_position_zero(self):
        """Set position to zero."""
        if self.added_node:
            self.added_node.sdo.download(0x3762, 0, b'\x00\x00\x00\x00')
            #print(f"[INFO] Node {self.node_id} - Position set to zero")

    def set_device_mode_position(self):
        """Set device mode to position."""
        if self.added_node:
            self.added_node.sdo.download(0x3003, 0, b'\x07\x00\x00\x00')
            #print(f"[INFO] Node {self.node_id} - Device mode set to position")

    def set_RPM(self,value):
        rpm_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3500, 0, rpm_byte)
    
    def set_steering_RPM(self, value):
        rpm_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3300, 0, rpm_byte)
    
    def set_steering_pos(self, value):
        position_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3790, 0, position_byte)
