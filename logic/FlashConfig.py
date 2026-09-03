"""
FlashConfigFile.py

Delegate configuration application to ConfigProcessing for consistency.
"""

import os, sys, time, argparse
from io_helpers.find_product_folder import find_config
from drivers.driver_QRreader import run_qr_reader
from utils.config_processing import ConfigProcessing
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN
from drivers.driver_mc import DSACompat
from utils.config_processing import nmt_reset_node_compat

# --- Steering script discovery (QR) ---
def import_script_via_qr():
    qrcode = run_qr_reader(show=True, once=True, return_first=True)
    if not qrcode:
        print("[ERROR] No QR detected. Aborting.")
        sys.exit(1)
    product_dir = os.path.join(find_config(qrcode),"S-1000-200-01") # withot "S-1000-200-01"
    if not product_dir:
        print(f"[ERROR] No product folder found for QR: {qrcode}")
        sys.exit(1)
    script_path = os.path.join(product_dir, "01_SwConfiguration", "SteeringScript.py")
    if os.path.isfile(script_path):
        return script_path
    print("[ERROR] No SteeringScript.py found in 01_SwConfiguration.")
    sys.exit(1)

def main(desired_node_id: int | None = None):
    script_path = import_script_via_qr()
    print(f"[INFO] Using script: {script_path}")

    # Let ConfigProcessing discover type (steering vs left/right),
    # extract parameters, open CAN and apply the configuration.
    cp = ConfigProcessing(script_path=script_path, can_bitrate_kbit=250)
    info = cp.summary()
    print(f"[INFO] Summary -> kind={info['kind']} | node={info['params'].get('current_node_id')} | new_node={info['params'].get('new_node_id')} | bitrate={info['can_bitrate_kbit']}")

    p = cp.params
    node = desired_node_id if desired_node_id is not None else int(p["current_node_id"])
    print(f"[INFO] Opening CAN at {cp.can_bitrate_kbit} kbit/s, current Node-ID={node}")
    can = DriverCan(can_bitrate=cp.can_bitrate_kbit)
    try:
        mic = MicontrolF35_CAN(can=can.can_network, node=node)
        if not mic.added_node:
            raise RuntimeError("Could not add CAN node (no SDO response).")
        dsa = DSACompat(mic.added_node)

        if cp.kind == "steering":
            print("[INFO] Running InitPar(d) from SteeringScript...")
            cp.funcs["InitPar"](dsa)  # SteeringScript.InitPar(d)
            # readback Node-ID param
            try:
                val = dsa.SdoRd(0x2000, 0x02)
                print(f"[DBG] Readback 0x2000:02 (Node-ID param) = {val}")
            except Exception as e:
                print(f"[WARN] Could not read 0x2000:02: {e}")
            # NMT reset if script set a new node id
            if p.get("new_node_id") is not None:
                if nmt_reset_node_compat(mic.added_node.nmt):
                    time.sleep(1.5)
                    print(f"[INFO] Device should now respond on Node-ID {p['new_node_id']}.")
                else:
                    print("[WARN] Power-cycle may be required to finalize Node-ID change.")
            return

        # Left/Right configs
        has_left = any(k.startswith("TractionLeft") for k in cp.funcs)
        has_right = any(k.startswith("TractionRight") for k in cp.funcs)
        if has_left and "TractionLeftPar" in cp.funcs:
            print("[INFO] Applying TractionLeftPar...")
            cp.funcs["TractionLeftPar"](dsa)
        if has_left and "TractionLeftCommPar" in cp.funcs:
            print("[INFO] Applying TractionLeftCommPar...")
            cp.funcs["TractionLeftCommPar"](dsa)
        if has_right and "TractionRightPar" in cp.funcs:
            print("[INFO] Applying TractionRightPar...")
            cp.funcs["TractionRightPar"](dsa)
        if has_right and "TractionRightCommPar" in cp.funcs:
            print("[INFO] Applying TractionRightCommPar...")
            cp.funcs["TractionRightCommPar"](dsa)

        # If baudrate function present, run it last
        if "Baudrate" in cp.funcs:
            print("[INFO] Applying Baudrate (device baud code @0x2000:03)...")
            cp.funcs["Baudrate"](dsa)

        # Readback Node-ID and reset if changed
        if p.get("new_node_id") is not None:
            try:
                after = dsa.SdoRd(0x2000, 0x02)
                print(f"[DBG] 0x2000:02 after write = {after}")
            except Exception:
                pass
            if nmt_reset_node_compat(mic.added_node.nmt):
                time.sleep(1.5)
                print(f"[INFO] Device should now respond on Node-ID {p['new_node_id']}.")
            else:
                print("[WARN] Power-cycle may be required to finalize Node-ID change.")

    finally:
        can.close_can()
        print("[INFO] CAN closed.")
if __name__ == "__main__":
    main()
