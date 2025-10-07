#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, re, glob, importlib.util

from io_helpers.find_product_folder import find_config
from drivers.driver_QRreader import run_qr_reader
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN
from drivers.driver_mc import DSACompat
from mc import _pymc_builtins_ as bi
from mc.pymc import Run  

# ---------- helpers ----------
def find_mpu_under_product(product_dir: str) -> str:
    cands = []
    cands += glob.glob(os.path.join(product_dir, "01_SwConfiguration", "my_program*.py"))
    if not cands:
        cands += glob.glob(os.path.join(product_dir, "**", "my_program*.py"), recursive=True)
    cands = sorted(set(cands), key=lambda p: (not re.search(r"MPU_v\\d+", os.path.basename(p)), p))
    return cands[0] if cands else ""

def resolve_mpu_via_qr() -> str:
    print("[INFO] Scanning QR (camera window opens)...")
    qr_text = run_qr_reader(show=True, once=True, return_first=True, timeout=0.0)
    if not qr_text:
        print("[ERROR] No QR detected."); sys.exit(1)

    if os.path.isdir(qr_text):
        product_dir = os.path.abspath(qr_text)
        print(f"[INFO] QR points to directory: {product_dir}")
    elif os.path.isfile(qr_text):
        product_dir = os.path.dirname(os.path.abspath(qr_text))
        print(f"[INFO] QR points to file; using its folder: {product_dir}")
    else:
        product_dir = find_config(qr_text)
        if not product_dir or not os.path.isdir(product_dir):
            print(f"[ERROR] Could not resolve product folder from QR: {qr_text}")
            sys.exit(1)
        print(f"[INFO] Product folder: {product_dir}")

    mpu = find_mpu_under_product(product_dir)
    if not mpu:
        print(f"[ERROR] No MPU*.py found under: {product_dir}")
        sys.exit(1)
    print(f"[INFO] Resolved MPU → {mpu}")
    return mpu

_INT = r"(0x[0-9A-Fa-f]+|\\d+)"
def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
def _m_int(pattern: str, text: str):
    m = re.search(pattern, text)
    return (int(m.group(1), 0) if m else None)
def parse_node_bitrate_timeout(mpu_src: str):
    node = _m_int(r"\\bSpGp_NodeId\\s*\\(\\s*%s\\s*\\)" % _INT, mpu_src) \
        or _m_int(r"\\bDsa\\s*\\(\\s*%s\\s*\\)" % _INT, mpu_src) \
        or _m_int(r"\\bNODE\\s*=\\s*%s\\b" % _INT, mpu_src) \
        or 2
    bitrate = _m_int(r"\\bBITRATE\\s*=\\s*%s\\b" % _INT, mpu_src) or 250
    timeout = _m_int(r"\\bSpGp_Timeout\\s*\\(\\s*%s\\s*\\)" % _INT, mpu_src) \
        or _m_int(r"\\bTIMEOUT\\s*=\\s*%s\\b" % _INT, mpu_src) \
        or 0xFFFF
    return node, bitrate, timeout

def import_module_from_file(path: str):
    mod_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        print(f"[ERROR] Cannot load module from {path}"); sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

# ---- main -------------------------------------------------------------------
def main():
    mpu_path = resolve_mpu_via_qr()              # e.g. ...\01_SwConfiguration\my_program_run.py (or similar)
    prog_dir = os.path.dirname(mpu_path)
    program_path = os.path.join(prog_dir, "my_program.py")

    if not os.path.isfile(program_path):
        print(f"[ERROR] my_program.py not found at: {program_path}")
        return

    src = _read_text(program_path)
    node, bitrate, timeout = parse_node_bitrate_timeout(src)
    print(f"[INFO] Using MPU params → NODE: {node} | BITRATE: {bitrate} kbit/s | TIMEOUT: {timeout} ms")

    can = DriverCan(can_bitrate=int(bitrate))
    mic = MicontrolF35_CAN(can=can.can_network, node=int(node))
    if not mic.added_node:
        print("[ERROR] Could not add CAN node."); can.close_can(); sys.exit(1)
    dsa = DSACompat(mic.added_node)

    try:
        try:
            dev_type = dsa.SdoRd(0x1000, 0x00)
            print(f"[INFO] DeviceType 0x1000:00 = 0x{dev_type:08X}")
        except Exception as e:
            print(f"[WARN] Could not read 0x1000:00: {e}")

        bi.Can.attach(dsa, int(node))
        bi.SpGp_NodeId(int(node));  bi.SpxGpx_NodeId(int(node))
        bi.SpGp_Timeout(int(timeout));  bi.SpxGpx_Timeout(int(timeout))

        # <<< key change: pass the absolute path >>>
        Run(node_id=int(node), prg_filename=program_path, store=False, start=True, dump=0)

        print("[INFO] MPU completed.")
    finally:
        can.close_can()
        print("[INFO] CAN closed.")


if __name__ == "__main__":
    main()
