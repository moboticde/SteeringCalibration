import os
import sys
import subprocess
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN 
from drivers.driver_QRreader import read
from io_helpers.find_product_folder import find_config

def open_folder(path: str):
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def run_script(script_path: str, interpreter: str | None = None, new_console: bool = True):
    interpreter = interpreter or sys.executable
    workdir = os.path.dirname(script_path)
    if sys.platform.startswith("win") and new_console:
        # Open a new console window
        subprocess.Popen(["cmd", "/c", "start", "", interpreter, os.path.basename(script_path)],
                         cwd=workdir)
    else:
        subprocess.run([interpreter, script_path], cwd=workdir, check=True)

def main():
    # Turn on camera and scan QR code
    qrcode = read()
    if not qrcode:
        raise RuntimeError("No QR code detected.")

    path = find_config(qrcode)
    if not path or not os.path.isdir(path):
        raise FileNotFoundError(f"Config folder not found for QR '{qrcode}': {path}")

    config_path = os.path.join(path, "01_SwConfiguration")
    if not os.path.isdir(config_path):
        raise FileNotFoundError(f"Missing folder: {config_path}")

    # Prefer SteeringScript_2.py, fall back to SteeringScript.py if needed
    product_script = os.path.join(config_path, "SteeringScript_2.py")
    if not os.path.isfile(product_script):
        alt = os.path.join(config_path, "SteeringScript.py")
        if os.path.isfile(alt):
            product_script = alt
        else:
            raise FileNotFoundError(f"No SteeringScript_2.py or SteeringScript.py in {config_path}")

    print(f"[INFO] Opening: {config_path}")
    open_folder(config_path)

    print(f"[INFO] Running: {product_script}")
    # Optionally choose interpreter with env var, e.g. set STEERING_PYTHON=C:\Python311\python.exe
    interpreter = os.environ.get("STEERING_PYTHON", None)
    run_script(product_script, interpreter=interpreter)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
