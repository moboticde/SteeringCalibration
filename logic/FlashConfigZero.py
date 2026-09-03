import ctypes
from ctypes import c_uint8, c_uint32, c_bool, c_char_p, c_void_p, POINTER, byref
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
from utils.interrupt_guard import install_deferred_keyboard_interrupt
from drivers.driver_miControlF35 import MicontrolF35_CAN
from drivers.driver_can import DriverCan
from drivers.driver_cam_st import AngleDetection


DLL_PATH = Path("/home/mobotic/Internal Projects/StCalibration-Linux/MU/MU_3SL_interface_3.4.1/bin/linux/x86_64/libMU_3SL_interface.so.3.4.1")
STEERING_ENCODER_CONFIG_PATH = Path("/home/mobotic/Internal Projects/StCalibration-Linux/resources/ic-mu_steering_encoder_front.cfg")
CONFIG_PATH_0 = str(STEERING_ENCODER_CONFIG_PATH).encode("utf-8")
ZERO_CONFIG_PATH = Path("/home/mobotic/Internal Projects/StCalibration-Linux/resources/ic_mu_miControl_enc.cfg")
ENCODER_MUX_STATES = ((1, True), (2, False))
ZERO_PRESET_PLAN = (
    (1, ENCODER_MUX_STATES[0][1], ZERO_CONFIG_PATH, 0),
    (2, ENCODER_MUX_STATES[1][1], ZERO_CONFIG_PATH, 0),
)
LOAD_CONFIG_OPEN_ATTEMPTS = 3
LOAD_CONFIG_MUX_SETTLE_S = 0.5
CONFIG_BACKUP_DIR = Path("/home/mobotic/Internal Projects/StCalibration-Linux/MU/config_backups")
ZERO_VISUAL_SCALE_CACHE_PATH = CONFIG_BACKUP_DIR / "visual_zero_motion_scale_cache.json"
MICON_POSITION_MIN = -(2**31)
MICON_POSITION_MAX = 2**31 - 1
ZERO_CAMERA_SETTLE_S = 2.0
ZERO_POSITION_TOLERANCE_COUNTS = 3
ZERO_VISUAL_TOLERANCE_DEG = 1.0
ZERO_VISUAL_MEASUREMENT_FLUCTUATION_TOLERANCE_DEG = 1.0
ZERO_CONTROLLER_VERIFY_TIMEOUT_S = 5.0
ZERO_CONTROLLER_VERIFY_POLL_S = 0.25
ZERO_VISUAL_MAX_CORRECTIONS = 8
ZERO_VISUAL_MOVE_RPM = 500
ZERO_VISUAL_FINE_MOVE_RPM = 200
ZERO_VISUAL_FINE_STEP_DEG = 10.0
ZERO_VISUAL_MAX_STEP_DEG = 60.0
ZERO_VISUAL_MIN_STEP_DEG = 5.0
ZERO_VISUAL_BAD_FEEDBACK_STEP_FACTOR = 0.5
ZERO_VISUAL_GOOD_FEEDBACK_STEP_FACTOR = 1.25
ZERO_VISUAL_MIN_FEEDBACK_DEG = 2.0
ZERO_VISUAL_MIN_FEEDBACK_COUNTS = 2
ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV = 4096.0
ZERO_VISUAL_MIN_DIRECT_ENCODER_FEEDBACK_COUNTS = 2.0
ZERO_VISUAL_SCALE_PROBE_COUNTS = 3
ZERO_VISUAL_SCALE_PROBE_RPM = 200
ZERO_VISUAL_MIN_CONTROLLER_COUNTS_PER_REV = 20.0
ZERO_VISUAL_MAX_CONTROLLER_COUNTS_PER_REV = 10000.0
ZERO_VISUAL_FALLBACK_CONTROLLER_COUNTS_PER_REV = 4096.0
ZERO_VISUAL_EXPECTED_SCALE_CENTERS = (170.0, 4096.0, 8192.0)
ZERO_VISUAL_EXPECTED_SCALE_REL_TOL = 0.25
ZERO_VISUAL_FEEDBACK_MISMATCH_MIN_RATIO = 0.25
ZERO_VISUAL_FEEDBACK_MISMATCH_MAX_RATIO = 2.0
ZERO_VISUAL_STALE_CAMERA_REREADS = 3
ZERO_VISUAL_MOVE_SETTLE_TIMEOUT_S = 8.0
ZERO_VISUAL_MOVE_SETTLE_POLL_S = 0.2
ZERO_VISUAL_MOVE_SETTLE_VELOCITY = 1
ZERO_POWER_CYCLE_CONFIRM_TIMEOUT_S = 600.0
CONTROLLER_SSI_READY_STATUS = 9
CONTROLLER_SSI_POSITION_VALID_STATUSES = frozenset({3, CONTROLLER_SSI_READY_STATUS})

mu = ctypes.CDLL(str(DLL_PATH))

MU_Handle = c_void_p
MU_Error  = c_uint32
MU_MB5U   = c_uint32(4)

# MU enums / constants
MU_CMD_SOFT_E2P_PRES = c_uint32(9)

MU_PRES_POS  = c_uint32(68)
MU_OFF_POS   = c_uint32(57)
MU_OFF_ABZ   = c_uint32(56)
MU_OFF_COM   = c_uint32(58)
MU_OFF_UVW   = c_uint32(67)
MU_I2C_DEVID_PARAM_INDEX = 90
MU_I2C_RETRY_PARAM_INDEX = 91
MU_HARD_REV_PARAM_INDEX = 92

MU_VERIFY    = c_uint32(2)
MU_WRITE     = c_uint32(1)
MU_SETONLY   = c_uint32(0)
MU_E2P_CFG   = c_uint32(0)

MU_MODEA     = c_uint32(16)
MU_BISS      = c_uint32(0x0002)
MU_SSI       = c_uint32(0x0004)

MU_OK        = 0
MU_FORCED_REV = 0x20  # known chip revision
MU_STABLE_CONFIG_PARAM_LAST = 100  # Excludes EEPROM CRC and live measurement/status values.
MU_MIN_STABLE_CONFIG_PARAMS = 50
MU_SESSION_NORMALIZED_PARAM_INDEXES = frozenset(
    {
        MU_MODEA.value,
        MU_OFF_POS.value,
        MU_I2C_DEVID_PARAM_INDEX,
        MU_I2C_RETRY_PARAM_INDEX,
        MU_HARD_REV_PARAM_INDEX,
    }
)
MU_POST_POWER_CYCLE_DERIVED_PARAM_INDEXES = frozenset(
    {
        MU_MODEA.value,
        MU_OFF_POS.value,
        MU_OFF_COM.value,
        MU_HARD_REV_PARAM_INDEX,
    }
)

MU_ERROR_NAMES = {
    0:  "MU_OK",
    1:  "MU_INVALID_HANDLE",
    2:  "MU_INTERFACEDRIVER_NOT_FOUND",
    3:  "MU_INTERFACE_NOT_FOUND",
    4:  "MU_INVALID_INTERFACE",
    5:  "MU_NO_INTERFACE_SELECTED",
    6:  "MU_INVALID_PARAMETER",
    7:  "MU_INVALID_ADDRESS",
    8:  "MU_INVALID_VALUE",
    9:  "MU_USB_ERROR",
    10: "MU_FILE_NOT_FOUND",
    11: "MU_INVALID_FILE",
    12: "MU_SPI_ERROR",
    13: "MU_SPI_DISMISS",
    14: "MU_SPI_FAIL",
    15: "MU_SPI_BUSY_TIMEOUT",
    16: "MU_VERIFY_FAILED",
    17: "MU_MASTERCOMM_FAILED",
    18: "MU_BISSCOMM_FAILED",
    19: "MU_INVALID_BISSMASTER",
    20: "MU_USB_HIGHSPEED_WARNING",
    21: "MU_FAST_ROTATION",
    22: "MU_SLOW_ROTATION",
    23: "MU_FILE_ACCESS_DENIED",
    24: "MU_READPARAM_SSI",
    25: "MU_SSIRING_ERROR",
    26: "MU_SEMI_ROTATION",
    27: "MU_BISS_REGERROR",
    28: "MU_INTERNAL_CALIB_ERROR",
    29: "MU_INVALID_CONFIGURATION",
    30: "MU_CALIBRATION_FAILED",
    31: "MU_ACQUISITION_FAILED",
    32: "MU_GAIN_LIMIT",
    33: "MU_OFFSET_LIMIT",
    34: "MU_PHASE_LIMIT",
    35: "MU_BAD_CAL_DATA",
    36: "MU_I2C_COMM_FAILED",
    37: "MU_USB_DATA_LOSS",
    38: "MU_MT_SYNC_FAILED",
    39: "MU_UNKNOWN_ERROR",
    40: "MU_UNKNOWN_REVISION",
    41: "MU_UNSUPPORTED_REVISION",
    42: "MU_UNKNOWN_PARAMETER",
    43: "MU_PARAMETER_NOT_IN_REVISION",
    44: "MU_REVISION_NOT_SET",
    45: "MU_UNSUPPORTED_CHIP",
    46: "MU_CONTRADICTORY_REVISIONS",
    47: "MU_FRAME_RATE_NOT_SUPPORTED",
    48: "MU_CLOCK_FREQUENCY_NOT_SUPPORTED",
    49: "MU_FRAME_CYCLE_TIME_TO_SHORT",
    50: "MU_NO_BISS_PROFILE_ID",
    51: "MU_ADAPTER_FIRMWARE_INCOMPATIBLE",
}

MU_ERROR_TYPE_NAMES = {
    0: "MU_NONE",
    1: "MU_HINT",
    2: "MU_WARNING",
    3: "MU_PROGRAMMING_ERROR",
    4: "MU_OPERATING_ERROR",
    5: "MU_COMMUNICATION_ERROR",
}

# ---- prototypes ----
mu.MU_Open.argtypes  = [POINTER(MU_Handle)]
mu.MU_Open.restype   = MU_Error
mu.MU_Close.argtypes = [MU_Handle]
mu.MU_Close.restype  = MU_Error

mu.MU_SetInterface.argtypes = [MU_Handle, c_uint32, c_char_p]
mu.MU_SetInterface.restype  = MU_Error

mu.MU_SetParam.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32, c_uint32]
mu.MU_SetParam.restype  = MU_Error

mu.MU_GetParam.argtypes = [MU_Handle, c_uint32, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_GetParam.restype  = MU_Error

mu.MU_WriteParams.argtypes = [MU_Handle, c_bool, POINTER(c_bool)]
mu.MU_WriteParams.restype  = MU_Error

mu.MU_WriteEeprom.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteEeprom.restype  = MU_Error

mu.MU_LoadParams.argtypes  = [MU_Handle, c_char_p]
mu.MU_LoadParams.restype   = MU_Error

mu.MU_SaveParams.argtypes  = [MU_Handle, c_char_p]
mu.MU_SaveParams.restype   = MU_Error

mu.MU_CalcPRES_POS.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32]
mu.MU_CalcPRES_POS.restype  = MU_Error

mu.MU_GetPRES_POS.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_GetPRES_POS.restype  = MU_Error

mu.MU_WriteCmdRegister.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteCmdRegister.restype  = MU_Error

# revision APIs
mu.MU_ReadChipRevisionOfParameterFile.argtypes = [MU_Handle, c_char_p, POINTER(c_uint8)]
mu.MU_ReadChipRevisionOfParameterFile.restype  = MU_Error

mu.MU_UseRevision.argtypes = [MU_Handle, c_uint8]
mu.MU_UseRevision.restype  = MU_Error

mu.MU_ReadParams.argtypes = [MU_Handle]
mu.MU_ReadParams.restype  = MU_Error

# BiSS + IO
mu.MU_SwitchToBiss.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_SwitchToBiss.restype  = MU_Error

mu.MU_Initialize.argtypes = [MU_Handle]
mu.MU_Initialize.restype  = MU_Error

mu.MU_SwitchToBiss_ex.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_bool)]
mu.MU_SwitchToBiss_ex.restype = MU_Error

mu.MU_GetLastError.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32), c_char_p]
mu.MU_GetLastError.restype  = MU_Error

def _mu_last_error(handle) -> str:
    last_error = c_uint32(0)
    err_type   = c_uint32(0)
    buf        = ctypes.create_string_buffer(1024)
    mu.MU_GetLastError(handle, byref(last_error), byref(err_type), buf)
    err_code = int(last_error.value)
    err_type_code = int(err_type.value)
    err_name = MU_ERROR_NAMES.get(err_code, f"#{err_code}")
    type_name = MU_ERROR_TYPE_NAMES.get(err_type_code, f"#{err_type_code}")
    return f"code={err_code}({err_name}) type={err_type_code}({type_name}) text='{buf.value.decode(errors='ignore')}'"

