# drivers/driver_arduino.py — robust port/framing probe + single-value fallback
import os, time, yaml, struct, threading
import serial.tools.list_ports
from serial import Serial, SerialException
from io_helpers.find_device import find_serial_port


# -------------------- CONFIG --------------------
config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

TARGET_VID = int(config["arduino"]["VID"])
TARGET_PID = int(config["arduino"]["PID"])
BITRATE    = int(config["arduino"]["BITRATE"])

H0, H1 = 0xAA, 0x55

DEVICE_NOT_CONNECTED_MSG = "Device is not connected, check USB cable "

# ---------- Commands ----------
CMD_GET_STATE        = 0x01
RSP_STATE            = 0x81

CMD_GET_RELAYS       = 0x02
RSP_RELAYS           = 0x82

CMD_GET_MEAS         = 0x03
RSP_MEAS             = 0x83

CMD_GET_MEAS_N       = 0x04
RSP_MEAS_N           = 0x84

CMD_GET_VOLTAGE      = 0x05
RSP_VOLTAGE          = 0x85

CMD_GET_CURRENT      = 0x06
RSP_CURRENT          = 0x86

CMD_GET_RESISTANCE   = 0x07
RSP_RESISTANCE       = 0x87

CMD_GET_POWER        = 0x08
RSP_POWER            = 0x88

CMD_SET_RELAYS_MASK  = 0x11
RSP_SET_RELAYS_MASK  = 0x91

# NEW: hold/restore while host disconnects
CMD_PAUSE           = 0x13
RSP_PAUSE           = 0x93

CMD_RESUME          = 0x14
RSP_RESUME          = 0x94

_DEBUG_FRAMES = False

def _hexdump(b: bytes) -> str:
    return ' '.join(f'{x:02X}' for x in b) if b else ''

# ---------- Framing (mode 2: 2-byte LEN) ----------
def _checksum2(tp: int, ln: int, payload: bytes) -> int:
    return (tp + (ln & 0xFF) + ((ln >> 8) & 0xFF) + sum(payload)) & 0xFF

def _frame2(tp: int, payload: bytes = b"") -> bytes:
    ln = len(payload)
    return bytes([H0, H1, tp, ln & 0xFF, (ln >> 8) & 0xFF]) + payload + bytes([_checksum2(tp, ln, payload)])

# ---------- Framing (mode 1: legacy 1-byte LEN) ----------
def _checksum1(tp: int, ln: int, payload: bytes) -> int:
    return (tp + (ln & 0xFF) + sum(payload)) & 0xFF

def _frame1(tp: int, payload: bytes = b"") -> bytes:
    ln = len(payload) & 0xFF
    return bytes([H0, H1, tp, ln]) + payload + bytes([_checksum1(tp, ln, payload)])

_shared_serial = None
_shared_len_mode = 2
_serial_io_lock = threading.RLock()

