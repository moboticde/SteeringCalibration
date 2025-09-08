# FlashConfigFile.py
import os, sys, time, argparse, importlib.util, inspect, re
from io_helpers.find_product_folder import find_config
from drivers.driver_QRreader import run_qr_reader
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN
from canopen.sdo.exceptions import SdoAbortedError

class DSACompat:
    def __init__(self, node):
        self.node = node

    def _sizes_for(self, v: int):
        v = int(v)
        if v <= 0xFF:    return (1, 2, 4)
        if v <= 0xFFFF:  return (2, 4)
        return (4,)

    def SdoWr(self, index, subindex, value, timeout=None):
        """
        Version-agnostic SDO write:
        1) Try EDS-based write via .raw
        2) Fallback to download() with auto-sizing
        3) Handle canopen versions that lack 'timeout' kwarg
        'timeout' may be given in ms (e.g. 500) or seconds (e.g. 0.5).
        """
        val = int(value)
        # 1) Fast path: EDS-based write
        try:
            self.node.sdo[index][subindex].raw = val
            return
        except Exception:
            pass
        # normalize timeout to seconds if it looks like milliseconds
        to_s = None
        if isinstance(timeout, (int, float)):
            to_s = timeout / 1000.0 if timeout > 10 else float(timeout)

        last_err = None
        for size in self._sizes_for(val):
            try:
                payload = val.to_bytes(size, "little", signed=False)
                if timeout is None:
                    self.node.sdo.download(index, subindex, payload)
                    return
                try:
                    self.node.sdo.download(index, subindex, payload, timeout=to_s)
                    return
                except TypeError:
                    old_to = getattr(self.node.sdo, "timeout", None)
                    try:
                        if hasattr(self.node.sdo, "timeout") and to_s is not None:
                            self.node.sdo.timeout = to_s
                        self.node.sdo.download(index, subindex, payload)
                        return 
                    finally:
                        if hasattr(self.node.sdo, "timeout") and old_to is not None:
                            self.node.sdo.timeout = old_to
            except OverflowError:
                continue
            except SdoAbortedError as e:
                if (hasattr(e, "code") and e.code == 0x06070010) or "0x06070010" in str(e):
                    last_err = e
                    continue
                raise
            except Exception as e:
                last_err = e
                break
        raise RuntimeError(f"SDO write failed {index:04X}h/{subindex:02X}h -> {value}: {last_err}")

    def SdoRd(self, index, subindex):
        data = self.node.sdo.upload(index, subindex)
        return int.from_bytes(data, "little", signed=False)


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

# --- Load InitPar(d) and arity ---
def load_config_function(script_path):
    mod_name = os.path.splitext(os.path.basename(script_path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, script_path)
    if spec is None or spec.loader is None:
        print(f"[ERROR] Cannot load module from {script_path}")
        sys.exit(1)
    steer_mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = steer_mod
    spec.loader.exec_module(steer_mod)
    apply_fn = getattr(steer_mod, "InitPar", None)
    if not callable(apply_fn):
        print(f"[ERROR] {script_path} lacks callable InitPar(d)")
        sys.exit(1)
    try:
        arity = len(inspect.signature(apply_fn).parameters)
    except Exception:
        arity = 1
    print(f"[DBG] Loaded {steer_mod.__name__} from {steer_mod.__file__} | InitPar arity={arity}")
    return steer_mod, apply_fn, arity

# --- Parse Dsa(1) and new_node_id from the steering file text ---
def read_text(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def parse_dsa_node(src_text):
    m = re.search(r'\bDsa\s*\(\s*(\d+)\s*\)', src_text)
    return int(m.group(1)) if m else None

def parse_new_node_id(src_text):
    m = re.search(r'\bnew_node_id\s*=\s*(\d+)', src_text)
    return int(m.group(1)) if m else None

def main():
    script_path = import_script_via_qr()
    print(f"[INFO] Using script: {script_path}")
    steer_mod, apply_fn, arity = load_config_function(script_path)

    # pull optional constants (most likely None in your file)
    script_bitrate = getattr(steer_mod, "BITRATE", None)
    script_node    = getattr(steer_mod, "NODE", None)
    script_set_id  = getattr(steer_mod, "SET_NODE_ID", None)

    # parse Dsa(1) and new_node_id from the file itself
    src = read_text(script_path)
    parsed_node        = parse_dsa_node(src) 
         # e.g., 1 from Dsa(1)  <-- used as current Node-ID
    parsed_new_node_id = parse_new_node_id(src)    # e.g., 50 from new_node_id = 50

    # Effective values (no CLI in this variant): parsed > script constants > fallback
    bitrate     = script_bitrate if script_bitrate is not None else 250
    node        = parsed_node if parsed_node is not None else (script_node if script_node is not None else 59)
    set_node_id = parsed_new_node_id if parsed_new_node_id is not None else (script_set_id if script_set_id is not None else None)

    print(f"[INFO] Params -> BITRATE: {bitrate} kbit/s | NODE: {node} | SET_NODE_ID: {set_node_id}")

    # Bring up CAN with BITRATE from script
    can = DriverCan(can_bitrate=bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        print("[ERROR] Could not add CAN node.")
        print(parsed_node) 
        sys.exit(1)
    dsa = DSACompat(mic.added_node)

    print("[INFO] Applying configuration from steering script...")
    # Your SteeringScript.InitPar(d) takes 1 arg
    apply_fn(dsa)
    print("[INFO] Configuration applied successfully.")

    # Debug readback of Node-ID parameter (0x2000:02)
    try:
        val = dsa.SdoRd(0x2000, 0x02)
        print(f"[DBG] Readback 0x2000:02 (Node-ID param) = {val}")
    except Exception as e:
        print(f"[WARN] Could not read 0x2000:02 after config: {e}")

    # Reset so new Node-ID takes effect (if any)
    can.close_can()

if __name__ == "__main__":
    main()