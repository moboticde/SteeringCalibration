# FlashConfigFile.py
import os, sys, subprocess
from io_helpers.find_product_folder import find_config
from drivers.driver_QRreader import run_qr_reader

# 1) Scan a single QR and get the matching product config
qrcode = run_qr_reader(show=True, once=True, return_first=True)
if not qrcode:
    print("[ERROR] No QR detected. Aborting.")
    sys.exit(1)

path = find_config(qrcode)
if not path:
    print(f"[ERROR] No product folder found for QR: {qrcode}")
    sys.exit(1)

config_path = os.path.join(path, "01_SwConfiguration")
try:
    os.startfile(config_path)  # Windows explorer
except Exception:
    pass

# 2) Build path to SteeringScript and run it
script = os.path.join(config_path, "SteeringScript_2.py")
if os.path.isfile(script):
    args = [
        sys.executable,
        script,
        "--bitrate", "125",
        "--node", "59",
        # "--set-node-id", "1",   # <- enable only when you really want to change it
    ]
    print("[INFO] Running:", " ".join(args))
    subprocess.run(args, check=True)
else:
    print(f"[ERROR] Steering script not found at: {script}")