def _log_mu(desc: str, ret: int, handle=None) -> None:
    """Log MU return code and include last-error info if available."""
    if ret != MU_OK:
        name = MU_ERROR_NAMES.get(int(ret), f"#{int(ret)}")
        extra = f" ({_mu_last_error(handle)})" if handle else ""
        print(f"[ERROR] {desc} failed (code={int(ret)}:{name}){extra}")
    else:
        print(desc)

def _enter_biss(handle) -> bool:
    """Try all available BiSS entry paths (switch_ex, switch, setparam verify/write)."""
    attempts = [
        ("SwitchToBiss_ex", lambda: mu.MU_SwitchToBiss_ex(handle, byref(c_uint32(MU_BISS.value)), byref(c_bool(False)))),
        ("SwitchToBiss",    lambda: mu.MU_SwitchToBiss(handle, byref(c_uint32(MU_BISS.value)), byref(c_uint32(0)))),
        ("SetParam MODEA verify", lambda: mu.MU_SetParam(handle, MU_MODEA, 0, MU_BISS, MU_VERIFY)),
        ("SetParam MODEA write",  lambda: mu.MU_SetParam(handle, MU_MODEA, 0, MU_BISS, MU_WRITE)),
    ]
    for idx, (name, fn) in enumerate(attempts, 1):
        ret = fn()
        _log_mu(f"{name} (attempt {idx})", ret, handle)
        if ret == MU_OK:
            print("Set BiSS")
            return True
        time.sleep(0.05 * idx)
    return False


def _visual_zero_error_deg(target_deg: float, current_deg: float) -> float:
    """Literal visual-zero error: desired angle minus current camera angle."""
    return float(target_deg) - float(current_deg)


def _visual_angle_distance_deg(target_deg: float, current_deg: float) -> float:
    """Shortest signed distance between two camera angles for verification."""
    return (float(target_deg) - float(current_deg) + 180.0) % 360.0 - 180.0


def _visual_zero_target_error_deg(target_deg: float, current_deg: float) -> float:
    """Signed visual error used for zero-write acceptance."""
    return _visual_angle_distance_deg(target_deg, current_deg)


@dataclass(frozen=True)
class VisualZeroTargetCheck:
    angle_deg: float
    target_deg: float
    error_deg: float
    tolerance_deg: float

    @property
    def ok(self) -> bool:
        return abs(self.error_deg) <= self.tolerance_deg


def _check_visual_zero_target(
    target_deg: float,
    current_deg: float,
    tolerance_deg: float = ZERO_VISUAL_TOLERANCE_DEG,
) -> VisualZeroTargetCheck:
    angle_deg = float(current_deg) % 360.0
    target_deg = float(target_deg) % 360.0
    return VisualZeroTargetCheck(
        angle_deg=angle_deg,
        target_deg=target_deg,
        error_deg=_visual_zero_target_error_deg(target_deg, angle_deg),
        tolerance_deg=float(tolerance_deg),
    )


def _visual_zero_is_within_target_tolerance(
    target_deg: float,
    current_deg: float,
    tolerance_deg: float = ZERO_VISUAL_TOLERANCE_DEG,
) -> bool:
    return _check_visual_zero_target(target_deg, current_deg, tolerance_deg).ok


def _visual_zero_reached(
    target_deg: float,
    current_deg: float,
    relaxed_tolerance_deg: float,
    *,
    require_strict_target: bool,
) -> bool:
    if _visual_zero_is_within_target_tolerance(target_deg, current_deg):
        return True
    if require_strict_target:
        return False
    return abs(_visual_zero_error_deg(target_deg, current_deg)) <= float(relaxed_tolerance_deg)


def _limit_visual_step_deg(error_deg: float, max_step_deg: float) -> float:
    """Split large visual corrections into bounded moves."""
    error_deg = float(error_deg)
    max_step_deg = max(float(max_step_deg), ZERO_VISUAL_MIN_STEP_DEG)
    if abs(error_deg) <= max_step_deg:
        return error_deg
    return math.copysign(max_step_deg, error_deg)


def _next_visual_step_limit_deg(current_limit_deg: float, feedback_plausible: bool) -> float:
    """Adjust the next visual step limit from feedback quality."""
    current_limit_deg = max(float(current_limit_deg), ZERO_VISUAL_MIN_STEP_DEG)
    if feedback_plausible:
        return min(
            ZERO_VISUAL_MAX_STEP_DEG,
            current_limit_deg * ZERO_VISUAL_GOOD_FEEDBACK_STEP_FACTOR,
        )
    return max(
        ZERO_VISUAL_MIN_STEP_DEG,
        current_limit_deg * ZERO_VISUAL_BAD_FEEDBACK_STEP_FACTOR,
    )


def _visual_correction_counts(step_error_deg: float, controller_counts_per_rev: float) -> int:
    """Convert a visual correction into at least one signed controller count."""
    raw_counts = float(step_error_deg) / 360.0 * float(controller_counts_per_rev)
    correction_counts = int(round(raw_counts))
    if correction_counts != 0:
        return correction_counts
    if raw_counts == 0:
        return 0
    return 1 if raw_counts > 0 else -1


def _visual_acceptance_tolerance_deg(controller_counts_per_rev: float) -> float:
    """Tolerance adjusted for the current controller position resolution."""
    if controller_counts_per_rev == 0 or not math.isfinite(controller_counts_per_rev):
        return ZERO_VISUAL_TOLERANCE_DEG
    half_count_deg = 180.0 / abs(float(controller_counts_per_rev))
    return max(ZERO_VISUAL_TOLERANCE_DEG, half_count_deg)


def _controller_counts_per_rev_is_valid(counts_per_rev: float) -> bool:
    return (
        math.isfinite(float(counts_per_rev))
        and ZERO_VISUAL_MIN_CONTROLLER_COUNTS_PER_REV
        <= abs(float(counts_per_rev))
        <= ZERO_VISUAL_MAX_CONTROLLER_COUNTS_PER_REV
    )


def _visual_scale_cache_key(mic) -> str:
    node_id = getattr(mic, "node_id", None)
    if node_id is None:
        return "default"
    return f"node_{int(node_id)}"


def _load_visual_scale_cache() -> dict:
    if not ZERO_VISUAL_SCALE_CACHE_PATH.is_file():
        return {}
    try:
        with ZERO_VISUAL_SCALE_CACHE_PATH.open("r", encoding="utf-8") as fh:
            cache = json.load(fh)
    except Exception as exc:
        print(f"[WARN] Could not read visual-zero scale cache: {exc}")
        return {}
    if not isinstance(cache, dict):
        print("[WARN] Ignoring visual-zero scale cache with unexpected format.")
        return {}
    return cache


def _cached_visual_controller_counts_per_rev(mic) -> float | None:
    cache = _load_visual_scale_cache()
    entry = cache.get(_visual_scale_cache_key(mic))
    if not isinstance(entry, dict):
        return None
    counts_per_rev = entry.get("controller_counts_per_rev")
    if counts_per_rev is None:
        return None
    try:
        counts_per_rev = float(counts_per_rev)
    except (TypeError, ValueError):
        return None
    if not _controller_counts_per_rev_is_valid(counts_per_rev):
        print(
            "[WARN] Ignoring invalid cached visual-zero scale: "
            f"{counts_per_rev!r} counts/rev"
        )
        return None
    if not _scale_is_near_expected_region(counts_per_rev):
        print(
            "[WARN] Ignoring stale cached visual-zero scale outside expected regions: "
            f"{counts_per_rev:.3f} counts/rev key={_visual_scale_cache_key(mic)}"
        )
        return None
    print(
        "[INFO] Visual-zero initial scale from cache: "
        f"{counts_per_rev:.3f} counts/rev key={_visual_scale_cache_key(mic)}"
    )
    return counts_per_rev


