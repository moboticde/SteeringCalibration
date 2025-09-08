import os
import subprocess, sys
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN 
from drivers.driver_QRreader import run_qr_reader
from io_helpers.find_product_folder import find_config

# Scan QR, locate config
run_qr_reader(show=True)
qrcode = run_qr_reader(show=True, once=True, return_first=True)
print("First QR:", qrcode)
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
   subprocess.run([
    sys.executable,
    script, # or config_path
    "--bitrate", "125",
    "--node", "59",
    "--set-node-id", "1",
], check=True)

print(f"Running: {script}")
subprocess.call([sys.executable, script])