import os
import sys
import subprocess
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN 
from drivers.driver_QRreader import run_qr_reader
from io_helpers.find_product_folder import find_config

# Scan QR, locate config
qrcode = read()
path = find_config(qrcode)
config_path = os.path.join(path, "01_SwConfiguration")

# Open folder (Windows)
try:
    os.startfile(config_path)  # type: ignore[attr-defined]
except Exception:
    pass

# Pick script and run it
script = os.path.join(config_path, "SteeringScript_2.py")
if not os.path.isfile(script):
    script = os.path.join(config_path, "SteeringScript.py")

print(f"Running: {script}")
subprocess.call([sys.executable, script])