def _store_visual_controller_counts_per_rev(mic, counts_per_rev: float) -> None:
    counts_per_rev = float(counts_per_rev)
    if not _controller_counts_per_rev_is_valid(counts_per_rev):
        return
    cache = _load_visual_scale_cache()
    cache[_visual_scale_cache_key(mic)] = {
        "controller_counts_per_rev": counts_per_rev,
        "updated_unix_s": time.time(),
    }
    try:
        ZERO_VISUAL_SCALE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ZERO_VISUAL_SCALE_CACHE_PATH.open("w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except Exception as exc:
        print(f"[WARN] Could not write visual-zero scale cache: {exc}")


def _seed_visual_controller_counts_per_rev(mic) -> tuple[float, bool, bool]:
    """Return initial scale, whether it came from cache, and whether to probe it."""
    cached_counts_per_rev = _cached_visual_controller_counts_per_rev(mic)
    if cached_counts_per_rev is not None:
        return cached_counts_per_rev, True, False

    if hasattr(mic, "get_ssi_single_turn_resolution"):
        try:
            resolution = mic.get_ssi_single_turn_resolution()
        except Exception as exc:
            print(f"[WARN] Could not read controller SSI resolution for visual-zero seed: {exc}")
        else:
            if resolution is not None and _controller_counts_per_rev_is_valid(float(resolution)):
                print(
                    "[INFO] Visual-zero initial scale from controller SSI resolution: "
                    f"{float(resolution):.3f} counts/rev"
                )
                counts_per_rev = float(resolution)
                return (
                    counts_per_rev,
                    False,
                    not _scale_is_near_expected_region(counts_per_rev),
                )
            print(
                "[WARN] Controller SSI resolution is unavailable or invalid for visual-zero seed: "
                f"{resolution}; using fallback {ZERO_VISUAL_FALLBACK_CONTROLLER_COUNTS_PER_REV:.3f} counts/rev."
            )

    print(
        "[INFO] Visual-zero initial scale fallback: "
        f"{ZERO_VISUAL_FALLBACK_CONTROLLER_COUNTS_PER_REV:.3f} counts/rev"
    )
    return ZERO_VISUAL_FALLBACK_CONTROLLER_COUNTS_PER_REV, False, True


def _initial_visual_controller_counts_per_rev(mic) -> float:
    """Seed visual motion scale before the first move, without probing."""
    counts_per_rev, _from_cache, _should_probe = _seed_visual_controller_counts_per_rev(mic)
    return counts_per_rev


def _plan_visual_zero_move(
    error_deg: float,
    controller_counts_per_rev: float,
    max_step_deg: float,
) -> tuple[float, float, int, float]:
    """Plan one bounded visual-zero move.

    Returns step_error_deg, correction_revolutions, correction_counts, and
    expected_visual_delta_deg.
    """
    step_error_deg = _limit_visual_step_deg(error_deg, max_step_deg)
    correction_revolutions = step_error_deg / 360.0
    correction_counts = _visual_correction_counts(
        step_error_deg,
        controller_counts_per_rev,
    )
    if controller_counts_per_rev == 0:
        expected_visual_delta_deg = 0.0
    else:
        expected_visual_delta_deg = correction_counts / controller_counts_per_rev * 360.0
    return (
        step_error_deg,
        correction_revolutions,
        correction_counts,
        expected_visual_delta_deg,
    )


def _visual_motion_delta_deg(
    after_deg: float,
    before_deg: float,
    expected_delta_deg: float,
) -> float:
    """Choose the camera delta that best matches the commanded visual move."""
    after_deg = float(after_deg) % 360.0
    before_deg = float(before_deg) % 360.0
    raw_delta = after_deg - before_deg
    candidates = (raw_delta, raw_delta + 360.0, raw_delta - 360.0)
    return min(candidates, key=lambda candidate: abs(candidate - float(expected_delta_deg)))


def _single_turn_delta_counts(
    after_counts: int,
    before_counts: int,
    counts_per_rev: float,
    expected_delta_counts: float,
) -> float:
    """Choose the encoder single-turn delta that best matches the expected move."""
    counts_per_rev = float(counts_per_rev)
    raw_delta = float(after_counts) - float(before_counts)
    candidates = (raw_delta, raw_delta + counts_per_rev, raw_delta - counts_per_rev)
    return min(candidates, key=lambda candidate: abs(candidate - float(expected_delta_counts)))


def _candidate_controller_counts_per_rev_from_encoder(
    moved_controller_counts: int,
    moved_encoder_counts: float,
) -> float | None:
    """Return a controller scale estimate from direct SSI encoder movement."""
    if abs(float(moved_controller_counts)) < ZERO_VISUAL_MIN_FEEDBACK_COUNTS:
        return None
    if abs(float(moved_encoder_counts)) < ZERO_VISUAL_MIN_DIRECT_ENCODER_FEEDBACK_COUNTS:
        return None
    candidate = (
        int(moved_controller_counts)
        / float(moved_encoder_counts)
        * ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV
    )
    if not _controller_counts_per_rev_is_valid(candidate):
        return None
    return candidate


def _scale_is_near_expected_region(counts_per_rev: float) -> bool:
    scale = abs(float(counts_per_rev))
    return any(
        abs(scale - center) <= center * ZERO_VISUAL_EXPECTED_SCALE_REL_TOL
        for center in ZERO_VISUAL_EXPECTED_SCALE_CENTERS
    )


def _scale_update_is_plausible(
    new_counts_per_rev: float,
    measured_delta_deg: float,
    expected_delta_deg: float,
) -> bool:
    return _scale_update_rejection_reason(
        new_counts_per_rev,
        measured_delta_deg,
        expected_delta_deg,
    ) is None


def _scale_update_rejection_reason(
    new_counts_per_rev: float,
    measured_delta_deg: float,
    expected_delta_deg: float,
) -> str | None:
    if not math.isfinite(new_counts_per_rev):
        return "candidate scale is not finite"
    if not (
        ZERO_VISUAL_MIN_CONTROLLER_COUNTS_PER_REV
        <= abs(new_counts_per_rev)
        <= ZERO_VISUAL_MAX_CONTROLLER_COUNTS_PER_REV
    ):
        return (
            "candidate scale outside allowed range "
            f"{ZERO_VISUAL_MIN_CONTROLLER_COUNTS_PER_REV:.1f}.."
            f"{ZERO_VISUAL_MAX_CONTROLLER_COUNTS_PER_REV:.1f} counts/rev"
        )
    if abs(measured_delta_deg) < ZERO_VISUAL_MIN_FEEDBACK_DEG:
        return (
            "measured visual movement below minimum feedback "
            f"{ZERO_VISUAL_MIN_FEEDBACK_DEG:.1f} deg"
        )
    if abs(expected_delta_deg) < ZERO_VISUAL_MIN_FEEDBACK_DEG:
        if _scale_is_near_expected_region(new_counts_per_rev):
            return None
        return (
            "expected visual movement too small and candidate scale is not near "
            "a known controller scale"
        )
    ratio = abs(measured_delta_deg / expected_delta_deg)
    if ZERO_VISUAL_FEEDBACK_MISMATCH_MIN_RATIO <= ratio <= ZERO_VISUAL_FEEDBACK_MISMATCH_MAX_RATIO:
        return None
    if _scale_is_near_expected_region(new_counts_per_rev):
        return None
    return (
        "measured/expected visual movement ratio outside allowed range "
        f"{ZERO_VISUAL_FEEDBACK_MISMATCH_MIN_RATIO:.2f}.."
        f"{ZERO_VISUAL_FEEDBACK_MISMATCH_MAX_RATIO:.2f}"
    )


def _candidate_controller_counts_per_rev(
    moved_counts: int,
    moved_visual_deg: float,
    expected_visual_delta_deg: float,
) -> float | None:
    """Return a plausible controller counts/rev estimate from one visual move."""
    if abs(float(moved_visual_deg)) < ZERO_VISUAL_MIN_FEEDBACK_DEG:
        return None
    candidate = int(moved_counts) / float(moved_visual_deg) * 360.0
    if not _scale_update_is_plausible(
        candidate,
        moved_visual_deg,
        expected_visual_delta_deg,
    ):
        return None
    return candidate


def _micon_i32_in_range(value: int) -> bool:
    return MICON_POSITION_MIN <= int(value) <= MICON_POSITION_MAX


def _checked_micon_i32(value: int, label: str) -> int:
    value = int(value)
    if not _micon_i32_in_range(value):
        raise RuntimeError(
            f"{label} is outside MiControl signed 32-bit counter range: "
            f"value={value} range=[{MICON_POSITION_MIN}..{MICON_POSITION_MAX}]"
        )
    return value


def _expected_micon_counter_after_relative_move(
    actual_position_counts: int,
    correction_counts: int,
) -> int:
    return _checked_micon_i32(
        int(actual_position_counts) + int(correction_counts),
        "Expected MiControl position counter",
    )


def _wait_for_visual_move_settle(
    mic,
    expected_position_counter: int,
    label: str,
) -> tuple[int | None, int | None]:
    """Wait until the controller is close to the requested position or stops moving."""
    expected_position_counter = _checked_micon_i32(
        expected_position_counter,
        "Expected MiControl position counter",
    )
    deadline = time.monotonic() + ZERO_VISUAL_MOVE_SETTLE_TIMEOUT_S
    last_position = None
    last_velocity = None
    previous_position = None
    stable_reads = 0

    while time.monotonic() < deadline:
        time.sleep(ZERO_VISUAL_MOVE_SETTLE_POLL_S)
        last_position = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
        last_velocity = mic.get_velocity() if hasattr(mic, "get_velocity") else None

        position_ok = (
            last_position is not None
            and abs(int(last_position) - expected_position_counter) <= ZERO_POSITION_TOLERANCE_COUNTS
        )
        velocity_ok = (
            last_velocity is None
            or abs(int(last_velocity)) <= ZERO_VISUAL_MOVE_SETTLE_VELOCITY
        )
        if position_ok and velocity_ok:
            return last_position, last_velocity

        position_stable = (
            last_position is not None
            and previous_position is not None
            and abs(int(last_position) - int(previous_position)) <= ZERO_POSITION_TOLERANCE_COUNTS
        )
        if velocity_ok and position_stable:
            stable_reads += 1
            if stable_reads >= 3:
                return last_position, last_velocity
        else:
            stable_reads = 0
        previous_position = last_position

    print(
        f"[WARN] Controller did not fully settle during {label}: "
        f"expected_position_counter={expected_position_counter} last_position={last_position} "
        f"last_velocity={last_velocity} timeout={ZERO_VISUAL_MOVE_SETTLE_TIMEOUT_S:.1f}s"
    )
    return last_position, last_velocity


def _visual_move_rpm_for_step(step_error_deg: float) -> int:
    if abs(float(step_error_deg)) <= ZERO_VISUAL_FINE_STEP_DEG:
        return ZERO_VISUAL_FINE_MOVE_RPM
    return ZERO_VISUAL_MOVE_RPM


def _prepare_visual_position_motion(mic, label: str, rpm: int) -> None:
    rpm = int(rpm)
    if hasattr(mic, "prepare_position_motion"):
        if mic.prepare_position_motion(rpm):
            return
        raise RuntimeError(
            f"Controller could not enter position mode before visual-zero move ({label})."
        )

    mic.enabled(False)
    time.sleep(0.25)
    _clear_controller_errors(mic)
    mic.set_device_mode_position()
    mic.set_RPM(rpm)
    if hasattr(mic, "set_steering_RPM"):
        mic.set_steering_RPM(rpm)
    mic.enabled(True)
    time.sleep(0.5)


def _command_visual_relative_move(
    mic,
    correction_counts: int,
    expected_position_counter: int,
    label: str,
    rpm: int,
) -> tuple[int | None, int | None]:
    """Command the computed relative MiControl move; the camera verifies the result."""
    correction_counts = _checked_micon_i32(
        correction_counts,
        "MiControl relative position correction",
    )
    expected_position_counter = _checked_micon_i32(
        expected_position_counter,
        "Expected MiControl position counter",
    )
    start_position = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
    _prepare_visual_position_motion(mic, label, rpm)

    try:
        if hasattr(mic, "set_steering_relative"):
            mic.set_steering_relative(correction_counts)
        else:
            mic.set_steering_pos(expected_position_counter)
    except Exception as first_exc:
        print(
            f"[WARN] Position command rejected during {label}; "
            f"performing one full position-mode retry: {first_exc}"
        )
        _prepare_visual_position_motion(mic, label, rpm)
        try:
            if hasattr(mic, "set_steering_relative"):
                mic.set_steering_relative(correction_counts)
            else:
                mic.set_steering_pos(expected_position_counter)
        except Exception as retry_exc:
            raise RuntimeError(
                "Controller rejected visual-zero relative move after position-mode retry: "
                f"correction_counts={correction_counts:+d} "
                f"expected_position_counter={expected_position_counter} "
                f"label={label} error={retry_exc}"
            ) from retry_exc
    end_position, end_velocity = _wait_for_visual_move_settle(
        mic,
        expected_position_counter,
        label,
    )
    print(
        f"[INFO] Visual-guided relative move commanded ({label}): "
        f"rpm={int(rpm)} "
        f"correction_counts={correction_counts:+d} "
        f"expected_position_counter={expected_position_counter} "
        f"controller_position={start_position}->{end_position} "
        f"velocity={end_velocity}; "
        "camera readback follows."
    )
    return end_position, end_velocity


def _probe_visual_controller_counts_per_rev(
    mic,
    current_counts_per_rev: float,
) -> float | None:
    """Learn controller counts/rev with a small direct-encoder verified move."""
    if not (
        hasattr(mic, "get_steering_pos")
        and hasattr(mic, "get_ssi_direct_position")
    ):
        return None

    before_position = mic.get_steering_pos()
    before_encoder = mic.get_ssi_direct_position()
    if before_position is None or before_encoder is None:
        print(
            "[WARN] Skipping visual-zero scale probe because controller or "
            "direct encoder position is unavailable."
        )
        return None

    probe_counts = int(ZERO_VISUAL_SCALE_PROBE_COUNTS)
    before_position = _checked_micon_i32(
        before_position,
        "Scale probe MiControl start position",
    )
    expected_position = _expected_micon_counter_after_relative_move(
        before_position,
        probe_counts,
    )
    if _controller_counts_per_rev_is_valid(current_counts_per_rev):
        expected_encoder_delta = (
            probe_counts
            / float(current_counts_per_rev)
            * ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV
        )
    else:
        expected_encoder_delta = 0.0

    print(
        "[STATUS] Visual-zero scale probe: "
        f"controller_position={before_position} "
        f"direct_encoder={before_encoder} "
        f"probe_counts={probe_counts:+d} "
        f"seed_counts_per_rev={current_counts_per_rev:.3f}"
    )
    try:
        settled_position, _settled_velocity = _command_visual_relative_move(
            mic,
            probe_counts,
            expected_position,
            "scale probe",
            ZERO_VISUAL_SCALE_PROBE_RPM,
        )
    except Exception as exc:
        print(f"[WARN] Visual-zero scale probe failed; continuing with seed scale: {exc}")
        return None

    after_position = mic.get_steering_pos()
    after_encoder = mic.get_ssi_direct_position()
    if after_position is None:
        after_position = settled_position
    if after_position is None or after_encoder is None:
        print("[WARN] Visual-zero scale probe could not read post-move feedback.")
        return None

    moved_controller_counts = int(after_position) - before_position
    moved_encoder_counts = _single_turn_delta_counts(
        after_encoder,
        before_encoder,
        ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV,
        expected_encoder_delta,
    )
    observed_counts_per_rev = _candidate_controller_counts_per_rev_from_encoder(
        moved_controller_counts,
        moved_encoder_counts,
    )
    moved_encoder_deg = (
        moved_encoder_counts
        / ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV
        * 360.0
    )
    if observed_counts_per_rev is None:
        print(
            "[WARN] Visual-zero scale probe feedback was not usable: "
            f"controller_delta={moved_controller_counts:+d} "
            f"encoder_delta={moved_encoder_counts:+.1f} counts "
            f"encoder_delta_deg={moved_encoder_deg:+.2f} deg"
        )
        return None

    _store_visual_controller_counts_per_rev(mic, observed_counts_per_rev)
    print(
        "[INFO] Visual-zero scale probe learned controller scale: "
        f"controller_delta={moved_controller_counts:+d} "
        f"encoder_delta={moved_encoder_counts:+.1f} counts "
        f"encoder_delta_deg={moved_encoder_deg:+.2f} deg "
        f"controller_counts_per_rev={observed_counts_per_rev:+.3f}"
    )
    return observed_counts_per_rev


def _move_to_visual_zero(
    mic,
    current_angle_deg: float,
    desired_angle_deg: float,
    read_angle_fn,
    *,
    require_strict_target: bool = False,
) -> float:
    """Use camera feedback to physically position the shaft at the requested zero."""
    current_angle_deg = float(current_angle_deg) % 360.0
    desired_angle_deg = float(desired_angle_deg) % 360.0
    error_deg = _visual_zero_error_deg(desired_angle_deg, current_angle_deg)
    print(
        f"[STATUS] Visual-zero positioning: current={current_angle_deg:.2f} deg "
        f"target={desired_angle_deg:.2f} deg error={error_deg:+.2f} deg"
    )
    controller_counts_per_rev, _scale_from_cache, scale_needs_probe = (
        _seed_visual_controller_counts_per_rev(mic)
    )
    acceptance_tolerance_deg = _visual_acceptance_tolerance_deg(controller_counts_per_rev)
    if _visual_zero_reached(
        desired_angle_deg,
        current_angle_deg,
        acceptance_tolerance_deg,
        require_strict_target=require_strict_target,
    ):
        print("[INFO] Shaft is already within visual-zero tolerance.")
        return current_angle_deg

    if scale_needs_probe:
        probed_counts_per_rev = _probe_visual_controller_counts_per_rev(
            mic,
            controller_counts_per_rev,
        )
        if probed_counts_per_rev is not None:
            controller_counts_per_rev = probed_counts_per_rev
            time.sleep(ZERO_CAMERA_SETTLE_S)
            current_angle_deg = float(read_angle_fn()) % 360.0
            error_deg = _visual_zero_error_deg(desired_angle_deg, current_angle_deg)
            acceptance_tolerance_deg = _visual_acceptance_tolerance_deg(
                controller_counts_per_rev,
            )
            print(
                "[STATUS] Visual-zero positioning after scale probe: "
                f"current={current_angle_deg:.2f} deg "
                f"target={desired_angle_deg:.2f} deg error={error_deg:+.2f} deg "
                f"controller_counts_per_rev={controller_counts_per_rev:.3f}"
            )
            if _visual_zero_reached(
                desired_angle_deg,
                current_angle_deg,
                acceptance_tolerance_deg,
                require_strict_target=require_strict_target,
            ):
                print("[INFO] Shaft is within visual-zero tolerance after scale probe.")
                return current_angle_deg

    max_step_deg = ZERO_VISUAL_MAX_STEP_DEG
    for attempt in range(1, ZERO_VISUAL_MAX_CORRECTIONS + 1):
        error_deg = _visual_zero_error_deg(desired_angle_deg, current_angle_deg)
        acceptance_tolerance_deg = _visual_acceptance_tolerance_deg(controller_counts_per_rev)
        if _visual_zero_reached(
            desired_angle_deg,
            current_angle_deg,
            acceptance_tolerance_deg,
            require_strict_target=require_strict_target,
        ):
            print(
                f"[STATE] Visual zero reached: angle={current_angle_deg:.2f} deg "
                f"target={desired_angle_deg:.2f} deg error={error_deg:+.2f} deg "
                f"tolerance={acceptance_tolerance_deg:.2f} deg "
                f"strict_tolerance={ZERO_VISUAL_TOLERANCE_DEG:.2f} deg"
            )
            return current_angle_deg
        actual_position = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
        if actual_position is None:
            raise RuntimeError(
                f"Could not read MiControl actual position before visual-zero move {attempt}."
            )
        encoder2_position = (
            mic.get_ssi_direct_position()
            if hasattr(mic, "get_ssi_direct_position")
            else None
        )
        (
            step_error_deg,
            correction_revolutions,
            correction_counts,
            expected_visual_delta_deg,
        ) = _plan_visual_zero_move(
            error_deg,
            controller_counts_per_rev,
            max_step_deg,
        )
        before_move_angle_deg = current_angle_deg
        before_move_position = _checked_micon_i32(
            actual_position,
            "Actual MiControl position counter",
        )
        expected_position_counter = _expected_micon_counter_after_relative_move(
            before_move_position,
            correction_counts,
        )
        move_rpm = _visual_move_rpm_for_step(step_error_deg)
        print(
            f"[STATUS] Mathematical visual-zero move {attempt}: "
            f"actual_visual={current_angle_deg:.2f} deg "
            f"actual_miControl_counter={before_move_position} "
            f"actual_encoder2={encoder2_position} "
            f"target_visual={desired_angle_deg:.2f} deg "
            f"visual_error={error_deg:+.2f} deg "
            f"step_error={step_error_deg:+.2f} deg "
            f"max_step={max_step_deg:.2f} deg "
            f"move_rpm={move_rpm} "
            f"correction_revolutions={correction_revolutions:+.6f} "
            f"controller_counts_per_rev={controller_counts_per_rev:.3f} "
            f"acceptance_tolerance={acceptance_tolerance_deg:.2f} deg "
            f"correction_counts={correction_counts:+d} "
            f"expected_miControl_counter={expected_position_counter}"
        )
        settled_position, _settled_velocity = _command_visual_relative_move(
            mic,
            correction_counts,
            expected_position_counter,
            f"mathematical move {attempt}",
            move_rpm,
        )
        current_angle_deg = float(read_angle_fn()) % 360.0
        after_move_position = (
            mic.get_steering_pos()
            if hasattr(mic, "get_steering_pos")
            else None
        )
        after_encoder2_position = (
            mic.get_ssi_direct_position()
            if hasattr(mic, "get_ssi_direct_position")
            else None
        )
        if after_move_position is None:
            after_move_position = settled_position
        moved_controller_counts = (
            int(after_move_position) - before_move_position
            if after_move_position is not None
            else None
        )
        moved_encoder_counts = None
        moved_encoder_deg = None
        if encoder2_position is not None and after_encoder2_position is not None:
            expected_encoder_delta_counts = (
                expected_visual_delta_deg
                / 360.0
                * ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV
            )
            moved_encoder_counts = _single_turn_delta_counts(
                after_encoder2_position,
                encoder2_position,
                ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV,
                expected_encoder_delta_counts,
            )
            moved_encoder_deg = (
                moved_encoder_counts
                / ZERO_VISUAL_DIRECT_ENCODER_COUNTS_PER_REV
                * 360.0
            )
        moved_visual_deg = _visual_motion_delta_deg(
            current_angle_deg,
            before_move_angle_deg,
            expected_visual_delta_deg,
        )
        stale_rereads = 0
        while (
            moved_controller_counts is not None
            and abs(moved_controller_counts) >= ZERO_VISUAL_MIN_FEEDBACK_COUNTS
            and abs(moved_visual_deg) < ZERO_VISUAL_MIN_FEEDBACK_DEG
            and stale_rereads < ZERO_VISUAL_STALE_CAMERA_REREADS
        ):
            stale_rereads += 1
            print(
                "[WARN] Camera feedback showed almost no movement after a controller move; "
                f"taking fresh camera read {stale_rereads}/{ZERO_VISUAL_STALE_CAMERA_REREADS} "
                "before learning scale."
            )
            time.sleep(ZERO_CAMERA_SETTLE_S)
            current_angle_deg = float(read_angle_fn()) % 360.0
            moved_visual_deg = _visual_motion_delta_deg(
                current_angle_deg,
                before_move_angle_deg,
                expected_visual_delta_deg,
            )
        print(
            "[INFO] Visual move feedback: "
            f"expected_delta={expected_visual_delta_deg:+.2f} deg "
            f"measured_delta={moved_visual_deg:+.2f} deg"
            + (
                f" encoder_delta={moved_encoder_deg:+.2f} deg"
                if moved_encoder_deg is not None
                else ""
            )
        )
        feedback_plausible = False
        scale_learned_from_encoder = False
        if after_move_position is not None:
            commanded_error = correction_counts - moved_controller_counts
            if abs(commanded_error) > ZERO_POSITION_TOLERANCE_COUNTS:
                print(
                    "[WARN] Controller movement differed from requested visual move: "
                    f"requested_delta={correction_counts:+d} "
                    f"actual_delta={moved_controller_counts:+d} "
                    f"delta_error={commanded_error:+d}"
                )
            if (
                moved_encoder_counts is not None
                and abs(moved_controller_counts) >= ZERO_VISUAL_MIN_FEEDBACK_COUNTS
            ):
                observed_counts_per_rev = _candidate_controller_counts_per_rev_from_encoder(
                    moved_controller_counts,
                    moved_encoder_counts,
                )
                if observed_counts_per_rev is not None:
                    controller_counts_per_rev = observed_counts_per_rev
                    _store_visual_controller_counts_per_rev(mic, controller_counts_per_rev)
                    feedback_plausible = True
                    scale_learned_from_encoder = True
                    print(
                        "[INFO] Updated controller visual scale from direct encoder: "
                        f"controller_delta={moved_controller_counts:+d} "
                        f"encoder_delta={moved_encoder_counts:+.1f} counts "
                        f"encoder_delta_deg={moved_encoder_deg:+.2f} deg "
                        f"controller_counts_per_rev={controller_counts_per_rev:+.3f}"
                    )
                else:
                    print(
                        "[WARN] Ignored direct encoder scale update: "
                        f"controller_delta={moved_controller_counts:+d} "
                        f"encoder_delta={moved_encoder_counts:+.1f} counts"
                    )
            if abs(moved_controller_counts) >= ZERO_VISUAL_MIN_FEEDBACK_COUNTS:
                if not scale_learned_from_encoder:
                    observed_counts_per_rev = _candidate_controller_counts_per_rev(
                        moved_controller_counts,
                        moved_visual_deg,
                        expected_visual_delta_deg,
                    )
                    if observed_counts_per_rev is not None:
                        controller_counts_per_rev = observed_counts_per_rev
                        _store_visual_controller_counts_per_rev(mic, controller_counts_per_rev)
                        feedback_plausible = True
                        print(
                            "[INFO] Updated controller visual scale: "
                            f"controller_delta={moved_controller_counts:+d} "
                            f"visual_delta={moved_visual_deg:+.2f} deg "
                            f"controller_counts_per_rev={controller_counts_per_rev:+.3f}"
                        )
                    elif abs(moved_visual_deg) >= ZERO_VISUAL_MIN_FEEDBACK_DEG:
                        rejected_candidate = (
                            moved_controller_counts / moved_visual_deg * 360.0
                        )
                        rejection_reason = _scale_update_rejection_reason(
                            rejected_candidate,
                            moved_visual_deg,
                            expected_visual_delta_deg,
                        )
                        print(
                            "[WARN] Ignored implausible position/camera scale update: "
                            f"controller_delta={moved_controller_counts:+d} "
                            f"expected_delta={expected_visual_delta_deg:+.2f} deg "
                            f"visual_delta={moved_visual_deg:+.2f} deg "
                            f"candidate_counts_per_rev={rejected_candidate:+.3f} "
                            f"reason={rejection_reason}"
                        )
        if (
            not scale_learned_from_encoder
            and (moved_controller_counts is None or abs(moved_controller_counts) < ZERO_VISUAL_MIN_FEEDBACK_COUNTS)
        ):
            commanded_counts_per_rev = _candidate_controller_counts_per_rev(
                correction_counts,
                moved_visual_deg,
                expected_visual_delta_deg,
            )
            if commanded_counts_per_rev is not None:
                controller_counts_per_rev = commanded_counts_per_rev
                _store_visual_controller_counts_per_rev(mic, controller_counts_per_rev)
                feedback_plausible = True
                print(
                    "[INFO] Updated controller visual scale from command/camera: "
                    f"commanded_counts={correction_counts:+d} "
                    f"visual_delta={moved_visual_deg:+.2f} deg "
                    f"controller_counts_per_rev={controller_counts_per_rev:+.3f}"
                )
            elif abs(moved_visual_deg) >= ZERO_VISUAL_MIN_FEEDBACK_DEG:
                rejected_candidate = correction_counts / moved_visual_deg * 360.0
                rejection_reason = _scale_update_rejection_reason(
                    rejected_candidate,
                    moved_visual_deg,
                    expected_visual_delta_deg,
                )
                print(
                    "[WARN] Ignored implausible command/camera scale update: "
                    f"commanded_counts={correction_counts:+d} "
                    f"expected_delta={expected_visual_delta_deg:+.2f} deg "
                    f"visual_delta={moved_visual_deg:+.2f} deg "
                    f"candidate_counts_per_rev={rejected_candidate:+.3f} "
                    f"reason={rejection_reason}"
                )
        previous_max_step_deg = max_step_deg
        max_step_deg = _next_visual_step_limit_deg(max_step_deg, feedback_plausible)
        if feedback_plausible:
            if max_step_deg != previous_max_step_deg:
                print(
                    "[INFO] Visual feedback accepted; next max step relaxed: "
                    f"{previous_max_step_deg:.2f}->{max_step_deg:.2f} deg"
                )
        else:
            print(
                "[WARN] Visual feedback not reliable; next max step reduced: "
                f"{previous_max_step_deg:.2f}->{max_step_deg:.2f} deg"
            )
        remaining_error_deg = _visual_zero_error_deg(desired_angle_deg, current_angle_deg)
        acceptance_tolerance_deg = _visual_acceptance_tolerance_deg(controller_counts_per_rev)
        print(
            f"[INFO] Visual-zero correction {attempt}: "
            f"angle={current_angle_deg:.2f} deg "
            f"remaining_error={remaining_error_deg:+.2f} deg "
            f"tolerance={acceptance_tolerance_deg:.2f} deg"
        )
        if _visual_zero_reached(
            desired_angle_deg,
            current_angle_deg,
            acceptance_tolerance_deg,
            require_strict_target=require_strict_target,
        ):
            print(
                f"[STATE] Visual zero reached: angle={current_angle_deg:.2f} deg "
                f"target={desired_angle_deg:.2f} deg error={remaining_error_deg:+.2f} deg "
                f"tolerance={acceptance_tolerance_deg:.2f} deg "
                f"strict_tolerance={ZERO_VISUAL_TOLERANCE_DEG:.2f} deg"
            )
            return current_angle_deg

    final_error = _visual_zero_error_deg(desired_angle_deg, current_angle_deg)
    if _visual_zero_reached(
        desired_angle_deg,
        current_angle_deg,
        acceptance_tolerance_deg,
        require_strict_target=require_strict_target,
    ):
        print(
            f"[STATE] Visual zero reached on final check: angle={current_angle_deg:.2f} deg "
            f"target={desired_angle_deg:.2f} deg error={final_error:+.2f} deg "
            f"tolerance={acceptance_tolerance_deg:.2f} deg "
            f"strict_tolerance={ZERO_VISUAL_TOLERANCE_DEG:.2f} deg"
        )
        return current_angle_deg
    raise RuntimeError(
        "Could not position motor at visual zero: "
        f"angle={current_angle_deg:.2f} target={desired_angle_deg:.2f} "
        f"error={final_error:+.2f} deg tolerance={acceptance_tolerance_deg:.2f} deg."
    )

def _set_current_mode_best_effort(handle: MU_Handle, final_mode: c_uint32, context: str) -> bool:
    # Do not verify a switch away from BiSS: after MODEA changes to SSI, the
    # BiSS verification transaction itself can fail even though the write worked.
    ret = mu.MU_SetParam(handle, MU_MODEA, 0, final_mode, MU_WRITE)
    if ret != MU_OK:
        print(
            f"[WARN] Set current MODEA final (no verify) failed after {context}; "
            f"live mode was not restored ({_mu_last_error(handle)})"
        )
        return False
    else:
        _log_mu("Set current MODEA final (no verify)", ret, handle)
        return True


def _write_eeprom_cfg(handle: MU_Handle, label: str) -> bool:
    ret = mu.MU_WriteEeprom(handle, MU_E2P_CFG)
    _log_mu(label, ret, handle)
    return ret == MU_OK


def _store_current_config_and_switch_mode(
    mu: ctypes.CDLL,
    handle: MU_Handle,
    final_mode: c_uint32,
) -> bool:
    if not _write_eeprom_cfg(handle, "Write EEPROM CFG in BiSS"):
        return False

    if not _set_current_mode_best_effort(
        handle,
        final_mode,
        "BiSS EEPROM write",
    ):
        return False

    if not _write_eeprom_cfg(handle, "Write EEPROM CFG in SSI"):
        return False

    time.sleep(0.5)
    return True

def write_to_SSi(mu: ctypes.CDLL, handle: MU_Handle) -> bool:
    return _store_current_config_and_switch_mode(mu, handle, MU_SSI)

def _iface_option(serial_last4: str) -> bytes:
    # IMPORTANT: MU_SetInterface wants EMPTY STRING if only one adapter is connected (NOT NULL).
    return serial_last4.encode("ascii") if serial_last4 else b""

def _set_mb5u_interface(handle: MU_Handle, serial_arg: bytes, label: str = "Set Interface") -> bool:
    ret = mu.MU_SetInterface(handle, MU_MB5U.value, serial_arg)
    _log_mu(label, ret, handle)
    if ret != MU_OK and not serial_arg:
        ret = mu.MU_SetInterface(handle, MU_MB5U.value, None)
        _log_mu(f"{label} (NULL fallback)", ret, handle)
    return ret == MU_OK

def _clear_controller_errors(mic) -> None:
    mic.clear_errors()
    mic.clear_errors()

def _open_mu_handle(handle: MU_Handle) -> bool:
    ret = mu.MU_Open(byref(handle))
    _log_mu("Open", ret, handle)
    return ret == MU_OK

def _close_mu_handle(handle: MU_Handle) -> None:
    _log_mu("Close", mu.MU_Close(handle), handle)


@contextmanager
def _managed_encoder_session(
    serial_arg: bytes,
    enc_idx: int,
    context: str,
    on_close=None,
):
    handle = MU_Handle()
    opened = False
    try:
        if not _open_encoder_session(handle, serial_arg, enc_idx, context):
            yield None
            return
        opened = True
        yield handle
    finally:
        if opened:
            if on_close is not None:
                on_close(handle)
            _close_mu_handle(handle)


def _open_encoder_session(
    handle: MU_Handle,
    serial_arg: bytes,
    enc_idx: int,
    context: str,
) -> bool:
    if not _open_mu_handle(handle):
        return False

    if not _set_mb5u_interface(handle, serial_arg):
        _close_mu_handle(handle)
        return False

    ret = mu.MU_UseRevision(handle, MU_FORCED_REV)
    _log_mu(f"Use revision 0x{MU_FORCED_REV:02X}", ret, handle)
    if ret != MU_OK:
        _close_mu_handle(handle)
        return False

    if not _enter_biss(handle):
        print(f"[ERROR] Unable to enter BiSS mode during {context} (encoder {enc_idx}).")
        _close_mu_handle(handle)
        return False

    ret = mu.MU_Initialize(handle)
    _log_mu("Initialize", ret, handle)
    if ret != MU_OK:
        _close_mu_handle(handle)
        return False

    return True


def _configured_config_path() -> Path:
    return Path(CONFIG_PATH_0.decode("utf-8", errors="replace"))

def _resolve_config_path(enc_idx: int | None = None) -> Path:
    return _configured_config_path()

def _load_config_0_or_abort(
    handle: MU_Handle,
    label: str = "Load config_0",
    enc_idx: int | None = None,
) -> bool:
    config_path = _resolve_config_path(enc_idx)
    if not config_path.is_file():
        print(f"[ERROR] {label} missing file: {config_path}")
        return False

    ret = mu.MU_LoadParams(handle, str(config_path).encode("utf-8"))
    _log_mu(label, ret, handle)
    return ret == MU_OK

def write_params_with_verify(mu: ctypes.CDLL, handle: MU_Handle) -> int:
    # The MB5U path returns MU_UNKNOWN_ERROR when MU_WriteParams verify=True.
    # Use the vendor-example-compatible write mode, then verify with MU_ReadParams.
    ret = mu.MU_WriteParams(handle, False, None)
    _log_mu("Write RAM (compatible bulk write; explicit readback follows)", ret, handle)
    return int(ret)

_CHECKPOINT_PARAMS = (
    (MU_MODEA, "MODEA"),
    (MU_OFF_ABZ, "OFF_ABZ"),
    (MU_OFF_POS, "OFF_POS"),
    (MU_PRES_POS, "PRES_POS"),
)

ZERO_WRITE_ALLOWED_PARAM_INDEXES = frozenset(
    {
        MU_MODEA.value,
        MU_OFF_ABZ.value,
        MU_OFF_POS.value,
        MU_OFF_COM.value,
        MU_OFF_UVW.value,
        MU_PRES_POS.value,
        MU_I2C_DEVID_PARAM_INDEX,
        MU_I2C_RETRY_PARAM_INDEX,
        MU_HARD_REV_PARAM_INDEX,
    }
)


def _print_vco_state(handle: MU_Handle, label: str) -> bool:
    """Print selected values from the VCO. Call MU_ReadParams first to show chip RAM."""
    print(f"\n[CHECKPOINT] {label}")
    ok = True
    for param, name in _CHECKPOINT_PARAMS:
        value_high = c_uint32(0)
        value_low = c_uint32(0)
        ret = mu.MU_GetParam(handle, param, byref(value_high), byref(value_low))
        if ret != MU_OK:
            _log_mu(f"GetParam {name}", ret, handle)
            ok = False
            continue
        value = (int(value_high.value) << 32) | int(value_low.value)
        print(
            f"[STATE] {name:<8} high=0x{int(value_high.value):08X} "
            f"low=0x{int(value_low.value):08X} low12={value & 0xFFF}"
        )

    value_high = c_uint32(0)
    value_low = c_uint32(0)
    ret = mu.MU_GetPRES_POS(handle, byref(value_high), byref(value_low))
    if ret != MU_OK:
        _log_mu("Get real PRES_POS", ret, handle)
        return False
    print(
        f"[STATE] REAL_PRES_POS high=0x{int(value_high.value):08X} "
        f"low=0x{int(value_low.value):08X} low12={int(value_low.value) & 0xFFF}"
    )
    return ok


def _checkpoint_ram(handle: MU_Handle, label: str) -> bool:
    """Refresh the VCO from chip RAM, then print the selected live RAM values."""
    ret = mu.MU_ReadParams(handle)
    _log_mu(f"ReadParams for RAM checkpoint: {label}", ret, handle)
    if ret != MU_OK:
        return False
    return _print_vco_state(handle, f"RAM after {label}")


def _verify_preset_readback(handle: MU_Handle, label: str, expected_preset_ticks: int) -> bool:
    """Verify the current RAM/VCO preset without disrupting BiSS communication."""
    value_high = c_uint32(0)
    value_low = c_uint32(0)
    ret = mu.MU_GetPRES_POS(handle, byref(value_high), byref(value_low))
    _log_mu(f"Verify PRES_POS readback: {label}", ret, handle)
    if ret != MU_OK:
        return False
    actual_ticks = int(value_low.value) & 0xFFF
    expected_ticks = int(expected_preset_ticks) & 0xFFF
    if actual_ticks != expected_ticks:
        print(
            f"[ERROR] PRES_POS mismatch after {label}: "
            f"expected={expected_ticks} actual={actual_ticks}"
        )
        return False
    print(f"[STATE] PRES_POS readback verified after {label}: {actual_ticks} ticks")
    return True


def _verify_zero_write_preserved_nonzero_config(
    before: dict[int, tuple[int, int]],
    after: dict[int, tuple[int, int]],
    label: str,
) -> bool:
    """Ensure zero writing did not wipe calibration or other non-zero config."""
    before_compare = dict(before)
    after_compare = dict(after)
    for param_idx in ZERO_WRITE_ALLOWED_PARAM_INDEXES:
        before_compare.pop(param_idx, None)
        after_compare.pop(param_idx, None)
    return _verify_stable_config_preserved(
        before_compare,
        after_compare,
        label,
    )


def _load_zero_config_for_zero(
    handle: MU_Handle,
    serial_arg: bytes,
    enc_idx: int,
    config_path: Path,
) -> bool:
    if not config_path.exists():
        print(f"[ERROR] Zero config disappeared after preflight: {config_path}")
        return False

    print(f"[INFO] Loading zero config before zeroing: {config_path}")
    ret = mu.MU_LoadParams(handle, str(config_path).encode("utf-8"))
    _log_mu("Load zero config", ret, handle)
    if ret != MU_OK:
        return False
    if not _print_vco_state(
        handle,
        f"VCO after encoder {enc_idx} zero config load (not yet in RAM)",
    ):
        return False
    if not _set_mb5u_interface(handle, serial_arg, "Set Interface after config load"):
        return False
    ret = mu.MU_UseRevision(handle, MU_FORCED_REV)
    _log_mu(f"Use revision 0x{MU_FORCED_REV:02X} after config load", ret, handle)
    if ret != MU_OK:
        return False
    ret = mu.MU_SetParam(handle, MU_MODEA, 0, MU_BISS, MU_SETONLY)
    _log_mu("Keep MODEA BiSS for zeroing", ret, handle)
    if ret != MU_OK:
        return False
    return _write_vco_to_ram_and_verify(
        handle,
        "zero config BiSS RAM write",
        0.2,
    )


def _write_zero_preset_to_encoder_eeprom(
    handle: MU_Handle,
    enc_idx: int,
    preset_ticks: int,
) -> dict[int, tuple[int, int]] | None:
    preset_ticks = int(preset_ticks) & 0xFFF
    ret = mu.MU_CalcPRES_POS(handle, c_uint32(0), c_uint32(preset_ticks), MU_VERIFY)
    _log_mu(f"Calc PRES_POS encoder {enc_idx} zero={preset_ticks}", ret, handle)
    if ret != MU_OK:
        return None
    if not _checkpoint_ram(handle, "Calc PRES_POS zero"):
        return None

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_SOFT_E2P_PRES)
    _log_mu(f"Soft E2P PRES encoder {enc_idx} zero={preset_ticks}", ret, handle)
    if ret != MU_OK:
        return None
    time.sleep(0.5)
    if not _checkpoint_ram(handle, "SOFT_E2P_PRES zero"):
        return None
    if not _verify_preset_readback(handle, "SOFT_E2P_PRES zero", preset_ticks):
        return None

    config_before_full_write = _capture_stable_config(handle)
    if len(config_before_full_write) < MU_MIN_STABLE_CONFIG_PARAMS:
        print("[ERROR] Could not capture configuration before final EEPROM write.")
        return None

    # ReadParams above refreshed the VCO with the new preset/offsets.
    # MU_WriteEeprom now stores that complete state using the working sequence.
    if not write_to_SSi(mu, handle):
        return None

    expected_eeprom_config = _capture_stable_config(handle)
    if len(expected_eeprom_config) < MU_MIN_STABLE_CONFIG_PARAMS:
        print(
            f"[ERROR] Could not capture encoder {enc_idx} expected EEPROM image "
            "after final write."
        )
        return None

    before_compare = dict(config_before_full_write)
    expected_compare = dict(expected_eeprom_config)
    for ignored_param in (MU_MODEA.value, MU_HARD_REV_PARAM_INDEX):
        before_compare.pop(ignored_param, None)
        expected_compare.pop(ignored_param, None)
    if not _verify_stable_config_preserved(
        before_compare,
        expected_compare,
        f"encoder {enc_idx} final EEPROM write input",
    ):
        return None
    return expected_eeprom_config


