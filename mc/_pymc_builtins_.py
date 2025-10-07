# -*- coding: utf-8 -*-
# miControl MPU builtins adapted to your DriverCan + MicontrolF35 + DSACompat

import sys
import threading

# --- local pyx (timers) -------------------------------------------------------
if __package__:
    from . import pyx
else:
    import pyx

# --- bring in your drivers + DSA wrapper -------------------------------------
# Prefer drivers.dsa_compat.DSACompat if you extracted it;
# otherwise fall back to the in-file class from FlashConfigFile.
try:
    from drivers.driver_mc import DSACompat  # preferred
except Exception:
    try:
        from FlashConfigFile import DSACompat  # fallback if not extracted
    except Exception:
        DSACompat = None  # last resort; we’ll fail loudly later

try:
    from drivers.driver_can import DriverCan
    from drivers.driver_miControlF35 import MicontrolF35_CAN
except Exception as e:
    # We delay raising until the first SDO use, to allow import in tooling.
    _driver_import_error = e
else:
    _driver_import_error = None

# ==============================================================================
# Globals compatible with original miControl helpers
PYMC            = 0
PYMC_VERSION    = 0x00000000
MPU             = 0
MPU_VERSION     = 0x00000000

_SpGp_NodeId    = 1
_SpGp_Timeout   = 0xFFFF       # milliseconds
_SpGp_TxCobId   = 0xFFFFFFFF   # ignored in our shim
_SpGp_RxCobId   = 0xFFFFFFFF   # ignored in our shim

_SpxGpx_NodeId  = 1
_SpxGpx_Timeout = 0xFFFF
_SpxGpx_TxCobId = 0xFFFFFFFF
_SpxGpx_RxCobId = 0xFFFFFFFF

# ==============================================================================
# Minimal “mc.Can” shim that talks via your DSACompat
# --- add (or replace) this _CanShim in mc/_pymc_builtins_.py ---
class _CanShim:
    """
    Minimal shim: you attach an existing DSA wrapper + node_id,
    and MPU helpers (Gp/Sp/Spx/Gpx) call SDOs through it.
    """
    def __init__(self):
        self._dsa = None
        self._node_id = None

    def attach(self, dsa, node_id: int):
        """Call this from FlashMPUFile after you create DSACompat."""
        self._dsa = dsa
        self._node_id = int(node_id)

    def _ensure_node(self, node_id: int):
        if self._dsa is None:
            raise RuntimeError("mc.Can is not attached — call Can.attach(dsa, node_id) first.")
        # If MPU calls with a different node, we just warn and keep going.
        if self._node_id is not None and int(node_id) != self._node_id:
            # Optional: raise instead of warn if you want to be strict.
            print(f"[WARN] mc.Can: requested node {node_id} != attached node {self._node_id}")

    def SdoWr(self, node_id, index, subindex, value, timeout_ms, *_cobs_ignored):
        self._ensure_node(int(node_id))
        # DSACompat already handles timeout if you pass seconds; ignore if not needed.
        to_s = (timeout_ms / 1000.0) if isinstance(timeout_ms, (int, float)) else None
        self._dsa.SdoWr(int(index), int(subindex), int(value), timeout=to_s)

    def SdoRd(self, node_id, index, subindex, timeout_ms, *_cobs_ignored):
        self._ensure_node(int(node_id))
        return int(self._dsa.SdoRd(int(index), int(subindex)))

# keep the public instance
Can = _CanShim()


# ==============================================================================
# Original convenience wrappers (Sp/Gp/Spx/Gpx + config setters)

def Sp(index, subindex, value):
    global _SpGp_NodeId, _SpGp_Timeout, _SpGp_TxCobId, _SpGp_RxCobId
    Can.SdoWr(_SpGp_NodeId, index, subindex, value, _SpGp_Timeout, _SpGp_TxCobId, _SpGp_RxCobId)

def Gp(index, subindex):
    global _SpGp_NodeId, _SpGp_Timeout, _SpGp_TxCobId, _SpGp_RxCobId
    return Can.SdoRd(_SpGp_NodeId, index, subindex, _SpGp_Timeout, _SpGp_TxCobId, _SpGp_RxCobId)

def SpGp_NodeId(node_id):
    global _SpGp_NodeId
    _SpGp_NodeId = int(node_id)

def SpGp_Timeout(time_ms):
    global _SpGp_Timeout
    _SpGp_Timeout = int(time_ms)

def SpGp_TxCobId(tx_cob_id):
    global _SpGp_TxCobId
    _SpGp_TxCobId = int(tx_cob_id)

def SpGp_RxCobId(rx_cob_id):
    global _SpGp_RxCobId
    _SpGp_RxCobId = int(rx_cob_id)

# ------------------------------------------------------------------------------

def Spx(a1, a2, a3, a4=None):
    global _SpxGpx_NodeId, _SpxGpx_Timeout, _SpxGpx_TxCobId, _SpxGpx_RxCobId
    if a4 is None:                   # Spx(index, subindex, value)
        node_id, index, subindex, value = _SpxGpx_NodeId, a1, a2, a3
    else:                            # Spx(node_id, index, subindex, value)
        node_id, index, subindex, value = a1, a2, a3, a4
    Can.SdoWr(node_id, index, subindex, value, _SpxGpx_Timeout, _SpxGpx_TxCobId, _SpxGpx_RxCobId)

def Gpx(a1, a2, a3=None):
    global _SpxGpx_NodeId, _SpxGpx_Timeout, _SpxGpx_TxCobId, _SpxGpx_RxCobId
    if a3 is None:                   # Gpx(index, subindex)
        node_id, index, subindex = _SpxGpx_NodeId, a1, a2
    else:                            # Gpx(node_id, index, subindex)
        node_id, index, subindex = a1, a2, a3
    return Can.SdoRd(node_id, index, subindex, _SpxGpx_Timeout, _SpxGpx_TxCobId, _SpxGpx_RxCobId)

def SpxGpx_NodeId(node_id):
    global _SpxGpx_NodeId
    _SpxGpx_NodeId = int(node_id)

def SpxGpx_Timeout(time_ms):
    global _SpxGpx_Timeout
    _SpxGpx_Timeout = int(time_ms)

def SpxGpx_TxCobId(tx_cob_id):
    global _SpxGpx_TxCobId
    _SpxGpx_TxCobId = int(tx_cob_id)

def SpxGpx_RxCobId(rx_cob_id):
    global _SpxGpx_RxCobId
    _SpxGpx_RxCobId = int(rx_cob_id)

# ==============================================================================
# Timing/math helpers expected by MPU scripts
def Delay(time_ms):
    pyx.sleep(time_ms / 1000.0)

def Clock():
    return int(pyx.clock() * 1000)

def DiffClock(timestamp):
    return int(Clock() - int(timestamp))

def Scale(value, nominator, denominator):
    return int(round(value * (float(nominator) / float(denominator))))

def ScaleDbl(value, nominator, denominator):
    return int(round(value * (float(nominator) / float(denominator))))

# ==============================================================================
# Stubs kept for compatibility
def DefUserVar(name, value, descr="", min_value=0x00000000, max_value=0xFFFFFFFF):
    if sys.version_info < (3, 0, 0):
        import __builtin__  # pylint: disable=import-error
        exec("__builtin__.%s = %d" % (name, value))
    else:
        import builtins     # pylint: disable=import-error
        exec("builtins.%s = %d" % (name, value))

def Addr(name): return 0
def Boost(steps=10): pass
def BoostShot(steps=10): pass
def MpuSet(nr, value): pass
def MpuGet(nr): return 0