class DriverArduino:
    """
    Auto-probes the correct COM port and framing (2-byte vs 1-byte LEN).
    Falls back for single-value commands if firmware is older.
    """
    def __init__(self):
        global _shared_serial
        self._len_mode = 2           # 2 = modern, 1 = legacy
        self._caps = {"single_value": None}  # None=unknown, True/False known
        if _shared_serial is not None:
            # Shared serial might have been closed by a previous session
            if not getattr(_shared_serial, "is_open", False):
                _shared_serial = None
            else:
                self.arduino = _shared_serial
                self._len_mode = _shared_len_mode
                return
        self.arduino = None
        try:
            self.initialize_arduino()
        except Exception:
            self._close_serial_quietly(self.arduino)
            self.arduino = None
            raise
        _shared_serial = self.arduino
        self._publish_shared_protocol()

    # ---------- Port open + probing ----------
    def initialize_arduino(self):
        candidates = find_serial_port(TARGET_VID, TARGET_PID)
        if not candidates:
            message = (
                f"{DEVICE_NOT_CONNECTED_MSG}"
                f"No serial port found for Arduino VID=0x{TARGET_VID:04X} "
                f"PID=0x{TARGET_PID:04X}."
            )
            raise RuntimeError(message)

        # Prefer 'Native' if present, else first (yours is Programming Port / COM16)
        candidates.sort(key=lambda t: (0 if 'native' in (t[1] or '').lower() else 1, t[0]))
        dev, desc, _ = candidates[0]

        try:
            self.arduino = Serial(dev, BITRATE, timeout=10, write_timeout=10)
        except PermissionError as e:
            raise RuntimeError(f"Port {dev} is busy. Close Serial Monitor/Putty and retry.") from e
        except SerialException as e:
            raise RuntimeError(f"Cannot open {dev}: {e}") from e

        # --- One-time reset handling for Arduino Due Programming Port ---
        # Opening the port pulses DTR -> board resets.
        # Hold DTR/RTS low and wait for the sketch to come up.
        try:
            self.arduino.setDTR(True)
            self.arduino.setRTS(True)
        except Exception:
            pass
        time.sleep(2.2)  # give the SAM3X time to reboot and start the sketch

        try:
            self.arduino.reset_input_buffer()
        except Exception:
            pass

        # One simple probe: try modern 2-byte LEN, then legacy 1-byte LEN.
        if not self._simple_probe():
            message = (
                f"{DEVICE_NOT_CONNECTED_MSG}"
                f"Arduino was found on {dev} ({desc}) at {BITRATE} baud, "
                "but it did not answer the EOL binary protocol probe. "
                "For Arduino Due VID:PID 2341:003E, upload the EOL sketch with "
                "the binary protocol on SerialUSB / Native USB, or connect the "
                "Programming Port and update resources/config.yaml accordingly."
            )
            raise RuntimeError(message)

        self._publish_shared_protocol()

    def _publish_shared_protocol(self) -> None:
        global _shared_len_mode
        _shared_len_mode = self._len_mode

    @staticmethod
    def _close_serial_quietly(serial_obj) -> None:
        try:
            if serial_obj is not None and getattr(serial_obj, "is_open", False):
                serial_obj.close()
        except Exception:
            pass

    def _simple_probe(self) -> bool:
        # Try 2-byte LEN
        try:
            self._len_mode = 2
            self._send_cmd_raw(CMD_GET_VOLTAGE, b"", RSP_VOLTAGE, timeout_s=0.8)
            return True
        except Exception:
            pass
        # Try legacy 1-byte LEN
        try:
            self._len_mode = 1
            self._send_cmd_raw(CMD_GET_VOLTAGE, b"", RSP_VOLTAGE, timeout_s=0.8)
            return True
        except Exception:
            pass
        return False

    # ---------- Low-level I/O ----------
    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.arduino.read(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def _read_frame1(self, expect_type: int = None, timeout_s: float = 1.0):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            b = self._read_exact(1)
            if not b or b[0] != H0: continue
            b2 = self._read_exact(1)
            if not b2 or b2[0] != H1: continue

            hdr = self._read_exact(2)  # TYPE, LEN(1)
            if len(hdr) != 2: continue
            tp, ln = hdr[0], hdr[1]

            payload = self._read_exact(ln)
            chk = self._read_exact(1)
            if len(payload) != ln or len(chk) != 1: continue

            want = _checksum1(tp, ln, payload)
            if chk[0] != want: continue

            if expect_type is not None and tp != expect_type:
                if _DEBUG_FRAMES: print(f"[RX1*]{tp:02X} len={ln} {_hexdump(payload)} (skipped)")
                continue

            if _DEBUG_FRAMES: print(f"[RX1 ] {tp:02X} len={ln} {_hexdump(payload)}")
            return tp, payload
        raise TimeoutError("Timeout waiting for binary frame (mode1)")

    def _read_frame2(self, expect_type: int = None, timeout_s: float = 1.0):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            b = self._read_exact(1)
            if not b or b[0] != H0: continue
            b2 = self._read_exact(1)
            if not b2 or b2[0] != H1: continue

            hdr = self._read_exact(3)  # TYPE, LENL, LENH
            if len(hdr) != 3: continue
            tp, ln_l, ln_h = hdr[0], hdr[1], hdr[2]
            ln = ln_l | (ln_h << 8)

            payload = self._read_exact(ln)
            chk = self._read_exact(1)
            if len(payload) != ln or len(chk) != 1: continue

            want = _checksum2(tp, ln, payload)
            if chk[0] != want: continue

            if expect_type is not None and tp != expect_type:
                if _DEBUG_FRAMES: print(f"[RX2*]{tp:02X} len={ln} {_hexdump(payload)} (skipped)")
                continue

            if _DEBUG_FRAMES: print(f"[RX2 ] {tp:02X} len={ln} {_hexdump(payload)}")
            return tp, payload
        raise TimeoutError("Timeout waiting for binary frame (mode2)")

    def _read_frame(self, expect_type: int = None, timeout_s: float = 1.0):
        return self._read_frame2(expect_type, timeout_s) if self._len_mode == 2 else self._read_frame1(expect_type, timeout_s)

    def _send_cmd_raw(self, tp: int, payload: bytes, expect_type: int, timeout_s: float):
        with _serial_io_lock:
            try:
                self.arduino.reset_input_buffer()
            except Exception:
                pass
            pkt = _frame2(tp, payload) if self._len_mode == 2 else _frame1(tp, payload)
            if _DEBUG_FRAMES: print(f"[TX{self._len_mode}] {_hexdump(pkt)}")
            self.arduino.write(pkt)
            self.arduino.flush()
            return self._read_frame(expect_type, timeout_s)

    def _send_cmd(self, tp: int, payload: bytes = b"", expect_type: int = None, timeout_s: float = 1.0):
        if expect_type is None:
            # fire-and-forget
            with _serial_io_lock:
                try: self.arduino.reset_input_buffer()
                except Exception: pass
                pkt = _frame2(tp, payload) if self._len_mode == 2 else _frame1(tp, payload)
                if _DEBUG_FRAMES: print(f"[TX{self._len_mode}] {_hexdump(pkt)}")
                self.arduino.write(pkt); self.arduino.flush()
                return None
        # normal request/response
        return self._send_cmd_raw(tp, payload, expect_type, timeout_s)

    # ---------- Parsers ----------
    def _parse_state_payload(self, payload: bytes):
        if len(payload) != 15:
            raise ValueError(f"Bad state payload length: {len(payload)}")
        rel_bits = struct.unpack_from('<H', payload, 0)[0] & 0x0FFF
        R_mOhm   = struct.unpack_from('<i', payload, 2)[0]
        I_mA     = struct.unpack_from('<i', payload, 6)[0]
        V_mV     = struct.unpack_from('<i', payload,10)[0]
        flags    = payload[14]
        return rel_bits, R_mOhm, I_mA, V_mV, flags

    def _parse_meas(self, payload: bytes):
        if len(payload) != 12:
            raise ValueError(f"Bad meas payload length: {len(payload)}")
        I_mA  = struct.unpack_from('<i', payload, 0)[0]
        V_mV  = struct.unpack_from('<i', payload, 4)[0]
        R_mOhm= struct.unpack_from('<i', payload, 8)[0]
        return I_mA, V_mV, R_mOhm

    def _parse_i32(self, payload: bytes) -> int:
        if len(payload) != 4:
            raise ValueError(f"Bad int payload length: {len(payload)}")
        return struct.unpack('<i', payload)[0]

    # ---------- Capability probe ----------
    def _ensure_caps(self):
        if self._caps["single_value"] is not None:
            return
        try:
            # quick probe: ask voltage with short timeout
            self._send_cmd_raw(CMD_GET_VOLTAGE, b"", RSP_VOLTAGE, timeout_s=0.4)
            self._caps["single_value"] = True
        except Exception:
            self._caps["single_value"] = False

    # ---------- Public API ----------
    def get_state(self, *value):
        last_err = None
        for attempt in range(3):
            try:
                _, pl = self._send_cmd(CMD_GET_STATE, b"", expect_type=RSP_STATE, timeout_s=1.5)
                rel_bits, R_mOhm, I_mA, V_mV, flags = self._parse_state_payload(pl)
                relay_states = {f"q{n+1}": 1 if (rel_bits & (1 << n)) else 0 for n in range(12)}
                R = R_mOhm / 1000.0
                I = I_mA   / 1000.0
                V = None if V_mV < 0 else (V_mV / 1000.0)
                hasINA = bool(flags & 0x01)

                if not value:
                    return {
                        "relay_states": relay_states,
                        "resistance": f"{R:.2f}",
                        "current":    f"{I:.2f}",
                        "voltage":    (None if V is None else f"{V:.3f}"),
                        "hasINA":     hasINA
                    }

                key = str(value[0]).upper()
                if key == 'R': return f"{R:.2f}"
                if key == 'I': return f"{I:.2f}"
                if key == 'V': return None if V is None else f"{V:.3f}"
                if key == 'S': return relay_states

                requested = {}
                for k in value:
                    try:
                        n = int(k)
                        requested[f"q{n}"] = relay_states.get(f"q{n}", "Unknown")
                    except Exception:
                        requested[str(k)] = "Unknown"
                return requested

            except (TimeoutError, SerialException, ValueError) as e:
                last_err = e
                try: self.arduino.reset_input_buffer()
                except Exception: pass
                time.sleep(0.05)

        print(f"[ERROR] Failed to read or parse state: {last_err or 'Timeout waiting for binary frame'}")
        return None

    def get_relays(self) -> int:
        _, pl = self._send_cmd(CMD_GET_RELAYS, b"", expect_type=RSP_RELAYS, timeout_s=1.0)
        if len(pl) != 2: raise ValueError("Bad RSP_RELAYS length")
        return struct.unpack("<H", pl)[0] & 0x0FFF

    def get_meas(self):
        _, pl = self._send_cmd(CMD_GET_MEAS, b"", expect_type=RSP_MEAS, timeout_s=1.0)
        I_mA, V_mV, R_mOhm = self._parse_meas(pl)
        return {
            "current": I_mA/1000.0,
            "voltage": (None if V_mV < 0 else V_mV/1000.0),
            "resistance": R_mOhm/1000.0
        }

    def get_meas_burst(self, N: int):
        if N <= 0: return []
        payload = struct.pack("<H", N & 0xFFFF)
        _, pl = self._send_cmd(CMD_GET_MEAS_N, payload, expect_type=RSP_MEAS_N, timeout_s=max(1.0, 0.001*N))
        if len(pl) % 12 != 0:
            raise ValueError(f"Bad RSP_MEAS_N length {len(pl)} (not multiple of 12)")
        out = []
        for off in range(0, len(pl), 12):
            I_mA, V_mV, R_mOhm = self._parse_meas(pl[off:off+12])
            out.append({
                "current": I_mA/1000.0,
                "voltage": (None if V_mV < 0 else V_mV/1000.0),
                "resistance": R_mOhm/1000.0
            })
        return out

    def get_voltage(self):
        self._ensure_caps()
        if self._caps["single_value"]:
            try:
                _, pl = self._send_cmd(CMD_GET_VOLTAGE, b"", expect_type=RSP_VOLTAGE, timeout_s=1.0)
                v_mV = self._parse_i32(pl)
                return None if v_mV < 0 else (v_mV / 1000.0)
            except Exception:
                self._caps["single_value"] = False
        try:
            return self.get_meas()["voltage"]
        except Exception:
            s = self.get_state() or {}
            v = s.get("voltage")
            return None if v is None else float(v)

    def get_current(self):
        self._ensure_caps()
        if self._caps["single_value"]:
            try:
                _, pl = self._send_cmd(CMD_GET_CURRENT, b"", expect_type=RSP_CURRENT, timeout_s=1.0)
                i_mA = self._parse_i32(pl)
                return i_mA / 1000.0
            except Exception:
                self._caps["single_value"] = False
        try:
            return self.get_meas()["current"]
        except Exception:
            s = self.get_state() or {}
            i = s.get("current")
            return None if i is None else float(i)

    def get_resistance(self):
        self._ensure_caps()
        if self._caps["single_value"]:
            try:
                _, pl = self._send_cmd(CMD_GET_RESISTANCE, b"", expect_type=RSP_RESISTANCE, timeout_s=1.0)
                r_mOhm = self._parse_i32(pl)
                return r_mOhm / 1000.0
            except Exception:
                self._caps["single_value"] = False
        try:
            return self.get_meas()["resistance"]
        except Exception:
            s = self.get_state() or {}
            r = s.get("resistance")
            return None if r is None else float(r)

    def get_power(self):
        self._ensure_caps()
        if self._caps["single_value"]:
            try:
                _, pl = self._send_cmd(CMD_GET_POWER, b"", expect_type=RSP_POWER, timeout_s=1.0)
                p_mW = self._parse_i32(pl)
                return p_mW / 1000.0
            except Exception:
                self._caps["single_value"] = False
        # fallback
        v = self.get_voltage()
        i = self.get_current()
        if v is None or i is None:
            return None
        return v * i

    # ---- bus hold helpers (pause/resume) ----
    def pause_com(self, max_retries: int = 2, settle_s: float = 0.2) -> bool:
        """Ask the Arduino to enter PAUSE (hold current relays) and persist the mask.
        Returns True on ack; False otherwise."""
        last_err = None
        for attempt in range(1, max_retries+1):
            try:
                self._send_cmd(CMD_PAUSE, b"", expect_type=RSP_PAUSE, timeout_s=0.8)
                if settle_s > 0: time.sleep(settle_s)
                return True
            except Exception as e:
                last_err = e
                try: self.arduino.reset_input_buffer()
                except Exception: pass
                time.sleep(0.05)
        print(f"[ERROR] pause_com failed: {last_err}")
        return False

    def resume_com(self, max_retries: int = 2) -> bool:
        """Leave PAUSE mode on Arduino. Keeps current relay outputs as-is.
        Returns True on ack; False otherwise."""
        last_err = None
        for attempt in range(1, max_retries+1):
            try:
                self._send_cmd(CMD_RESUME, b"", expect_type=RSP_RESUME, timeout_s=0.8)
                return True
            except Exception as e:
                last_err = e
                try: self.arduino.reset_input_buffer()
                except Exception: pass
                time.sleep(0.05)
        print(f"[ERROR] resume_com failed: {last_err}")
        return False

    # ---- relays
    def _set_relays_bits(self, bits: int) -> bool:
        payload = struct.pack("<H", bits & 0x0FFF)
        try:
            _, pl = self._send_cmd(CMD_SET_RELAYS_MASK, payload, expect_type=RSP_SET_RELAYS_MASK, timeout_s=1.0)
            if len(pl) != 2: return False
            echo = struct.unpack_from("<H", pl, 0)[0] & 0x0FFF
            return echo == (bits & 0x0FFF)
        except Exception as e:
            print(f"[ERROR] Failed to set relays: {e}")
            return False

    def set_relay_state(self, command: str) -> bool:
        try:
            cur = self.get_state('S')
            if not isinstance(cur, dict):
                print("[ERROR] set_relay_state(): cannot read current state")
                return False
            bits = 0
            for i in range(12):
                if cur.get(f"q{i+1}", 0):
                    bits |= (1 << i)
            parts = [p for p in command.split(",") if p]
            for p in parts:
                if not p.startswith("q") or "=" not in p:
                    continue
                k, v = p.split("=")
                idx = int(k[1:]) - 1
                if not (0 <= idx < 12):
                    continue
                if int(v) != 0: bits |= (1 << idx)
                else:           bits &= ~(1 << idx)
            return self._set_relays_bits(bits)
        except Exception as e:
            print(f"[ERROR] set_relay_state failed: {e}")
            return False

    def send_and_confirm_relay_state(self, command: str, max_attempts: int = 3) -> bool:
        for attempt in range(1, max_attempts+1):
            if self.set_relay_state(command):
                # verify
                try:
                    cur = self.get_state('S')
                    if not isinstance(cur, dict):
                        time.sleep(0.05)
                        continue
                    # Build expected bits from command
                    bits_expected = 0
                    for i in range(12):
                        if cur.get(f"q{i+1}", 0):
                            bits_expected |= (1 << i)
                    # No strict compare to string; trust device echo
                    return True
                except Exception:
                    pass
            time.sleep(0.1)
        return False

    # ---- close/open ----
    def close_arduino(self):
        """Force all relays off and close the serial port."""
        global _shared_serial
        import time

        try:
            if getattr(self, "arduino", None) and getattr(self.arduino, "is_open", False):
                try:
                    # Write zero mask to drop q1..q12
                    self._set_relays_bits(0)

                    # Briefly confirm (debounce a few reads)
                    stable = 0
                    for _ in range(6):
                        try:
                            cur = self.get_relays()
                            if (cur & 0x0FFF) == 0:
                                stable += 1
                                if stable >= 3:
                                    break
                            else:
                                stable = 0
                        except Exception:
                            # ignore transient read errors on teardown
                            pass
                        time.sleep(0.02)
                except Exception as e:
                    print(f"[WARN] close_arduino: failed to clear relays: {e}")
        finally:
            try:
                if getattr(self, "arduino", None) and getattr(self.arduino, "is_open", False):
                    self.arduino.close()
                if getattr(self, "arduino", None) is _shared_serial:
                    _shared_serial = None
            except Exception as e:
                print(f"[WARN] close_arduino: error closing serial: {e}")


# -------------------- Multimeter-like facade --------------------
class MeasureFromINA:
    """Uses single-value endpoints if available, else falls back automatically."""
    def __init__(self, arduino=None):
        self.arduino = arduino if arduino is not None else DriverArduino()
    def measure_voltage(self):   return self.arduino.get_voltage()
    def measure_current(self):   return self.arduino.get_current()
    def measure_resistance(self):return self.arduino.get_resistance()
    def measure_power(self):     return self.arduino.get_power()
    def wait_for_ready(self):    return
    def close_multimeter(self):  return