def _verify_controller_zero_reference(mic, label: str) -> bool:
    deadline = time.monotonic() + ZERO_CONTROLLER_VERIFY_TIMEOUT_S
    steering_pos = None
    direct_pos = None
    status = None
    while True:
        steering_pos = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
        direct_pos = (
            mic.get_ssi_direct_position()
            if hasattr(mic, "get_ssi_direct_position")
            else None
        )
        status = (
            mic.get_ssi_encoder_status()
            if hasattr(mic, "get_ssi_encoder_status")
            else None
        )
        print(
            f"[STATE] Controller zero reference after {label}: "
            f"status={status} direct_position={direct_pos} steering_position={steering_pos}"
        )
        if steering_pos is not None and abs(int(steering_pos)) <= ZERO_POSITION_TOLERANCE_COUNTS:
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(ZERO_CONTROLLER_VERIFY_POLL_S)

    if steering_pos is None:
        print("[ERROR] Controller steering zero readback is unavailable.")
        return False
    if abs(int(steering_pos)) > ZERO_POSITION_TOLERANCE_COUNTS:
        print(
            "[ERROR] Controller steering position is not zero at the desired visual angle: "
            f"position={steering_pos} tolerance=+/-{ZERO_POSITION_TOLERANCE_COUNTS}"
        )
        return False


