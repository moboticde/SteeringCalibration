import time
import os

CANOPEN_SAVE_SIGNATURE = 0x65766173
MICON_I32_MIN = -(2**31)
MICON_I32_MAX = 2**31 - 1
SSI_ZERO_POSITION_TOLERANCE_COUNTS = 3
SSI_ZERO_WRITE_ATTEMPTS = 6
SSI_ZERO_WRITE_SETTLE_TIMEOUT_S = 3.0
SSI_ZERO_WRITE_POLL_S = 0.25


def _checked_i32(value, label):
    value = int(value)
    if not MICON_I32_MIN <= value <= MICON_I32_MAX:
        raise ValueError(
            f"{label} outside signed 32-bit range: "
            f"value={value} range=[{MICON_I32_MIN}..{MICON_I32_MAX}]"
        )
    return value

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
            added_node = self.can.add_node(node_value, self.eds)
            probes = (
                (0x1000, 0x00, "device type"),
                (0x2000, 0x02, "node id parameter"),
                (0x3001, 0x00, "error code"),
            )
            last_error = None
            for attempt in range(1, 4):
                for index, subindex, label in probes:
                    try:
                        added_node.sdo.upload(index, subindex)
                        print(
                            f"[INFO] MiControlF35 - Successfully verified Node {node_value} "
                            f"via {label} 0x{index:04X}:{subindex:02X} with EDS {self.eds}"
                        )
                        return added_node
                    except Exception as e:
                        last_error = e
                        if e.__class__.__name__ == "SdoAbortedError":
                            print(
                                f"[WARN] Node {node_value} responded with SDO abort on "
                                f"0x{index:04X}:{subindex:02X}; treating node as reachable: {e}"
                            )
                            return added_node
                time.sleep(0.25 * attempt)
            print(f"[ERROR] Failed to add node {node_value}: {last_error}")
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

    def get_error_code(self):
        """Read the current controller error code from object 0x3001."""
        if not self.added_node:
            return None
        try:
            error_raw = self.added_node.sdo.upload(0x3001, 0)
            return int.from_bytes(error_raw, byteorder='little', signed=True)
        except Exception as e:
            print(f"[ERROR] Failed to read error code on node {self.node_id}: {e}")
            return None

    # activate/deactivate SSI encoder 
    def SSI_encoder(self, enable=True):
        """Enable or disable SSI encoder mode on F35."""
        if not self.added_node:
            return False

        node = self.added_node
        mode_value = b'\x01\x00' if enable else b'\x00\x00'
        try:
            self.added_node.sdo.download(0x3970, 0, mode_value)
            time.sleep(1)  # Allow time for mode change
            return True
        except Exception as e:
            print(f"[ERROR] Failed to {'enable' if enable else 'disable'} SSI encoder: {e}")
            return False

    def get_ssi_encoder_status(self):
        """Read the controller SSI encoder status bit."""
        if not self.added_node:
            return None
        try:
            raw = self.added_node.sdo.upload(0x3970, 0x01)
            return int.from_bytes(raw, byteorder='little', signed=False)
        except Exception as e:
            print(f"[ERROR] Failed to read SSI encoder status: {e}")
            return None

    def get_ssi_direct_position(self):
        """Read direct SSI absolute position before controller origin handling."""
        if not self.added_node:
            return None
        try:
            raw = self.added_node.sdo.upload(0x397A, 0x02)
            return int.from_bytes(raw, byteorder='little', signed=True)
        except Exception as e:
            print(f"[ERROR] Failed to read SSI direct position: {e}")
            return None

    def get_ssi_single_turn_resolution(self):
        """Read SSI absolute encoder single-turn resolution in controller counts."""
        if not self.added_node:
            return None
        try:
            raw = self.added_node.sdo.upload(0x3972, 0)
            return int.from_bytes(raw, byteorder='little', signed=False)
        except Exception as e:
            print(f"[ERROR] Failed to read SSI single-turn resolution: {e}")
            return None

    def restore_extended_ssi_mode(self) -> bool:
        """Restore the controller's operational 15-bit SSI frame configuration."""
        if not self.added_node:
            return False
        try:
            self.added_node.sdo.download(
                0x3971,
                0x02,
                int(15).to_bytes(4, byteorder='little', signed=False),
            )
            time.sleep(0.5)
            self.clear_errors()
            self.clear_errors()
            print("[INFO] Controller extended SSI frame restored: bits=15.")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to restore controller extended SSI frame: {e}")
            return False

    def store_parameters(self) -> bool:
        """Persist controller parameters using the device store command."""
        if not self.added_node:
            return False
        try:
            save_signature = CANOPEN_SAVE_SIGNATURE.to_bytes(4, byteorder='little', signed=False)
            self.added_node.sdo.download(0x3000, 0, b'\x80\x00')
            time.sleep(1.0)
            self.added_node.sdo.download(0x1010, 1, save_signature)
            time.sleep(1.0)
            self.added_node.sdo.download(0x1010, 6, save_signature)
            time.sleep(3.0)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to store controller parameters: {e}")
            return False

    def _wait_for_steering_zero_after_write(self, timeout_s: float) -> int | None:
        deadline = time.monotonic() + float(timeout_s)
        last_position = None
        while True:
            last_position = self.get_steering_pos()
            if (
                last_position is not None
                and abs(int(last_position)) <= SSI_ZERO_POSITION_TOLERANCE_COUNTS
            ):
                return int(last_position)
            if time.monotonic() >= deadline:
                return last_position
            time.sleep(SSI_ZERO_WRITE_POLL_S)

    def save_ssi_absolute_zero(self) -> bool:
        """Persist the controller-side SSI absolute encoder zero reference."""
        if not self.added_node:
            return False

        try:
            self.clear_errors()
            if not self.SSI_encoder(True):
                return False
            zero_bytes = int(0).to_bytes(4, byteorder='little', signed=True)
            zero_readback = None
            for attempt in range(1, SSI_ZERO_WRITE_ATTEMPTS + 1):
                self.added_node.sdo.download(0x3762, 0, zero_bytes)
                zero_readback = self._wait_for_steering_zero_after_write(
                    SSI_ZERO_WRITE_SETTLE_TIMEOUT_S,
                )
                print(
                    "[INFO] Controller actual-position zero write "
                    f"attempt {attempt}: steering_position={zero_readback}"
                )
                if (
                    zero_readback is not None
                    and abs(int(zero_readback)) <= SSI_ZERO_POSITION_TOLERANCE_COUNTS
                ):
                    break
            if (
                zero_readback is None
                or abs(int(zero_readback)) > SSI_ZERO_POSITION_TOLERANCE_COUNTS
            ):
                print(
                    "[ERROR] Controller actual position did not read back as zero "
                    f"before SSI absolute zero save: steering_position={zero_readback}"
                )
                return False
            self.added_node.sdo.download(
                0x3970,
                0x08,
                CANOPEN_SAVE_SIGNATURE.to_bytes(4, byteorder='little', signed=False),
            )
            time.sleep(1.0)
            if not self.store_parameters():
                return False
            print(
                "[INFO] Controller zero save readback: "
                f"direct_position={self.get_ssi_direct_position()} "
                f"steering_position={self.get_steering_pos()}"
            )
            self.clear_errors()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save SSI absolute zero: {e}")
            return False
    
    # remove time sleep
    def get_extended_ssi(self):
        """Verify standard SSI does not trigger -1092, then restore extended SSI."""
        if not self.added_node:
            return False

        node = self.added_node
        error_value = None
        self.last_ssi_configuration_error = None
        self.last_ssi_configuration_check_ok = False
        restored_extended_ssi = False

        self.clear_errors()
        self.clear_errors()
        if not self.SSI_encoder(True):
            print("[ERROR] Could not enable SSI encoder before configuration check.")
            return False

        try:
            print("[INFO] Checking that controller SSI configuration does not trigger -1092.")
            node.sdo.download(0x3971, 0x02, b'\x0c\x00\x00\x00')
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                time.sleep(0.25)
                error_value = self.get_error_code()
                if error_value not in (None, 0):
                    break
            print(f"[INFO] Controller error after standard SSI check: {error_value}")
        except Exception as exc:
            print(f"[ERROR] SSI configuration check failed: {exc}")
        finally:
            try:
                node.sdo.download(0x3971, 0x02, b'\x0f\x00\x00\x00')
                time.sleep(1.0)
                node.sdo.download(0x3000, 0, b'\x01\x00')
                time.sleep(0.2)
                restored_extended_ssi = True
            except Exception as exc:
                print(f"[ERROR] Could not restore extended SSI mode after -1092 check: {exc}")

        if not restored_extended_ssi:
            return False

        self.last_ssi_configuration_error = error_value
        if error_value == -1092:
            print("[ERROR] Controller error -1092 detected after configuration.")
            return False
        if error_value != 0:
            print(f"[ERROR] Unexpected controller error after configuration: {error_value}.")
            return False

        self.last_ssi_configuration_check_ok = True
        print("[INFO] No controller error -1092 detected; extended SSI mode restored.")
        return True



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
    
    def set_current_mode(self):
        if self.added_node:
            try:
                self.added_node.sdo.download(0x3003,0, b'\x02\x00\x00\x00')
                #print(f"[INFO] Node {self.node_id}: Current mode enabled.")
            except Exception as e:
                print(f"[ERROR] Failed to set current mode for node {self.node_id}: {e}")

    def set_position_mode(self):
        """Set device mode to position."""
        if self.added_node:
            self.added_node.sdo.download(0x3003, 0, b'\x07\x00\x00\x00')
            #print(f"[INFO] Node {self.node_id} - Device mode set to position")

    def set_device_mode_position(self):
        """Compatibility wrapper for callers that use the device-mode naming."""
        self.set_position_mode()

    def get_device_mode(self):
        """Read the active controller device mode."""
        if not self.added_node:
            return None
        try:
            raw = self.added_node.sdo.upload(0x3003, 0)
            return int.from_bytes(raw, byteorder='little', signed=False)
        except Exception as e:
            print(f"[ERROR] Failed to read device mode: {e}")
            return None

    def prepare_position_motion(self, rpm: int) -> bool:
        """Transition from calibration/current mode into motion-ready position mode."""
        if not self.added_node:
            return False
        try:
            self.enabled(False)
            time.sleep(0.25)
            self.clear_errors()
            self.clear_errors()
            self.set_device_mode_position()
            self.set_RPM(rpm)
            self.set_steering_RPM(rpm)
            time.sleep(0.25)
            self.enabled(True)
            time.sleep(0.5)
            mode = self.get_device_mode()
            error = self.get_error_code()
            print(
                "[INFO] Controller prepared for position motion: "
                f"mode={mode} rpm={int(rpm)} error={error}"
            )
            return mode == 7 and error in (None, 0)
        except Exception as e:
            print(f"[ERROR] Failed to prepare controller for position motion: {e}")
            return False

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
        position_fb = self.added_node.sdo.upload(0x3762, 0)
        return int.from_bytes(position_fb, byteorder='little', signed=True)

    def get_actual_position(self):
        """Retrieve actual position from the controller."""
        return self.get_steering_pos()

    def get_actual_current(self):
        """Retrieve RMS current from the controller."""
        if not self.added_node:
            return None
        actcurrent_fb = self.added_node.sdo.upload(0x3262, 0x00)
        return int.from_bytes(actcurrent_fb, byteorder='little', signed=True)

    def get_desired_current(self):
        """Retrieve desired current setpoint from the controller."""
        if not self.added_node:
            return None
        desired_fb = self.added_node.sdo.upload(0x3200, 0x00)
        return int.from_bytes(desired_fb, byteorder='little', signed=True)

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
    
    def set_digital_output(self, status=True):
        """Set digital output."""
        if self.added_node:
            dout = b'\x01\x00' if status else b'\x00\x00'
            self.added_node.sdo.download(0x3150, 0, dout)

    def set_position_zero(self):
        """Set position to zero."""
        if self.added_node:
            self.added_node.sdo.download(0x3762, 0, b'\x00\x00\x00\x00')
            #print(f"[INFO] Node {self.node_id} - Position set to zero")

    def set_RPM(self,value):
        rpm_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3500, 0, rpm_byte)
    
    def set_steering_RPM(self, value):
        rpm_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3300, 0, rpm_byte)
    
    def set_steering_pos(self, value):
        value = _checked_i32(value, "steering absolute position")
        position_byte = int.to_bytes(value, 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3790, 0, position_byte)

    def set_steering_relative(self, value):
        value = _checked_i32(value, "steering relative position")
        position_byte = int.to_bytes(value, 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3791, 0, position_byte)

    def set_error(self, value):
        error_byte = int.to_bytes(int(value), 2, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3000, 0x08, error_byte)

    def set_desired_current(self, value):
        current_byte = int.to_bytes(int(value), 4, byteorder='little', signed=True)
        if self.added_node:
            self.added_node.sdo.download(0x3200, 0, current_byte)
