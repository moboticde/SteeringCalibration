#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, re, importlib.util, time
from typing import Optional, Dict, Any, Callable, Tuple


# ---------------- NMT reset helper (from FlashConfigFile.py) ------------------
def nmt_reset_node_compat(nmt) -> bool:
    try:
        nmt.reset_node()
        print("[INFO] NMT: reset_node() sent.")
        return True
    except AttributeError:
        pass
    try:
        nmt.reset_communication()
        print("[INFO] NMT: reset_communication() sent.")
        return True
    except Exception:
        pass
    for s in ("RESET NODE", "RESET"):
        try:
            nmt.state = s
            print(f"[INFO] NMT: state='{s}' sent.")
            return True
        except Exception:
            continue
    try:
        nmt.state = "PRE-OPERATIONAL"
        time.sleep(0.2)
        nmt.state = "OPERATIONAL"
        print("[INFO] NMT: toggled PRE-OPERATIONAL → OPERATIONAL.")
        return True
    except Exception:
        pass
    print("[WARN] Could not send any NMT reset command on this canopen version.")
    return False

# ---------------------------- core class --------------------------------------
class ConfigProcessing:
    """
    Load a product config script (Left/Right or SteeringScript), extract parameters,
    bring up CAN, and run its functions against a DSACompat wrapper.

    Usage examples:
        # 1) Direct path (Left/Right)
        cp = ConfigProcessing(script_path=r'...\01_SwConfiguration\\ConfigLeft V2.17-HW201.py')
        cp.apply()

        # 2) SteeringScript
        cp = ConfigProcessing(script_path=r'...\01_SwConfiguration\\SteeringScript.py', can_bitrate_kbit=250)
        cp.apply()
    """

    def __init__(
        self,
        script_path: Optional[str] = None,
        *,
        can_bitrate_kbit: Optional[int] = 250,
        override_node_id: Optional[int] = None,
        override_new_node_id: Optional[int] = None,
        override_baudrate: Optional[int] = None,
    ):
        self.script_path = script_path 
        if not self.script_path or not os.path.isfile(self.script_path):
            raise FileNotFoundError(f"No script found: {self.script_path}")

        self.can_bitrate_kbit = can_bitrate_kbit or 250
        self.overrides = {
            "current_node_id": override_node_id,
            "new_node_id": override_new_node_id,
            "baudrate": override_baudrate,
        }

        # Load module + raw text
        self.mod, self.src = self._import_module(self.script_path)
        # Detect kind & pick callable(s)
        self.kind, self.funcs = self._discover_functions(self.mod)
        # Extract parameters from module/contents
        self.params = self._extract_params(self.kind, self.mod, self.src)
        # Apply overrides
        for k, v in self.overrides.items():
            if v is not None:
                self.params[k] = int(v)

    @staticmethod
    def _import_module(path: str):
        name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load module from {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
        return mod, src

    @staticmethod
    def _discover_functions(mod) -> Tuple[str, Dict[str, Callable[..., Any]]]:
        # SteeringScript style
        if hasattr(mod, "InitPar") and callable(getattr(mod, "InitPar")):
            return "steering", {"InitPar": getattr(mod, "InitPar")}

        # Left/Right style functions
        candidates = {}
        for fn in ("TractionLeftPar", "TractionRightPar",
                   "TractionLeftCommPar", "TractionRightCommPar",
                   "Baudrate"):
            if hasattr(mod, fn) and callable(getattr(mod, fn)):
                candidates[fn] = getattr(mod, fn)
        if candidates:
            return "lr", candidates

        raise RuntimeError("Unsupported config module: no known functions found.")

    # -------------------- parameter extraction --------------------------------
    @staticmethod
    def _re_int_in(src: str, pattern: str) -> Optional[int]:
        m = re.search(pattern, src)
        return int(m.group(1), 0) if m else None

    def _extract_params(self, kind: str, mod, src: str) -> Dict[str, Any]:
        params = {"current_node_id": None, "new_node_id": None, "baudrate": None}

        if kind == "steering":
            # current node: Dsa(<id>) inside __main__ or explicit SpGp_NodeId(...)
            node = self._re_int_in(src, r"\bDsa\s*\(\s*(\d+)\s*\)")
            if node is None:
                node = self._re_int_in(src, r"\bSpGp_NodeId\s*\(\s*(0x[0-9A-Fa-f]+|\d+)\s*\)")
            # new node is a local in InitPar; parse from source (same as FlashConfigFile)
            new_id = self._re_int_in(src, r"\bnew_node_id\s*=\s*(\d+)")
            params["current_node_id"] = node if node is not None else 1
            params["new_node_id"] = new_id
            # baudrate: not defined in SteeringScript; we only set the CAN *bus* rate to connect
            # (device baud change would be via SDO 0x2000:03, but your script keeps that commented)
            params["baudrate"] = None
            return params

        # Left/Right: read easy module-level constants if present
        for name in ("CurrentLeftID", "CurrentRightID", "LeftNodeID", "RightNodeID", "baudrate"):
            if hasattr(mod, name):
                params[name] = getattr(mod, name)

        # normalize
        params["current_node_id"] = (
            params.get("CurrentLeftID")
            or params.get("CurrentRightID")
            or params.get("current_node_id")
            or 1
        )
        params["new_node_id"] = (
            params.get("LeftNodeID")
            or params.get("RightNodeID")
            or params.get("new_node_id")
        )
        params["baudrate"] = params.get("baudrate", None)
        return params

    # ---------------------------- execution -----------------------------------
    def summary(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "params": self.params,
            "can_bitrate_kbit": self.can_bitrate_kbit,
            "functions": list(self.funcs.keys()),
        }