def _verify_eeprom_after_power_cycle(
    mic,
    serial_arg: bytes,
    expected_configs: dict[int, dict[int, tuple[int, int]]],
    expected_presets: dict[int, int],
    encoder_mux_states: tuple[tuple[int, bool], ...] = ENCODER_MUX_STATES,
) -> bool:
    """Verify the complete startup-loaded EEPROM state after a real power cycle."""
    for enc_idx, dig_out in encoder_mux_states:
        handle = MU_Handle()
        opened = False
        entered_biss = False
        live_ssi_restored = False
        live_ssi_restore_attempted = False
        try:
            _clear_controller_errors(mic)
            mic.set_digital_output(dig_out)
            time.sleep(0.2)

            if not _open_mu_handle(handle):
                return False
            opened = True
            if not _set_mb5u_interface(handle, serial_arg):
                return False

            ret = mu.MU_UseRevision(handle, MU_FORCED_REV)
            _log_mu(f"Use revision 0x{MU_FORCED_REV:02X} for EEPROM verification", ret, handle)
            if ret != MU_OK:
                return False

            startup_mode = c_uint32(0)
            switched = c_bool(False)
            ret = mu.MU_SwitchToBiss_ex(handle, byref(startup_mode), byref(switched))
            _log_mu(f"Read startup MODEA / enter BiSS for encoder {enc_idx}", ret, handle)
            if ret != MU_OK:
                return False
            entered_biss = True
            if int(startup_mode.value) != MU_SSI.value:
                print(
                    f"[ERROR] Encoder {enc_idx} EEPROM startup MODEA mismatch: "
                    f"expected={MU_SSI.value} actual={int(startup_mode.value)}"
                )
                return False

            ret = mu.MU_Initialize(handle)
            _log_mu(f"Initialize encoder {enc_idx} for EEPROM verification", ret, handle)
            if ret != MU_OK:
                return False
            if not _checkpoint_ram(handle, f"encoder {enc_idx} post-power-cycle EEPROM load"):
                return False
            if not _verify_preset_readback(
                handle,
                f"encoder {enc_idx} post-power-cycle EEPROM load",
                expected_presets[enc_idx],
            ):
                return False

            expected = dict(expected_configs[enc_idx])
            actual = _capture_stable_config(handle)
            # MODEA is checked before entering BiSS. At startup the chip amends
            # EEPROM OFF_ABZ/OFF_UVW with nonius/multiturn data into RAM-only
            # OFF_POS/OFF_COM. Verify the persistent offsets and real preset.
            for derived_param, derived_name in (
                (MU_OFF_POS.value, "OFF_POS"),
                (MU_OFF_COM.value, "OFF_COM"),
            ):
                if expected.get(derived_param) != actual.get(derived_param):
                    print(
                        f"[STATE] Encoder {enc_idx} power-up regenerated {derived_name}: "
                        f"before_power_cycle={expected.get(derived_param)} "
                        f"after_power_cycle={actual.get(derived_param)}; "
                        "persistent offsets and real PRES_POS are verified separately."
                    )
            for ignored_param in MU_POST_POWER_CYCLE_DERIVED_PARAM_INDEXES:
                expected.pop(ignored_param, None)
                actual.pop(ignored_param, None)
            if not _verify_stable_config_preserved(
                expected,
                actual,
                f"encoder {enc_idx} EEPROM post-power-cycle readback",
            ):
                return False
            live_ssi_restore_attempted = True
            live_ssi_restored = _set_current_mode_best_effort(
                handle,
                MU_SSI,
                f"encoder {enc_idx} post-power-cycle EEPROM verification",
            )
            if not live_ssi_restored:
                print(
                    f"[WARN] Encoder {enc_idx} EEPROM is verified, but live SSI restoration "
                    "could not be confirmed. Controller SSI readiness will be checked next."
                )
            print(f"[STATE] Encoder {enc_idx} EEPROM verified after real power cycle.")
        finally:
            if opened:
                if entered_biss and not live_ssi_restored and not live_ssi_restore_attempted:
                    _restore_runtime_ssi_best_effort(
                        handle,
                        f"encoder {enc_idx} post-power-cycle EEPROM verification failure",
                    )
                _close_mu_handle(handle)
            _clear_controller_errors(mic)
    return True


