import serial
import serial.tools.list_ports
import pyvisa

def find_serial_port(target_vid, target_pid):
    """
    Finds and connects to a serial device by VID & PID.
    
    """
    ports = serial.tools.list_ports.comports()

    for port in ports:
        if port.vid == target_vid and port.pid == target_pid:
            return port.device

def find_visa_port(target_vid, target_pid):
    """
    Finds and connects to a VISA device by VID & PID.
    """
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    target_vid_str = hex(target_vid)[2:].upper().zfill(4)  # Ensure consistent format
    target_pid_str = hex(target_pid)[2:].upper().zfill(4)

    for resource in resources:
        resource_upper = resource.upper()  # Convert full resource string to uppercase
        if target_vid_str in resource_upper and target_pid_str in resource_upper:
            #print(f"[INFO] Found VISA device: {resource}")
            return resource
    
    print("[ERROR] No matching VISA device found.")
    return None


def find_pcan_port(target_vid, target_pid):
    """
    Finds and returns the PCAN channel name corresponding to the given VID and PID.
    """
    devices = serial.tools.list_ports.comports()
    for device in devices:
        if device.vid == target_vid and device.pid == target_pid:
            #print(f"[INFO] Found PCAN device: {device.device}")
            return device.device
    print("[ERROR] No matching PCAN device found.")
    return None