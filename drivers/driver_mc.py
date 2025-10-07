# drivers/dsa_compat.py
"""
Compatibility wrapper for SDO read/write across different python-canopen versions.
"""

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