def _arm_power_cycle_proof(
    mic,
    serial_arg: bytes,
    expected_configs: dict[int, dict[int, tuple[int, int]]],
    expected_presets: dict[int, int],
    encoder_mux_states: tuple[tuple[int, bool], ...] = ENCODER_MUX_STATES,
) -> bool:
    """
    Capture the canonical reopened-session state, then leave both encoders in live BiSS.

    A real power cycle must restore EEPROM startup mode SSI. If power was not
    cycled, post-cycle verification sees BiSS and fails. Reopening a session can
    normalize a small known set of interface/offset parameters, so validate
    that no other parameters change and use the normalized state for the exact
    post-power-cycle comparison.
    """
    for enc_idx, dig_out in encoder_mux_states:
        try:
            _clear_controller_errors(mic)
            mic.set_digital_output(dig_out)
            with _managed_encoder_session(serial_arg, enc_idx, "power-cycle proof") as handle:
                if handle is None:
                    return False

                ret = mu.MU_ReadParams(handle)
                _log_mu(f"Read live MODEA for encoder {enc_idx} power-cycle proof", ret, handle)
                if ret != MU_OK:
                    return False
                if not _verify_preset_readback(
                    handle,
                    f"encoder {enc_idx} power-cycle proof",
                    expected_presets[enc_idx],
                ):
                    return False

                reopened_config = _capture_stable_config(handle)
                written_config = expected_configs[enc_idx]
                missing = sorted(set(written_config) - set(reopened_config))
                added = sorted(set(reopened_config) - set(written_config))
                changed = sorted(
                    param_idx
                    for param_idx in set(written_config) & set(reopened_config)
                    if written_config[param_idx] != reopened_config[param_idx]
                )
                unexpected = sorted(
                    param_idx
                    for param_idx in set(missing) | set(added) | set(changed)
                    if param_idx not in MU_SESSION_NORMALIZED_PARAM_INDEXES
                )
                if (
                    len(reopened_config) < MU_MIN_STABLE_CONFIG_PARAMS
                    or unexpected
                ):
                    print(
                        f"[ERROR] Encoder {enc_idx} reopened session changed protected parameters: "
                        f"missing={missing} added={added} changed={changed} unexpected={unexpected}"
                    )
                    return False
                normalized = sorted(
                    param_idx
                    for param_idx in set(missing) | set(added) | set(changed)
                    if param_idx in MU_SESSION_NORMALIZED_PARAM_INDEXES
                )
                print(
                    f"[STATE] Encoder {enc_idx} canonical reopened-session image captured; "
                    f"session-normalized parameters={normalized}"
                )
                expected_configs[enc_idx] = reopened_config

                value_high = c_uint32(0)
                value_low = c_uint32(0)
                ret = mu.MU_GetParam(handle, MU_MODEA, byref(value_high), byref(value_low))
                _log_mu(f"Get live MODEA for encoder {enc_idx} power-cycle proof", ret, handle)
                if ret != MU_OK or int(value_low.value) != MU_BISS.value:
                    print(
                        f"[ERROR] Could not arm encoder {enc_idx} power-cycle proof: "
                        f"live_MODEA={int(value_low.value)}"
                    )
                    return False
                print(
                    f"[STATE] Encoder {enc_idx} power-cycle proof armed: "
                    "live MODEA=BiSS, EEPROM startup MODEA=SSI."
                )
        finally:
            _clear_controller_errors(mic)
    return True


def _capture_stable_config(handle: MU_Handle) -> dict[int, tuple[int, int]]:
    """Capture stable configuration parameters from the current VCO."""
    snapshot: dict[int, tuple[int, int]] = {}
    for param_idx in range(MU_STABLE_CONFIG_PARAM_LAST + 1):
        value_high = c_uint32(0)
        value_low = c_uint32(0)
        ret = mu.MU_GetParam(
            handle,
            c_uint32(param_idx),
            byref(value_high),
            byref(value_low),
        )
        if ret == MU_OK:
            snapshot[param_idx] = (int(value_high.value), int(value_low.value))
    return snapshot


def _verify_stable_config_preserved(
    before: dict[int, tuple[int, int]],
    after: dict[int, tuple[int, int]],
    label: str,
) -> bool:
    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(
        param_idx
        for param_idx in set(before) & set(after)
        if before[param_idx] != after[param_idx]
    )
    if (
        len(before) < MU_MIN_STABLE_CONFIG_PARAMS
        or len(after) < MU_MIN_STABLE_CONFIG_PARAMS
        or missing
        or added
        or changed
    ):
        print(
            f"[ERROR] Stable configuration changed during {label}: "
            f"before_count={len(before)} after_count={len(after)} "
            f"missing_params={missing} added_params={added} changed_params={changed}"
        )
        for param_idx in changed[:10]:
            print(
                f"[ERROR] param[{param_idx}] before={before[param_idx]} "
                f"after={after[param_idx]}"
            )
        return False
    print(f"[STATE] Stable configuration preserved during {label}: {len(before)} parameters")
    return True


def _write_vco_to_ram_and_verify(handle: MU_Handle, label: str, settle_s: float) -> bool:
    """Write the VCO using the compatible mode, then compare it with chip RAM."""
    expected = _capture_stable_config(handle)
    expected.pop(MU_HARD_REV_PARAM_INDEX, None)
    if len(expected) < MU_MIN_STABLE_CONFIG_PARAMS:
        print(
            f"[ERROR] Could not capture expected VCO configuration before {label}: "
            f"parameter_count={len(expected)}"
        )
        return False

    if write_params_with_verify(mu, handle) != MU_OK:
        return False
    time.sleep(settle_s)
    if not _checkpoint_ram(handle, label):
        return False

    actual = _capture_stable_config(handle)
    actual.pop(MU_HARD_REV_PARAM_INDEX, None)
    return _verify_stable_config_preserved(expected, actual, f"{label} RAM readback")


def _restore_runtime_ssi_best_effort(handle: MU_Handle, context: str) -> None:
    """Best-effort live-mode recovery without issuing unsupported SOFT_RESET."""
    if not _set_current_mode_best_effort(handle, MU_SSI, context):
        print(f"[WARN] Could not restore live SSI mode after {context}.")


def _restore_and_verify_controller_ssi(mic, dig_out: bool = False) -> bool:
    """Refresh MiControl SSI after MU sessions and require a ready live input."""
    if hasattr(mic, "restore_extended_ssi_mode") and not mic.restore_extended_ssi_mode():
        return False
    if hasattr(mic, "SSI_encoder") and not mic.SSI_encoder(False):
        print("[ERROR] Could not disable controller SSI before final refresh.")
        return False
    mic.set_digital_output(dig_out)
    time.sleep(0.25)
    _clear_controller_errors(mic)
    if hasattr(mic, "SSI_encoder") and not mic.SSI_encoder(True):
        print("[ERROR] Could not enable controller SSI during final refresh.")
        return False

    deadline = time.monotonic() + 5.0
    last_status = None
    last_direct = None
    last_actual = None
    while time.monotonic() < deadline:
        last_status = (
            mic.get_ssi_encoder_status()
            if hasattr(mic, "get_ssi_encoder_status")
            else None
        )
        last_direct = (
            mic.get_ssi_direct_position()
            if hasattr(mic, "get_ssi_direct_position")
            else None
        )
        last_actual = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
        print(
            "[STATE] Controller SSI refresh: "
            f"digital_output={dig_out} status={last_status} "
            f"direct_position={last_direct} steering_position={last_actual}"
        )
        if last_status == CONTROLLER_SSI_READY_STATUS:
            return True
        if (
            last_status in CONTROLLER_SSI_POSITION_VALID_STATUSES
            and last_direct is not None
            and last_actual is not None
        ):
            print(
                "[STATE] Controller SSI position readback is valid before ready status: "
                f"status={last_status} direct_position={last_direct} "
                f"steering_position={last_actual}"
            )
            return True
        time.sleep(0.5)

    print(
        "[ERROR] Controller SSI did not become ready after MU session recovery: "
        f"digital_output={dig_out} status={last_status} "
        f"direct_position={last_direct} steering_position={last_actual}"
    )
    return False


def _save_controller_zero_reference(mic, label: str) -> bool:
    if not hasattr(mic, "save_ssi_absolute_zero"):
        print("[WARN] Controller driver has no save_ssi_absolute_zero method.")
        return True
    if not mic.save_ssi_absolute_zero():
        print(f"[ERROR] Controller SSI zero reference was not saved after {label}.")
        return False
    print(f"[INFO] Controller SSI zero reference saved after {label}.")
    return True


def _restore_visual_zero_before_controller_save(
    mic,
    desired_angle: float,
    read_angle_fn,
) -> float:
    """Re-center the shaft before persisting the controller-side zero."""
    current_angle = float(read_angle_fn()) % 360.0
    check = _check_visual_zero_target(desired_angle, current_angle)
    print(
        "[STATE] Visual-zero check before controller zero save: "
        f"angle={check.angle_deg:.2f} deg "
        f"target={check.target_deg:.2f} deg "
        f"target_error={check.error_deg:+.2f} deg "
        f"tolerance=+/-{check.tolerance_deg:.2f} deg "
        f"ok={check.ok}"
    )
    if check.ok:
        return check.angle_deg

    print(
        "[STATUS] Shaft shifted before controller zero save; "
        "returning to visual zero before storing controller reference."
    )
    restored_angle = _move_to_visual_zero(
        mic,
        check.angle_deg,
        desired_angle,
        read_angle_fn,
        require_strict_target=True,
    )
    restored_check = _check_visual_zero_target(desired_angle, restored_angle)
    print(
        "[STATE] Visual-zero restored before controller zero save: "
        f"angle={restored_check.angle_deg:.2f} deg "
        f"target={restored_check.target_deg:.2f} deg "
        f"target_error={restored_check.error_deg:+.2f} deg "
        f"tolerance=+/-{restored_check.tolerance_deg:.2f} deg "
        f"ok={restored_check.ok}"
    )
    if not restored_check.ok:
        raise RuntimeError(
            "Could not restore visual zero before saving controller zero reference: "
            f"angle={restored_check.angle_deg:.2f} "
            f"target={restored_check.target_deg:.2f} "
            f"target_error={restored_check.error_deg:+.2f} deg "
            f"tolerance=+/-{restored_check.tolerance_deg:.2f} deg."
        )
    return restored_check.angle_deg


def _save_live_config_snapshot(handle: MU_Handle, enc_idx: int, label: str) -> bool:
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = CONFIG_BACKUP_DIR / f"encoder_{enc_idx}_{label}_{timestamp}.cfg"
    ret = mu.MU_SaveParams(handle, str(backup_path).encode("utf-8"))
    _log_mu(f"Save live config snapshot {backup_path}", ret, handle)
    return ret == MU_OK


def _preflight_zero_config_files(config_paths: tuple[Path, ...]) -> bool:
    """Validate every zero config before either encoder EEPROM is modified."""
    handle = MU_Handle()
    if not _open_mu_handle(handle):
        return False
    try:
        for config_path in config_paths:
            if not config_path.is_file():
                print(f"[ERROR] Required zero config is missing: {config_path}")
                return False
            revision = c_uint8(0)
            ret = mu.MU_ReadChipRevisionOfParameterFile(
                handle,
                str(config_path).encode("utf-8"),
                byref(revision),
            )
            _log_mu(f"Preflight zero config {config_path.name}", ret, handle)
            if ret != MU_OK:
                return False
            if int(revision.value) != MU_FORCED_REV:
                print(
                    f"[ERROR] Wrong chip revision in {config_path.name}: "
                    f"expected=0x{MU_FORCED_REV:02X} actual=0x{int(revision.value):02X}"
                )
                return False
        return True
    finally:
        _close_mu_handle(handle)


def _preflight_zero_encoder_sessions(
    mic,
    serial_arg: bytes,
    encoder_mux_states: tuple[tuple[int, bool], ...],
) -> bool:
    """Verify both physical encoder sessions before either EEPROM is modified."""
    for enc_idx, dig_out in encoder_mux_states:
        try:
            _clear_controller_errors(mic)
            mic.set_digital_output(dig_out)
            time.sleep(0.2)
            with _managed_encoder_session(serial_arg, enc_idx, "zeroing preflight") as handle:
                if handle is None:
                    return False
                if not _checkpoint_ram(handle, f"encoder {enc_idx} zeroing preflight"):
                    return False
                print(
                    f"[STATE] Encoder {enc_idx} communication preflight passed: "
                    f"digital_output={dig_out}"
                )
        finally:
            _clear_controller_errors(mic)
    return True


def _load_initial_config_to_encoder(
    handle: MU_Handle,
    mic,
    serial_arg: bytes,
    enc_idx: int,
    dig_out: bool,
    switch_to_ssi: bool,
    settle_s: float,
) -> bool:
    _clear_controller_errors(mic)
    mic.set_digital_output(dig_out)
    time.sleep(LOAD_CONFIG_MUX_SETTLE_S)

    opened = False
    for attempt in range(1, LOAD_CONFIG_OPEN_ATTEMPTS + 1):
        print(
            f"[INFO] Opening MU session for encoder {enc_idx}: "
            f"digital_output={dig_out} attempt={attempt}/{LOAD_CONFIG_OPEN_ATTEMPTS}"
        )
        if _open_encoder_session(handle, serial_arg, enc_idx, "init"):
            opened = True
            break
        _clear_controller_errors(mic)
        time.sleep(LOAD_CONFIG_MUX_SETTLE_S * attempt)

    if not opened:
        return False
    try:
        if not _load_config_0_or_abort(handle, "Load config", enc_idx=enc_idx):
            return False
        if not _print_vco_state(handle, f"VCO after encoder {enc_idx} config load (not yet in RAM)"):
            return False

        if not _write_vco_to_ram_and_verify(
            handle,
            f"encoder {enc_idx} config write",
            settle_s,
        ):
            return False

        if switch_to_ssi:
            if not write_to_SSi(mu, handle):
                return False
            print(
                f"[INFO] Encoder {enc_idx} config saved to EEPROM with startup MODEA SSI. "
                "Configuration succeeds only if the controller does not report -1092."
            )
        return True
    finally:
        _close_mu_handle(handle)

def upload_config_0_both(mu: ctypes.CDLL, handle: MU_Handle, mic, serial_last4: str) -> bool:
    """Upload CONFIG_PATH_0 to both encoders (no preset)."""
    serial_arg = _iface_option(serial_last4)

    for enc_idx, dig_out in ENCODER_MUX_STATES:
        if not _load_initial_config_to_encoder(
            handle,
            mic,
            serial_arg,
            enc_idx,
            dig_out,
            switch_to_ssi=False,
            settle_s=0.2,
        ):
            return False

    _clear_controller_errors(mic)
    return True

def write_just_conf(mu: ctypes.CDLL, handle: MU_Handle, mic, serial_last4) -> bool:
    serial_arg = _iface_option(serial_last4)  

    _clear_controller_errors(mic)

    def write_one_encoder(enc_idx: int, dig_out: bool, settle_s: float) -> bool:
        mic.set_digital_output(dig_out)

        ret = mu.MU_Open(byref(handle))
        _log_mu("Open", ret, handle)
        if ret != MU_OK:
            return False

        try:
            if not _set_mb5u_interface(handle, serial_arg):
                return False

            ret = mu.MU_UseRevision(handle, MU_FORCED_REV)
            _log_mu(f"Use revision 0x{MU_FORCED_REV:02X}", ret, handle)
            if ret != MU_OK:
                return False

            if not _enter_biss(handle):
                print(f"[ERROR] Unable to enter BiSS mode during init (encoder {enc_idx}).")
                return False

            ret = mu.MU_Initialize(handle)
            _log_mu("Initialize", ret, handle)
            if ret != MU_OK:
                return False

            ret = mu.MU_LoadParams(handle, CONFIG_PATH_0)
            _log_mu("Load config", ret, handle)
            if ret != MU_OK:
                return False

            if write_params_with_verify(mu, handle) != MU_OK:
                return False
            time.sleep(settle_s)

            if not write_to_SSi(mu, handle):
                return False

            return True
        finally:
            _log_mu("Close", mu.MU_Close(handle), handle)
            _clear_controller_errors(mic)

    if not write_one_encoder(1, True, 0.5):
        return False
    if not write_one_encoder(2, False, 0.2):
        return False

    _clear_controller_errors(mic)
    return True

def read_angle(samples: int = 20, timeout_s: float | None = 20.0) -> float:
    print(f"[STATUS] Waiting {ZERO_CAMERA_SETTLE_S:.1f}s for camera angle to stabilize.")
    time.sleep(ZERO_CAMERA_SETTLE_S)
    print(
        "[STATUS] Reading camera angle for zeroing "
        f"({samples} samples, timeout {timeout_s if timeout_s is not None else 'none'}s)."
    )
    angle = AngleDetection(debug=False, return_after=samples, timeout_s=timeout_s)
    if angle is None:
        raise RuntimeError("Could not measure steering angle for zeroing.")
    angle = float(angle)
    print(f"[INFO] Camera angle for zeroing: {angle:.2f} deg")
    return angle


def wait_for_power_cycle_console(_timeout_s: float) -> bool:
    input("[STATUS] Power-cycle the supply, then press Enter to verify EEPROM: ")
    return True


def write_des_zero_process(
    serial_last4: str = "",
    node: int = 50,
    desired_angle: float = 270.0,
    can_bitrate: int = 125,
    read_angle_fn=None,
    prepare_controller_fn=None,
    power_cycle_wait_fn=None,
    can=None,
    mic=None,
    preserve_current_encoder_config: bool = True,
    result_callback=None,
) -> bool:
    read_angle_fn = read_angle_fn or read_angle
    if power_cycle_wait_fn is None:
        print(
            "[ERROR] Zeroing requires a real post-write power cycle to verify EEPROM, "
            "but no power-cycle confirmation callback was provided."
        )
        return False
    if (can is None) != (mic is None):
        raise ValueError("Pass both can and mic, or pass neither.")
    owns_controller = can is None
    if owns_controller:
        can = DriverCan(can_bitrate=can_bitrate)
        mic = MicontrolF35_CAN(can=can.can_network, node=node)
        if not mic.added_node:
            can.close_can()
            raise RuntimeError(f"Could not add CAN node {node}.")
        mic.enabled(True)
    elif not mic.added_node:
        raise RuntimeError(f"CAN node {node} is not available.")

    completed_encoder_eeprom: list[int] = []
    expected_eeprom_configs: dict[int, dict[int, tuple[int, int]]] = {}
    expected_eeprom_presets: dict[int, int] = {}
    try:
        serial_arg = _iface_option(serial_last4)

        angle_deg = float(read_angle_fn())
        print(f"[INFO] Measured steering angle before visual-zero move: {angle_deg:.2f} deg")
        print(
            "[INFO] Visual-zero motion uses camera verification and does not require "
            "controller SSI-ready status before encoder zero writing."
        )
        _clear_controller_errors(mic)
        motion_reference_dig_out = False
        mic.set_digital_output(motion_reference_dig_out)
        mic.enabled(False)
        angle_deg = _move_to_visual_zero(
            mic,
            angle_deg,
            desired_angle,
            read_angle_fn,
            require_strict_target=True,
        )
        visual_check = _check_visual_zero_target(desired_angle, angle_deg)
        if result_callback is not None:
            result_callback(
                {
                    "stage": "zero_write_position",
                    "angle_deg": visual_check.angle_deg,
                    "target_deg": visual_check.target_deg,
                    "error_deg": visual_check.error_deg,
                    "tolerance_deg": visual_check.tolerance_deg,
                    "ok": visual_check.ok,
                }
            )
        print(
            f"[INFO] Measured steering angle used for zero write: "
            f"angle={visual_check.angle_deg:.2f} deg "
            f"target={visual_check.target_deg:.2f} deg "
            f"target_error={visual_check.error_deg:+.2f} deg "
            f"tolerance=+/-{visual_check.tolerance_deg:.2f} deg "
            f"ok={visual_check.ok}"
        )
        if not visual_check.ok:
            raise RuntimeError(
                "Visual zero move stopped outside the allowed target tolerance; "
                "encoder zero was not written: "
                f"angle={visual_check.angle_deg:.2f} target={visual_check.target_deg:.2f} "
                f"target_error={visual_check.error_deg:+.2f} deg "
                f"tolerance=+/-{visual_check.tolerance_deg:.2f} deg."
            )
        print(
            "[INFO] Zero save sequence at desired physical position: "
            + (
                "use current calibrated encoder config -> write preset command -> "
                "BiSS Write EEPROM -> SSI Write EEPROM."
                if preserve_current_encoder_config
                else "load matching miControl/MU config -> BiSS Write RAM -> "
                "write preset command -> BiSS Write EEPROM -> SSI Write EEPROM."
            )
        )

        mic.enabled(False)
        print(
            "[INFO] Controller drive disabled at visual zero while writing encoder zero."
        )
        zero_encoder_mux_states = ENCODER_MUX_STATES
        zero_plan = ZERO_PRESET_PLAN
        if preserve_current_encoder_config:
            print(
                "[INFO] Encoder zero plan: preserve each encoder's current live "
                "calibrated configuration and update only zero-related parameters; "
                f"digital_output={zero_plan[0][1]} preset {zero_plan[0][3]}; "
                f"digital_output={zero_plan[1][1]} preset {zero_plan[1][3]}."
            )
        else:
            print(
                "[INFO] Encoder zero plan: "
                f"digital_output={zero_plan[0][1]} uses {zero_plan[0][2].name} and preset {zero_plan[0][3]}; "
                f"digital_output={zero_plan[1][1]} uses {zero_plan[1][2].name} and preset {zero_plan[1][3]}."
            )
            if not _preflight_zero_config_files(
                tuple(config_path for _, _, config_path, _ in zero_plan)
            ):
                return False
        if not _preflight_zero_encoder_sessions(
            mic,
            serial_arg,
            zero_encoder_mux_states,
        ):
            print("[ERROR] Both encoder sessions must pass preflight before zero writing.")
            return False

        for enc_idx, dig_out, config_path, preset_ticks in zero_plan:
            preset_ticks &= 0xFFF
            encoder_complete = False

            def restore_if_incomplete(handle):
                if not encoder_complete:
                    _restore_runtime_ssi_best_effort(
                        handle,
                        f"encoder {enc_idx} zeroing failure",
                    )

            try:
                _clear_controller_errors(mic)
                mic.set_digital_output(dig_out)
                with _managed_encoder_session(
                    serial_arg,
                    enc_idx,
                    "zeroing",
                    restore_if_incomplete,
                ) as handle:
                    if handle is None:
                        return False
                    if not _checkpoint_ram(handle, "original live state before zeroing"):
                        return False
                    if not _save_live_config_snapshot(handle, enc_idx, "original_before_zero"):
                        return False

                    if preserve_current_encoder_config:
                        print(
                            f"[INFO] Preserving encoder {enc_idx} current calibrated "
                            "configuration for zero write; no template zero config loaded."
                        )
                    else:
                        if not _load_zero_config_for_zero(
                            handle,
                            serial_arg,
                            enc_idx,
                            config_path,
                        ):
                            return False

                    if not _save_live_config_snapshot(handle, enc_idx, "zero_input"):
                        return False

                    zero_input_config = _capture_stable_config(handle)
                    if len(zero_input_config) < MU_MIN_STABLE_CONFIG_PARAMS:
                        print(
                            f"[ERROR] Could not capture encoder {enc_idx} zero-input "
                            "configuration before zero write."
                        )
                        return False

                    expected_eeprom_config = _write_zero_preset_to_encoder_eeprom(
                        handle,
                        enc_idx,
                        preset_ticks,
                    )
                    if expected_eeprom_config is None:
                        return False
                    completed_encoder_eeprom.append(enc_idx)
                    if preserve_current_encoder_config and not _verify_zero_write_preserved_nonzero_config(
                        zero_input_config,
                        expected_eeprom_config,
                        f"encoder {enc_idx} calibration-preserving zero write",
                    ):
                        return False
                    expected_eeprom_configs[enc_idx] = expected_eeprom_config
                    expected_eeprom_presets[enc_idx] = preset_ticks
                    print(
                        f"[STATE] Encoder {enc_idx} zero/full configuration saved to EEPROM; "
                        f"startup MODEA=SSI expected_preset={preset_ticks}"
                    )

                    if not _save_live_config_snapshot(handle, enc_idx, "after_zero"):
                        return False
                    encoder_complete = True
            finally:
                _clear_controller_errors(mic)

        if not _arm_power_cycle_proof(
            mic,
            serial_arg,
            expected_eeprom_configs,
            expected_eeprom_presets,
            zero_encoder_mux_states,
        ):
            print("[ERROR] Could not arm post-zero power-cycle proof.")
            return False

        print(
            "[STATUS] Both encoder EEPROM writes completed. A real supply power cycle is "
            "required now for EEPROM verification."
        )
        try:
            mic.enabled(False)
        except Exception:
            pass
        try:
            can.close_can()
        except Exception:
            pass
        can = None
        mic = None

        if not power_cycle_wait_fn(ZERO_POWER_CYCLE_CONFIRM_TIMEOUT_S):
            print("[ERROR] Timed out waiting for power-cycle confirmation after zero write.")
            return False

        print("[INFO] Power-cycle confirmed. Reconnecting controller for EEPROM verification.")
        can = DriverCan(can_bitrate=can_bitrate)
        mic = MicontrolF35_CAN(can=can.can_network, node=node)
        if not mic.added_node:
            print(f"[ERROR] Could not add CAN node {node} after power cycle.")
            return False
        mic.enabled(True)
        if not _verify_eeprom_after_power_cycle(
            mic,
            serial_arg,
            expected_eeprom_configs,
            expected_eeprom_presets,
            zero_encoder_mux_states,
        ):
            print("[ERROR] Encoder EEPROM verification failed after power cycle.")
            return False
        print("[INFO] Both encoder EEPROM images verified after power cycle.")
        if not _restore_and_verify_controller_ssi(mic, dig_out=False):
            print("[ERROR] Controller SSI is not operational after zero EEPROM verification.")
            return False
        print("[INFO] Controller SSI is operational after zero EEPROM verification.")
        controller_zero_angle = _restore_visual_zero_before_controller_save(
            mic,
            desired_angle,
            read_angle_fn,
        )
        if not _save_controller_zero_reference(mic, "encoder zero EEPROM verification"):
            return False
        if not _verify_controller_zero_reference(mic, "encoder zero EEPROM verification"):
            return False

        final_visual_angle = float(read_angle_fn()) % 360.0
        final_visual_check = _check_visual_zero_target(desired_angle, final_visual_angle)
        final_visual_drift = _visual_angle_distance_deg(controller_zero_angle, final_visual_angle)
        if result_callback is not None:
            result_callback(
                {
                    "stage": "final_visual_verification",
                    "angle_deg": final_visual_check.angle_deg,
                    "target_deg": final_visual_check.target_deg,
                    "error_deg": final_visual_check.error_deg,
                    "tolerance_deg": final_visual_check.tolerance_deg,
                    "ok": final_visual_check.ok,
                    "drift_from_controller_zero_deg": final_visual_drift,
                }
            )
        print(
            f"[STATE] Final visual-zero verification: "
            f"angle={final_visual_check.angle_deg:.2f} deg "
            f"target={final_visual_check.target_deg:.2f} deg "
            f"target_error={final_visual_check.error_deg:+.2f} deg "
            f"tolerance=+/-{final_visual_check.tolerance_deg:.2f} deg "
            f"target_ok={final_visual_check.ok} "
            f"drift_from_controller_zero_position={final_visual_drift:+.2f} deg "
            f"fluctuation_tolerance=+/-{ZERO_VISUAL_MEASUREMENT_FLUCTUATION_TOLERANCE_DEG:.2f} deg"
        )
        if not final_visual_check.ok:
            raise RuntimeError(
                "Final visual angle is outside the zero target tolerance after "
                "EEPROM/controller-zero verification: "
                f"angle={final_visual_check.angle_deg:.2f} "
                f"target={final_visual_check.target_deg:.2f} "
                f"target_error={final_visual_check.error_deg:+.2f} deg "
                f"tolerance=+/-{final_visual_check.tolerance_deg:.2f} deg."
            )
        if abs(final_visual_drift) > ZERO_VISUAL_MEASUREMENT_FLUCTUATION_TOLERANCE_DEG:
            raise RuntimeError(
                "Motor moved away from the visual position used for controller zero save: "
                f"angle_used_for_controller_zero={controller_zero_angle:.2f} "
                f"current_angle={final_visual_check.angle_deg:.2f} "
                f"drift={final_visual_drift:+.2f} deg "
                f"tolerance=+/-{ZERO_VISUAL_MEASUREMENT_FLUCTUATION_TOLERANCE_DEG:.2f} deg."
            )

        print(
            "[INFO] Encoder zero process passed: visual position held, "
            "calibration-mapped encoder 1 preset=0 and encoder 2 preset=0 "
            "verified from EEPROM."
        )
        print("Zeroing completed")
        return True
    finally:
        if 0 < len(completed_encoder_eeprom) < len(ENCODER_MUX_STATES):
            print(
                "[CRITICAL] Zeroing stopped after only some encoder EEPROM writes completed: "
                f"completed_encoders={completed_encoder_eeprom}"
            )
        try:
            if mic:
                mic.enabled(False)
        except Exception:
            pass
        try:
            if can:
                can.close_can()
        except Exception:
            pass

def main(serial_last4: str = "", node: int = 50, desired_angle: float = 270.0):

    # === Flash config from SteeringScript.py ===
    can_bitrate = 125  # kbit/s
    can = DriverCan(can_bitrate=can_bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        print("[ERROR] Could not add CAN node.")
        return

    print("[INFO] Preparing controller for zeroing.")
    if not mic.SSI_encoder(True):
        print("[ERROR] Could not enable controller SSI encoder before zeroing.")
        can.close_can()
        return
    _clear_controller_errors(mic)
    print("[INFO] Configuration applied and errors cleared.")

    time.sleep(0.5)  # allow encoder to power up before opening MU handle

    handle = MU_Handle()
    if not upload_config_0_both(mu, handle, mic, serial_last4):
        print("[ERROR] Could not upload initial RAM configuration to both encoders.")
        can.close_can()
        return
    time.sleep(0.2)
    write_des_zero_process(
        serial_last4=serial_last4,
        node=node,
        desired_angle=desired_angle,
        can_bitrate=can_bitrate,
        power_cycle_wait_fn=wait_for_power_cycle_console,
        can=can,
        mic=mic,
    )

if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="config zero flash")
    try:
        main(serial_last4="")
    finally:
        restore_sigint()
