import ctypes
from ctypes import (
    c_int, c_int8, c_long, c_uint8, c_uint16, c_uint32, c_ulong, c_size_t,
    c_double, c_bool, c_char_p, c_void_p, POINTER, byref
)
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Optional

from calibration_quality import (
    AcquisitionTiming,
    AnalogResidualRun,
    CalibrationMetrics,
    ResidualVector,
    build_quality_report,
    evaluate_quality,
)
from drivers.driver_arduino import DriverArduino
from drivers.driver_miControlF35 import MicontrolF35_CAN
from drivers.driver_can import DriverCan
from drivers.driver_mc import DSACompat
from drivers.driver_cam_st import AngleDetection
from drivers.driver_owon import power_cycle_owon_spe6053
from config_processing import nmt_reset_node_compat
from interrupt_guard import install_deferred_keyboard_interrupt
from FlashSteeringScript import import_script_via_qr, load_config_function


# =====================================================================================
# MU paths (yours)
# =====================================================================================
DLL_PATH = Path(r"/home/mobotic/Internal Projects/StCalibration-Linux/MU/MU_3SL_interface_3.4.1/bin/linux/x86_64/libMU_3SL_interface.so.3.4.1")
STEERING_ENCODER_CONFIG_PATH = Path(
    r"/home/mobotic/Internal Projects/StCalibration-Linux/resources/ic-mu_steering_encoder_front.cfg"
)
CONFIG_PATH_1 = str(STEERING_ENCODER_CONFIG_PATH).encode("utf-8")
CONFIG_PATH_2 = str(STEERING_ENCODER_CONFIG_PATH).encode("utf-8")
PRESERVED_TEMP_CONFIG_DIR = Path(
    r"/home/mobotic/Internal Projects/StCalibration-Linux/MU/calib_logs/preserved_temp_configs"
)
CALIBRATED_CONFIG_PATH_1 = Path(
    PRESERVED_TEMP_CONFIG_DIR / "encoder_1_calibrated_preserved.cfg"
)
CALIBRATED_CONFIG_PATH_2 = Path(
    PRESERVED_TEMP_CONFIG_DIR / "encoder_2_calibrated_preserved.cfg"
)
ZERO_RETURN_SETTLE_S = 2.0
ZERO_RETURN_TIMEOUT_S = 6.0
ZERO_POSITION_TOLERANCE_COUNTS = 3
ZERO_RETURN_RPM = 1000
MU_OFF_ABZ_UNITS_PER_OFF_POS_TICK = 4096
ZERO_COMPENSATION_MAX_ATTEMPTS = 3

EXPORT_DIR_1 = Path(
    r"/home/mobotic/Internal Projects/StCalibration-Linux/MU/calib_logs/enc_1"
)
EXPORT_DIR_2 = Path(
    r"/home/mobotic/Internal Projects/StCalibration-Linux/MU/calib_logs/enc_2"
)

mu = ctypes.CDLL(str(DLL_PATH))

MU_Handle = c_void_p
MU_Error = c_uint32

# Interface enum (per your setup)
MU_MB5U = c_uint32(4)

# Commands (per interface manual Table 14)
MU_CMD_WRITE_ALL = c_uint32(1)
MU_CMD_WRITE_OFF = c_uint32(2)
MU_CMD_ABS_RESET = c_uint32(3)
MU_CMD_CRC_CALC = c_uint32(14)
MU_CMD_SOFT_PRES = c_uint32(8)
MU_CMD_SOFT_E2P_PRES = c_uint32(9)  # IMPORTANT: store preset into EEPROM

# Param enums (your usage)
MU_MODEA = c_uint32(16)
MU_OFF_ABZ = c_uint32(56)
MU_OFF_POS = c_uint32(57)
MU_OFF_COM = c_uint32(58)
MU_OFF_UVW = c_uint32(67)
MU_PRES_POS = c_uint32(68)
MU_MPC = c_uint32(29)
MU_BISS = c_uint32(0x0002)
MU_SSI = c_uint32(0x0004)

# Write/Verify flags
MU_SETONLY = c_uint32(0)
MU_WRITE = c_uint32(1)
MU_VERIFY = c_uint32(2)

# EEPROM area (Table 17)
MU_E2P_CFG = c_uint32(0)

MU_OK = 0
MU_FORCED_REV = 0x20  # your known chip revision

MU_CALIBRATION_ANALYZE_RESULT_LOG_ERRORS = 1
MU_CALIBRATION_ANALYZE_RESULT_LOG_WARNINGS = 2
MU_CALIBRATION_ANALYZE_RESULT_LOG_NOTE = 4
MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL = (
    MU_CALIBRATION_ANALYZE_RESULT_LOG_ERRORS
    | MU_CALIBRATION_ANALYZE_RESULT_LOG_WARNINGS
    | MU_CALIBRATION_ANALYZE_RESULT_LOG_NOTE
)

MU_ADJUSTMENT_MESSAGE_LOG_ERRORS = 1
MU_ADJUSTMENT_MESSAGE_LOG_WARNINGS = 2
MU_ADJUSTMENT_MESSAGE_LOG_NOTE = 4
MU_ADJUSTMENT_MESSAGE_LOG_ALL = (
    MU_ADJUSTMENT_MESSAGE_LOG_ERRORS
    | MU_ADJUSTMENT_MESSAGE_LOG_WARNINGS
    | MU_ADJUSTMENT_MESSAGE_LOG_NOTE
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


# =====================================================================================
# Calibration structs (from your St_Calib_GUI / SDK header)
# =====================================================================================
class MU_Calibration_RelativeAnalogTrackAdjustments(ctypes.Structure):
    _fields_ = [
        ("cosineGain_lsb",   c_double),
        ("sineOffset_lsb",   c_double),
        ("cosineOffset_lsb", c_double),
        ("phase_lsb",        c_double),
    ]


class MU_Calibration_AnalogTrackAdjustments(ctypes.Structure):
    _fields_ = [
        ("cosineGain", c_uint8),
        ("sineOffset", c_uint8),
        ("cosineOffset", c_uint8),
        ("phase", c_uint8),
        ("phaseRange", c_uint8),
    ]


class MU_Calibration_NoniusTrackOffsetTable(ctypes.Structure):
    _fields_ = [
        ("spoBase", c_int8),
        ("spo",     c_int8 * 16),
    ]


# =====================================================================================
# Prototypes (your style)
# =====================================================================================
mu.MU_Open.argtypes = [POINTER(MU_Handle)]
mu.MU_Open.restype = MU_Error

mu.MU_Close.argtypes = [MU_Handle]
mu.MU_Close.restype = MU_Error

mu.MU_SetInterface.argtypes = [MU_Handle, c_uint32, c_char_p]
mu.MU_SetInterface.restype = MU_Error

mu.MU_Initialize.argtypes = [MU_Handle]
mu.MU_Initialize.restype = MU_Error

mu.MU_UseRevision.argtypes = [MU_Handle, c_uint8]
mu.MU_UseRevision.restype = MU_Error

mu.MU_ReadChipRevision.argtypes = [MU_Handle, POINTER(c_uint8)]
mu.MU_ReadChipRevision.restype = MU_Error

mu.MU_LoadParams.argtypes = [MU_Handle, c_char_p]
mu.MU_LoadParams.restype = MU_Error

mu.MU_SaveParams.argtypes = [MU_Handle, c_char_p]
mu.MU_SaveParams.restype = MU_Error

mu.MU_WriteParams.argtypes = [MU_Handle, c_bool, POINTER(c_bool)]
mu.MU_WriteParams.restype = MU_Error

mu.MU_ReadParams.argtypes = [MU_Handle]
mu.MU_ReadParams.restype = MU_Error

mu.MU_SetParam.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32, c_uint32]
mu.MU_SetParam.restype = MU_Error

mu.MU_GetParam.argtypes = [MU_Handle, c_uint32, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_GetParam.restype = MU_Error

mu.MU_WriteCmdRegister.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteCmdRegister.restype = MU_Error

mu.MU_WriteEeprom.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteEeprom.restype = MU_Error

mu.MU_WriteSwitchCommand.argtypes = [MU_Handle, c_uint32, c_uint32]
mu.MU_WriteSwitchCommand.restype = MU_Error

mu.MU_GetLastError.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32), c_char_p]
mu.MU_GetLastError.restype = MU_Error

# BiSS switching
mu.MU_SwitchToBiss.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_SwitchToBiss.restype = MU_Error

mu.MU_SwitchToBiss_ex.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_bool)]
mu.MU_SwitchToBiss_ex.restype = MU_Error

# Preset
mu.MU_CalcPRES_POS.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32]
mu.MU_CalcPRES_POS.restype = MU_Error

mu.MU_GetPRES_POS.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_uint32)]
mu.MU_GetPRES_POS.restype = MU_Error

# Calibration API
mu.MU_activateCalibrationConfig.argtypes = [MU_Handle]
mu.MU_activateCalibrationConfig.restype = MU_Error

mu.MU_deactivateCalibrationConfig.argtypes = [MU_Handle]
mu.MU_deactivateCalibrationConfig.restype = MU_Error

mu.MU_getCalibration.argtypes = [MU_Handle]
mu.MU_getCalibration.restype = c_void_p

mu.MU_setCalibration.argtypes = [MU_Handle, c_void_p]
mu.MU_setCalibration.restype = MU_Error

mu.MU_Calibration_delete.argtypes = [c_void_p]
mu.MU_Calibration_delete.restype = None

mu.MU_acquireRawData.argtypes = [
    MU_Handle,
    POINTER(c_uint16),  # master
    POINTER(c_uint16),  # nonius
    c_size_t,           # samples
    c_uint32,           # reserved
    c_double,           # frame_cycle_time_s
    c_double,           # clock_frequency_hz
]
mu.MU_acquireRawData.restype = c_int  # 0 = OK

mu.MU_Calibration_analyzeRawData.argtypes = [c_void_p, POINTER(c_uint16), POINTER(c_uint16), c_size_t]
mu.MU_Calibration_analyzeRawData.restype = c_void_p  # analyze result ptr

mu.MU_CalibrationAnalyzeResult_delete.argtypes = [c_void_p]
mu.MU_CalibrationAnalyzeResult_delete.restype = None

mu.MU_Calibration_getAnalyzeResultLog.argtypes = [c_void_p, c_char_p, c_size_t, c_uint32]
mu.MU_Calibration_getAnalyzeResultLog.restype = c_size_t

mu.MU_Calibration_isAnalogAnalysesValid.argtypes = [c_void_p]
mu.MU_Calibration_isAnalogAnalysesValid.restype = c_bool

mu.MU_Calibration_isNoniusAnalysesValid.argtypes = [c_void_p]
mu.MU_Calibration_isNoniusAnalysesValid.restype = c_bool

mu.MU_Calibration_getRelativeMasterTrackAdjustments.argtypes = [c_void_p, POINTER(MU_Calibration_RelativeAnalogTrackAdjustments)]
mu.MU_Calibration_getRelativeMasterTrackAdjustments.restype = None

mu.MU_Calibration_getRelativeNoniusTrackAdjustments.argtypes = [c_void_p, POINTER(MU_Calibration_RelativeAnalogTrackAdjustments)]
mu.MU_Calibration_getRelativeNoniusTrackAdjustments.restype = None

if hasattr(mu, "MU_Calibration_setCurrentAnalogTrackAdjustments"):
    mu.MU_Calibration_setCurrentAnalogTrackAdjustments.argtypes = [
        c_void_p,
        POINTER(MU_Calibration_AnalogTrackAdjustments),
        POINTER(MU_Calibration_AnalogTrackAdjustments),
    ]
    mu.MU_Calibration_setCurrentAnalogTrackAdjustments.restype = c_bool

mu.MU_Calibration_adjustAnalogByAnalyzeResult.argtypes = [c_void_p, c_void_p]
mu.MU_Calibration_adjustAnalogByAnalyzeResult.restype = c_bool

mu.MU_Calibration_isAnalogAnalyzeResultAdjustable.argtypes = [c_void_p, c_void_p, c_char_p, c_size_t, c_uint32]
mu.MU_Calibration_isAnalogAnalyzeResultAdjustable.restype = c_bool

mu.MU_Calibration_getOptimizedNoniusTrackOffsetTable.argtypes = [c_void_p, POINTER(MU_Calibration_NoniusTrackOffsetTable)]
mu.MU_Calibration_getOptimizedNoniusTrackOffsetTable.restype = None

mu.MU_Calibration_setCurrentNoniusTrackOffsetTable.argtypes = [c_void_p, POINTER(MU_Calibration_NoniusTrackOffsetTable)]
mu.MU_Calibration_setCurrentNoniusTrackOffsetTable.restype = c_bool

mu.MU_Calibration_numberOfNoniusCurveSamples.argtypes = [c_void_p]
mu.MU_Calibration_numberOfNoniusCurveSamples.restype = c_size_t

mu.MU_Calibration_noniusPhaseError.argtypes = [c_void_p]
mu.MU_Calibration_noniusPhaseError.restype = POINTER(c_long)

mu.MU_Calibration_noniusPhaseMarginMax.argtypes = [c_void_p]
mu.MU_Calibration_noniusPhaseMarginMax.restype = c_long

mu.MU_Calibration_noniusPhaseMarginMin.argtypes = [c_void_p]
mu.MU_Calibration_noniusPhaseMarginMin.restype = c_long

mu.MU_Calibration_noniusPhaseRangeLimit.argtypes = [c_void_p]
mu.MU_Calibration_noniusPhaseRangeLimit.restype = c_long

mu.MU_Calibration_noniusUpperPhaseMargin.argtypes = [c_void_p]
mu.MU_Calibration_noniusUpperPhaseMargin.restype = c_double

mu.MU_Calibration_noniusLowerPhaseMargin.argtypes = [c_void_p]
mu.MU_Calibration_noniusLowerPhaseMargin.restype = c_double

if hasattr(mu, "MU_Interface_nearestPossibleFrameCycleTime"):
    mu.MU_Interface_nearestPossibleFrameCycleTime.argtypes = [c_uint32, c_double]
    mu.MU_Interface_nearestPossibleFrameCycleTime.restype = c_double

if hasattr(mu, "MU_Interface_nearestPossibleClockFreq"):
    mu.MU_Interface_nearestPossibleClockFreq.argtypes = [c_uint32, c_double]
    mu.MU_Interface_nearestPossibleClockFreq.restype = c_double


# =====================================================================================
# MU helpers (your style)
# =====================================================================================
def _mu_last_error(handle) -> str:
    last_error = c_uint32(0)
    err_type = c_uint32(0)
    buf = ctypes.create_string_buffer(1024)
    mu.MU_GetLastError(handle, byref(last_error), byref(err_type), buf)
    err_code = int(last_error.value)
    err_type_code = int(err_type.value)
    err_name = MU_ERROR_NAMES.get(err_code, f"#{err_code}")
    type_name = MU_ERROR_TYPE_NAMES.get(err_type_code, f"#{err_type_code}")
    return f"code={err_code}({err_name}) type={err_type_code}({type_name}) text='{buf.value.decode(errors='ignore')}'"


def _log_mu(desc: str, ret: int, handle=None) -> None:
    if ret != MU_OK:
        name = MU_ERROR_NAMES.get(int(ret), f"#{int(ret)}")
        extra = f" ({_mu_last_error(handle)})" if handle else ""
        print(f"[ERROR] {desc} failed (code={int(ret)}:{name}){extra}")
    else:
        print(desc)


@dataclass(frozen=True)
class ProtectedMuParam:
    index: int
    name: str
    high: int
    low: int


@dataclass(frozen=True)
class ProtectedZeroState:
    params: dict[int, ProtectedMuParam]
    derived_params: dict[int, ProtectedMuParam]
    real_pres_pos_high: int
    real_pres_pos_low: int


PROTECTED_MU_PARAMS = (
    (MU_OFF_ABZ.value, "OFF_ABZ"),
    (MU_OFF_UVW.value, "OFF_UVW"),
    (MU_PRES_POS.value, "PRES_POS"),
)

MONITORED_DERIVED_ZERO_PARAMS = (
    (MU_OFF_POS.value, "OFF_POS"),
    (MU_OFF_COM.value, "OFF_COM"),
)


def _format_protected_param(param: ProtectedMuParam) -> str:
    combined = (param.high << 32) | param.low
    return (
        f"{param.name:<8} high=0x{param.high:08X} "
        f"low=0x{param.low:08X} low12={combined & 0xFFF}"
    )


def _read_param(handle: MU_Handle, param_idx: int, name: str) -> ProtectedMuParam | None:
    value_high = c_uint32(0)
    value_low = c_uint32(0)
    ret = mu.MU_GetParam(
        handle,
        c_uint32(param_idx),
        byref(value_high),
        byref(value_low),
    )
    if ret != MU_OK:
        _log_mu(f"GetParam {name}", ret, handle)
        return None
    return ProtectedMuParam(
        index=param_idx,
        name=name,
        high=int(value_high.value),
        low=int(value_low.value),
    )


def _capture_protected_params(
    handle: MU_Handle,
    label: str,
) -> ProtectedZeroState | None:
    print(f"\n[CHECKPOINT] Protected MU params: {label}")
    snapshot: dict[int, ProtectedMuParam] = {}
    for param_idx, name in PROTECTED_MU_PARAMS:
        param = _read_param(handle, param_idx, name)
        if param is None:
            return None
        snapshot[param_idx] = param
        print(f"[STATE] {_format_protected_param(param)}")

    for param_idx, name in MONITORED_DERIVED_ZERO_PARAMS:
        param = _read_param(handle, param_idx, name)
        if param is None:
            return None
        snapshot[param_idx] = param
        print(f"[STATE] {_format_protected_param(param)} (monitored, regenerated)")

    value_high = c_uint32(0)
    value_low = c_uint32(0)
    ret = mu.MU_GetPRES_POS(handle, byref(value_high), byref(value_low))
    _log_mu(f"Get real PRES_POS: {label}", ret, handle)
    if ret != MU_OK:
        return None
    print(
        f"[STATE] REAL_PRES_POS high=0x{int(value_high.value):08X} "
        f"low=0x{int(value_low.value):08X} low12={int(value_low.value) & 0xFFF}"
    )

    return ProtectedZeroState(
        params={
            param_idx: snapshot[param_idx]
            for param_idx, _name in PROTECTED_MU_PARAMS
        },
        derived_params={
            param_idx: snapshot[param_idx]
            for param_idx, _name in MONITORED_DERIVED_ZERO_PARAMS
        },
        real_pres_pos_high=int(value_high.value),
        real_pres_pos_low=int(value_low.value),
    )


def _restore_protected_params(
    handle: MU_Handle,
    protected_state: ProtectedZeroState,
    label: str,
) -> bool:
    for param in protected_state.params.values():
        ret = mu.MU_SetParam(
            handle,
            c_uint32(param.index),
            c_uint32(param.high),
            c_uint32(param.low),
            MU_VERIFY,
        )
        _log_mu(f"Restore protected {param.name}: {label}", ret, handle)
        if ret != MU_OK:
            return False
    return True


def _verify_protected_params(
    handle: MU_Handle,
    protected_state: ProtectedZeroState,
    label: str,
    *,
    refresh_from_ram: bool,
) -> bool:
    if refresh_from_ram:
        ret = mu.MU_ReadParams(handle)
        _log_mu(f"ReadParams for protected verify: {label}", ret, handle)
        if ret != MU_OK:
            return False

    actual = _capture_protected_params(handle, label)
    if actual is None:
        return False

    changed = []
    for param_idx, expected in protected_state.params.items():
        observed = actual.params.get(param_idx)
        if observed != expected:
            changed.append((expected, observed))

    if changed:
        print(f"[ERROR] Protected MU params changed during {label}:")
        for expected, observed in changed:
            print(f"[ERROR] expected {_format_protected_param(expected)}")
            if observed is None:
                print("[ERROR] observed <missing>")
            else:
                print(f"[ERROR] observed {_format_protected_param(observed)}")
        return False

    if (
        actual.real_pres_pos_high != protected_state.real_pres_pos_high
        or actual.real_pres_pos_low != protected_state.real_pres_pos_low
    ):
        print(
            f"[ERROR] REAL_PRES_POS changed during {label}: "
            f"expected=(0x{protected_state.real_pres_pos_high:08X}, "
            f"0x{protected_state.real_pres_pos_low:08X}) "
            f"observed=(0x{actual.real_pres_pos_high:08X}, "
            f"0x{actual.real_pres_pos_low:08X})"
        )
        return False

    print(f"[STATE] Protected MU params preserved during {label}.")
    return True


def _write_params_preserving(
    handle: MU_Handle,
    protected_state: ProtectedZeroState,
    label: str,
) -> int:
    if not _restore_protected_params(handle, protected_state, label):
        return 1

    ret = write_params_with_verify(handle)
    if ret != MU_OK:
        return ret

    if not _verify_protected_params(
        handle,
        protected_state,
        f"{label} RAM write",
        refresh_from_ram=True,
    ):
        return 1
    return MU_OK


def _save_original_config_backup(handle: MU_Handle, export_dir: Path) -> bool:
    backup_path = export_dir / (
        "original_config_before_calibration_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.cfg"
    )
    return _save_mu_config(handle, backup_path)


def _enter_biss(handle) -> bool:
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


def write_params_with_verify(handle: MU_Handle) -> int:
    valid_flags = (c_bool * 128)()
    ret = mu.MU_WriteParams(handle, False, valid_flags)
    _log_mu("Write RAM (verify)", ret, handle)
    return int(ret)


def _u32_value(value) -> int:
    return int(value.value if hasattr(value, "value") else value)


def _combined_param_value(param: ProtectedMuParam) -> int:
    return ((int(param.high) << 32) | int(param.low)) & ((1 << 64) - 1)


def _split_param_value(value: int) -> tuple[int, int]:
    return (int(value) >> 32) & 0xFFFFFFFF, int(value) & 0xFFFFFFFF


def _signed_mod_delta(target: int, current: int, bits: int) -> int:
    modulus = 1 << bits
    mask = modulus - 1
    delta = (int(target) - int(current)) & mask
    if delta >= (modulus >> 1):
        delta -= modulus
    return delta


def _infer_offset_bits(*values: int) -> int:
    max_value = max(int(value) for value in values)
    for bits in (12, 16, 20, 24, 28, 32, 36):
        if max_value < (1 << bits):
            return bits
    return 36


def _set_combined_param(
    handle: MU_Handle,
    param_idx: int,
    name: str,
    value: int,
    label: str,
) -> bool:
    high, low = _split_param_value(value)
    ret = mu.MU_SetParam(
        handle,
        c_uint32(param_idx),
        c_uint32(high),
        c_uint32(low),
        MU_VERIFY,
    )
    _log_mu(f"Set compensated {name}: {label}", ret, handle)
    return ret == MU_OK


def _param_values_equal_modulo(expected: ProtectedMuParam, observed: ProtectedMuParam) -> bool:
    expected_value = _combined_param_value(expected)
    observed_value = _combined_param_value(observed)
    bits = _infer_offset_bits(expected_value, observed_value)
    mask = (1 << bits) - 1
    return (expected_value & mask) == (observed_value & mask)


def _read_master_period_count(handle: MU_Handle) -> int | None:
    param = _read_param(handle, MU_MPC.value, "MPC")
    if param is None:
        return None
    mpc_code = int(param.low) & 0xF
    if mpc_code >= 31:
        print(f"[ERROR] Unsupported MPC value for zero compensation: {mpc_code}")
        return None
    master_period_count = 1 << mpc_code
    print(
        "[STATE] Encoder-side zero compensation scale: "
        f"MPC=0x{mpc_code:X} master_period_count={master_period_count}"
    )
    return master_period_count


def _compensate_zero_shift_from_derived_offsets(
    handle: MU_Handle,
    baseline_state: ProtectedZeroState,
    label: str,
    attempt: int = 1,
) -> ProtectedZeroState | None:
    ret = mu.MU_ReadParams(handle)
    _log_mu(
        f"ReadParams before encoder-side zero compensation attempt {attempt}: {label}",
        ret,
        handle,
    )
    if ret != MU_OK:
        return None

    current_state = _capture_protected_params(
        handle,
        f"{label} measured derived offsets attempt {attempt}",
    )
    if current_state is None:
        return None

    master_period_count = _read_master_period_count(handle)
    if master_period_count is None:
        return None

    compensation_pairs = (
        (MU_OFF_ABZ.value, "OFF_ABZ", MU_OFF_POS.value, "OFF_POS"),
        (MU_OFF_UVW.value, "OFF_UVW", MU_OFF_COM.value, "OFF_COM"),
    )
    changed = False
    compensated_params = dict(current_state.params)

    for persistent_idx, persistent_name, derived_idx, derived_name in compensation_pairs:
        baseline_derived = baseline_state.derived_params.get(derived_idx)
        current_derived = current_state.derived_params.get(derived_idx)
        current_persistent = current_state.params.get(persistent_idx)
        if (
            baseline_derived is None
            or current_derived is None
            or current_persistent is None
        ):
            print(
                "[ERROR] Cannot compensate zero shift because required "
                f"{persistent_name}/{derived_name} state is missing."
            )
            return None

        baseline_value = _combined_param_value(baseline_derived)
        current_value = _combined_param_value(current_derived)
        persistent_value = _combined_param_value(current_persistent)
        bits = _infer_offset_bits(baseline_value, current_value)
        delta = _signed_mod_delta(baseline_value, current_value, bits)
        print(
            "[STATE] Encoder-side zero compensation: "
            f"{derived_name}_before=0x{baseline_value:X} "
            f"{derived_name}_after=0x{current_value:X} "
            f"bits={bits} delta={delta:+d}"
        )
        if delta == 0:
            continue

        persistent_delta = delta
        if persistent_idx == MU_OFF_ABZ.value and derived_idx == MU_OFF_POS.value:
            persistent_delta = delta * MU_OFF_ABZ_UNITS_PER_OFF_POS_TICK
            print(
                "[STATE] Encoder-side zero compensation scaled delta: "
                f"{persistent_name}_delta={persistent_delta:+d} "
                f"({derived_name}_delta {delta:+d} * "
                f"{MU_OFF_ABZ_UNITS_PER_OFF_POS_TICK}; "
                f"MPC master periods={master_period_count})"
            )

        persistent_bits = 36 if persistent_idx in {MU_OFF_ABZ.value, MU_OFF_UVW.value} else bits
        modulus = 1 << persistent_bits
        compensated_value = (persistent_value + persistent_delta) & (modulus - 1)
        if not _set_combined_param(
            handle,
            persistent_idx,
            persistent_name,
            compensated_value,
            label,
        ):
            return None
        high, low = _split_param_value(compensated_value)
        compensated_params[persistent_idx] = ProtectedMuParam(
            index=persistent_idx,
            name=persistent_name,
            high=high,
            low=low,
        )
        changed = True

    if not changed:
        print("[INFO] Encoder-side zero compensation not needed; derived offsets did not move.")
        return baseline_state

    ret = write_params_with_verify(handle)
    if ret != MU_OK:
        return None

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_WRITE_OFF)
    _log_mu("WRITE_OFF compensated zero offsets", ret, handle)
    if ret != MU_OK:
        return None

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_CRC_CALC)
    _log_mu("CRC_CALC after encoder-side zero compensation", ret, handle)
    if ret != MU_OK:
        return None

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_ABS_RESET)
    _log_mu("ABS_RESET after encoder-side zero compensation", ret, handle)
    if ret != MU_OK:
        return None

    ret = mu.MU_ReadParams(handle)
    _log_mu(f"ReadParams after encoder-side zero compensation: {label}", ret, handle)
    if ret != MU_OK:
        return None

    verified_state = _capture_protected_params(handle, f"{label} compensated verify")
    if verified_state is None:
        return None

    mismatches = []
    for derived_idx, expected in baseline_state.derived_params.items():
        observed = verified_state.derived_params.get(derived_idx)
        if observed is None or not _param_values_equal_modulo(expected, observed):
            mismatches.append((expected, observed))

    if mismatches:
        print("[ERROR] Encoder-side zero compensation did not restore derived offsets:")
        for expected, observed in mismatches:
            print(f"[ERROR] expected {_format_protected_param(expected)}")
            if observed is None:
                print("[ERROR] observed <missing>")
            else:
                print(f"[ERROR] observed {_format_protected_param(observed)}")
        if attempt < ZERO_COMPENSATION_MAX_ATTEMPTS:
            print(
                "[WARN] Encoder-side zero compensation has residual error; "
                f"retrying from measured encoder state ({attempt + 1}/"
                f"{ZERO_COMPENSATION_MAX_ATTEMPTS})."
            )
            return _compensate_zero_shift_from_derived_offsets(
                handle,
                baseline_state,
                label,
                attempt + 1,
            )
        return None

    print("[STATE] Encoder-side zero compensation restored derived offsets.")
    return ProtectedZeroState(
        params=compensated_params,
        derived_params=baseline_state.derived_params,
        real_pres_pos_high=baseline_state.real_pres_pos_high,
        real_pres_pos_low=baseline_state.real_pres_pos_low,
    )


def _store_to_eeprom_and_set_mode(
    handle: MU_Handle,
    final_mode: c_uint32,
    protected_state: ProtectedZeroState | None = None,
) -> bool:
    current_zero_state = protected_state
    if current_zero_state is not None and not _verify_protected_params(
        handle,
        current_zero_state,
        "before EEPROM store",
        refresh_from_ram=False,
    ):
        print("[WARN] Protected MU params drifted before EEPROM store; restoring once.")
        if not _restore_protected_params(handle, current_zero_state, "before EEPROM store"):
            return False
        if write_params_with_verify(handle) != MU_OK:
            return False
        if not _verify_protected_params(
            handle,
            current_zero_state,
            "before EEPROM store restored RAM",
            refresh_from_ram=True,
        ):
            return False

    # Match the iC-Haus calibration examples: after the final calibration RAM
    # write, recalculate CRC and rebuild OFF_POS/OFF_COM from OFF_ABZ/OFF_UVW
    # using the calibrated nonius/multiturn state before storing EEPROM.
    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_CRC_CALC)
    _log_mu("CRC_CALC after final calibration", ret, handle)
    if ret != MU_OK:
        return False

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_ABS_RESET)
    _log_mu("ABS_RESET after final calibration", ret, handle)
    if ret != MU_OK:
        return False

    if current_zero_state is not None:
        current_zero_state = _compensate_zero_shift_from_derived_offsets(
            handle,
            current_zero_state,
            "after calibrated ABS_RESET before EEPROM store",
        )
        if current_zero_state is None:
            return False

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_WRITE_ALL)
    _log_mu("WRITE_ALL calibrated config after ABS_RESET", ret, handle)
    if ret != MU_OK:
        return False

    # Switch the live mode without verification, then store once more.
    # Verifying after SSI is active causes MU_READPARAM_SSI.
    ret = mu.MU_SetParam(handle, MU_MODEA, 0, final_mode, MU_WRITE)
    if ret != MU_OK:
        print(
            "[ERROR] Set current MODEA final (no verify) failed after EEPROM save; "
            f"{_mu_last_error(handle)}"
        )
        return False
    else:
        _log_mu("Set current MODEA final (no verify)", ret, handle)

    ret = mu.MU_WriteCmdRegister(handle, MU_CMD_WRITE_ALL)
    _log_mu("WRITE_ALL calibrated config in SSI", ret, handle)
    if ret != MU_OK:
        return False

    return True


def _open_session(handle: MU_Handle, serial_last4: str) -> bool:
    # IMPORTANT: empty-string is allowed; do NOT pass None by default (per your failing log)
    serial_arg = serial_last4.encode("ascii") if serial_last4 else b""

    _log_mu("Open", mu.MU_Open(byref(handle)), handle)

    ret = mu.MU_SetInterface(handle, MU_MB5U.value, serial_arg)
    _log_mu("Set Interface", ret, handle)
    if ret != MU_OK and not serial_last4:
        # fallback try NULL (some driver stacks accept it)
        ret2 = mu.MU_SetInterface(handle, MU_MB5U.value, None)
        _log_mu("Set Interface (NULL fallback)", ret2, handle)
        if ret2 != MU_OK:
            return False

    _log_mu(f"Use revision 0x{MU_FORCED_REV:02X}", mu.MU_UseRevision(handle, MU_FORCED_REV), handle)

    if not _enter_biss(handle):
        print("[ERROR] Unable to enter BiSS mode during init.")
        return False

    _log_mu("Initialize", mu.MU_Initialize(handle), handle)
    return True


def _close_session(handle: MU_Handle) -> None:
    _log_mu("Close", mu.MU_Close(handle), handle)


def _save_mu_config(handle: MU_Handle, config_path: Path | None) -> bool:
    if not config_path:
        return True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    ret = mu.MU_SaveParams(handle, str(config_path).encode("utf-8"))
    _log_mu(f"Save MU config -> {config_path}", ret, handle)
    return ret == MU_OK


def _get_analyze_result_log(analyze: c_void_p) -> str:
    size = int(
        mu.MU_Calibration_getAnalyzeResultLog(
            analyze,
            None,
            0,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL,
        )
    )
    if size <= 0:
        return ""

    buf = ctypes.create_string_buffer(size + 1)
    mu.MU_Calibration_getAnalyzeResultLog(
        analyze,
        buf,
        len(buf),
        MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL,
    )
    return buf.value.decode(errors="ignore").strip()


def _get_relative_adjustments(analyze: c_void_p):
    rel_m = MU_Calibration_RelativeAnalogTrackAdjustments()
    rel_n = MU_Calibration_RelativeAnalogTrackAdjustments()
    mu.MU_Calibration_getRelativeMasterTrackAdjustments(analyze, byref(rel_m))
    mu.MU_Calibration_getRelativeNoniusTrackAdjustments(analyze, byref(rel_n))

    master = (
        float(rel_m.cosineGain_lsb),
        float(rel_m.sineOffset_lsb),
        float(rel_m.cosineOffset_lsb),
        float(rel_m.phase_lsb),
    )
    nonius = (
        float(rel_n.cosineGain_lsb),
        float(rel_n.sineOffset_lsb),
        float(rel_n.cosineOffset_lsb),
        float(rel_n.phase_lsb),
    )
    return master, nonius


def _residuals_are_close(lhs, rhs, tol: float = 1e-4) -> bool:
    if lhs is None or rhs is None:
        return False
    return all(abs(a - b) <= tol for a, b in zip(lhs, rhs))


def _get_adjustment_message(calibration: c_void_p, analyze: c_void_p):
    buf = ctypes.create_string_buffer(2048)
    adjustable = bool(
        mu.MU_Calibration_isAnalogAnalyzeResultAdjustable(
            calibration,
            analyze,
            buf,
            len(buf),
            MU_ADJUSTMENT_MESSAGE_LOG_ALL,
        )
    )
    return adjustable, buf.value.decode(errors="ignore").strip()


def _set_initial_analog_track_adjustments(
    calibration: c_void_p,
    *,
    nonius_phase: int = 0,
    nonius_phase_range: int = 0,
) -> bool:
    if not hasattr(mu, "MU_Calibration_setCurrentAnalogTrackAdjustments"):
        print("[ERROR] MU_Calibration_setCurrentAnalogTrackAdjustments is not available.")
        return False

    zero_master = MU_Calibration_AnalogTrackAdjustments()
    zero_nonius = MU_Calibration_AnalogTrackAdjustments()
    zero_nonius.phase = c_uint8(nonius_phase).value
    zero_nonius.phaseRange = c_uint8(nonius_phase_range).value
    return bool(
        mu.MU_Calibration_setCurrentAnalogTrackAdjustments(
            calibration,
            byref(zero_master),
            byref(zero_nonius),
        )
    )


def _analog_initial_seed_for_attempt(attempt_idx: int) -> tuple[str, int, int]:
    return "zero analog", 0, 0


def _resolve_acquisition_timing(
    frame_cycle_time_s: float,
    clock_frequency_hz: float,
) -> AcquisitionTiming:
    actual_frame_cycle_time_s = float(frame_cycle_time_s)
    actual_clock_frequency_hz = float(clock_frequency_hz)

    if hasattr(mu, "MU_Interface_nearestPossibleFrameCycleTime"):
        nearest_frame_cycle_time = float(
            mu.MU_Interface_nearestPossibleFrameCycleTime(
                MU_MB5U.value,
                frame_cycle_time_s,
            )
        )
        if nearest_frame_cycle_time > 0.0:
            actual_frame_cycle_time_s = nearest_frame_cycle_time

    if hasattr(mu, "MU_Interface_nearestPossibleClockFreq"):
        nearest_clock_frequency = float(
            mu.MU_Interface_nearestPossibleClockFreq(
                MU_MB5U.value,
                clock_frequency_hz,
            )
        )
        if nearest_clock_frequency > 0.0:
            actual_clock_frequency_hz = nearest_clock_frequency

    return AcquisitionTiming(
        requested_frame_cycle_time_s=float(frame_cycle_time_s),
        actual_frame_cycle_time_s=actual_frame_cycle_time_s,
        requested_clock_frequency_hz=float(clock_frequency_hz),
        actual_clock_frequency_hz=actual_clock_frequency_hz,
    )


def _acquire_raw_data(
    handle: MU_Handle,
    n_samples: int,
    frame_cycle_time_s: float,
    clock_frequency_hz: float,
):
    timing = _resolve_acquisition_timing(frame_cycle_time_s, clock_frequency_hz)
    master_arr = (c_uint16 * n_samples)()
    nonius_arr = (c_uint16 * n_samples)()

    calibration_config_active = False
    try:
        ret = mu.MU_activateCalibrationConfig(handle)
        _log_mu("activateCalibrationConfig", ret, handle)
        if ret != MU_OK:
            return None, None, timing, int(ret)
        calibration_config_active = True

        rc = int(
            mu.MU_acquireRawData(
                handle,
                ctypes.cast(master_arr, POINTER(c_uint16)),
                ctypes.cast(nonius_arr, POINTER(c_uint16)),
                c_size_t(n_samples),
                c_uint32(0),
                c_double(timing.actual_frame_cycle_time_s),
                c_double(timing.actual_clock_frequency_hz),
            )
        )
        return master_arr, nonius_arr, timing, rc
    finally:
        if calibration_config_active:
            _log_mu(
                "deactivateCalibrationConfig",
                mu.MU_deactivateCalibrationConfig(handle),
                handle,
            )


def _append_analog_history(
    history: list[AnalogResidualRun],
    label: str,
    analog_valid: bool,
    master_residuals,
    nonius_residuals,
) -> None:
    history.append(
        AnalogResidualRun(
            label=label,
            analog_valid=bool(analog_valid),
            master_residuals=ResidualVector.from_values(master_residuals),
            nonius_residuals=ResidualVector.from_values(nonius_residuals),
        )
    )


def _collect_quality_metrics(
    analyze: c_void_p,
    analog_residual_history: list[AnalogResidualRun],
    acquisition_timing: AcquisitionTiming,
) -> CalibrationMetrics:
    master_residuals, nonius_residuals = _get_relative_adjustments(analyze)
    max_abs_analog_residual = max(
        abs(value) for value in (*master_residuals, *nonius_residuals)
    )

    phase_range_limit = int(mu.MU_Calibration_noniusPhaseRangeLimit(analyze))
    phase_margin_max = int(mu.MU_Calibration_noniusPhaseMarginMax(analyze))
    phase_margin_min = int(mu.MU_Calibration_noniusPhaseMarginMin(analyze))

    curve_samples = int(mu.MU_Calibration_numberOfNoniusCurveSamples(analyze))
    phase_error_ptr = mu.MU_Calibration_noniusPhaseError(analyze)
    max_abs_phase_error = 0
    if phase_error_ptr and curve_samples > 0:
        max_abs_phase_error = max(abs(int(phase_error_ptr[i])) for i in range(curve_samples))

    max_abs_phase_margin = max(abs(phase_margin_max), abs(phase_margin_min))
    max_abs_phase_margin_pct = (
        max_abs_phase_margin / abs(phase_range_limit) * 100.0
        if phase_range_limit
        else 0.0
    )

    return CalibrationMetrics(
        analog_valid=bool(mu.MU_Calibration_isAnalogAnalysesValid(analyze)),
        nonius_valid=bool(mu.MU_Calibration_isNoniusAnalysesValid(analyze)),
        master_residuals=ResidualVector.from_values(master_residuals),
        nonius_residuals=ResidualVector.from_values(nonius_residuals),
        max_abs_analog_residual_lsb=max_abs_analog_residual,
        phase_range_limit_lsb=phase_range_limit,
        phase_margin_max_lsb=phase_margin_max,
        phase_margin_min_lsb=phase_margin_min,
        max_abs_phase_margin_pct_of_range_limit=max_abs_phase_margin_pct,
        upper_phase_margin_pct=float(mu.MU_Calibration_noniusUpperPhaseMargin(analyze)),
        lower_phase_margin_pct=float(mu.MU_Calibration_noniusLowerPhaseMargin(analyze)),
        max_abs_phase_error_lsb=max_abs_phase_error,
        analyze_log=_get_analyze_result_log(analyze),
        analog_residual_history=tuple(analog_residual_history),
        acquisition_timing=acquisition_timing,
    )


def _write_quality_report(export_dir: Path, attempt_idx: int, metrics: CalibrationMetrics, evaluation) -> Path:
    report_path = export_dir / f"calibration_report_attempt_{attempt_idx:02d}.txt"
    report_path.write_text(
        build_quality_report(attempt_idx, metrics, evaluation),
        encoding="utf-8",
    )
    return report_path


def _select_encoder(mic: MicontrolF35_CAN, enc_idx: int) -> None:
    # YOUR convention:
    #   enc 0 -> digital output True
    #   enc 1 -> digital output False
    if enc_idx == 0:
        mic.set_digital_output(True)
    else:
        mic.set_digital_output(False)
    time.sleep(0.2)


# =====================================================================================
# 1) CALIBRATION ONLY (no preset / no zeroing here)
# =====================================================================================
def calibrate_one_encoder(
    export_dir: Path,
    serial_last4: str,
    saved_config_path: Path | None = None,
    n_samples: int = 64000,
    frame_cycle_time_s: float = 187.5e-6,
    clock_frequency_hz: float = 2.0e6,
    max_analog_runs: int = 3,
    residual_limit_lsb: float = 1.0,
    final_residual_cap_lsb: float = 20.0,
    max_calibration_attempts: int = 2,
    max_phase_margin_pct: float = 50.0,
) -> bool:
    export_dir.mkdir(parents=True, exist_ok=True)

    handle = MU_Handle()
    if not _open_session(handle, serial_last4):
        _close_session(handle)
        return False

    calibration = None
    analyze = None
    try:
        # Sync back
        ret = mu.MU_ReadParams(handle)
        _log_mu("ReadParams", ret, handle)
        if ret != MU_OK:
            return False

        protected_params = _capture_protected_params(
            handle,
            "original live encoder state before calibration",
        )
        if protected_params is None:
            print("[ERROR] Could not capture protected MU params; aborting calibration.")
            return False
        if not _save_original_config_backup(handle, export_dir):
            print("[ERROR] Could not save original MU config backup; aborting calibration.")
            return False

        for attempt_idx in range(1, max_calibration_attempts + 1):
            calibration = mu.MU_getCalibration(handle)
            if not calibration:
                print("[ERROR] MU_getCalibration returned NULL")
                return False
            if analyze:
                mu.MU_CalibrationAnalyzeResult_delete(analyze)
                analyze = None

            print(f"\n[INFO] Calibration attempt {attempt_idx}/{max_calibration_attempts}")
            seed_label, seed_nonius_phase, seed_nonius_phase_range = (
                _analog_initial_seed_for_attempt(attempt_idx)
            )
            print(f"[INFO] Initial analog seed: {seed_label}")
            if not _set_initial_analog_track_adjustments(
                calibration,
                nonius_phase=seed_nonius_phase,
                nonius_phase_range=seed_nonius_phase_range,
            ):
                print("[ERROR] Could not set initial analog adjustments.")
                try:
                    mu.MU_Calibration_delete(calibration)
                except Exception:
                    pass
                calibration = None
                continue

            ret = mu.MU_setCalibration(handle, calibration)
            _log_mu("setCalibration(initial analog)", ret, handle)
            if ret != MU_OK or _write_params_preserving(
                handle,
                protected_params,
                "initial analog calibration",
            ) != MU_OK:
                try:
                    mu.MU_Calibration_delete(calibration)
                except Exception:
                    pass
                calibration = None
                continue

            analog_residuals_ok = False
            attempt_aborted = False
            previous_master_residuals = None
            previous_nonius_residuals = None
            analog_residual_history: list[AnalogResidualRun] = []
            master_arr = None
            nonius_arr = None
            acquisition_timing = None

            for run_idx in range(max_analog_runs):
                if analyze:
                    mu.MU_CalibrationAnalyzeResult_delete(analyze)
                    analyze = None

                master_arr, nonius_arr, acquisition_timing, rc = _acquire_raw_data(
                    handle,
                    n_samples=n_samples,
                    frame_cycle_time_s=frame_cycle_time_s,
                    clock_frequency_hz=clock_frequency_hz,
                )
                if rc != 0:
                    print(
                        f"[ERROR] Raw data acquisition/config failed rc={rc} "
                        f"({_mu_last_error(handle)})"
                    )
                    attempt_aborted = True
                    break
                if master_arr is None or nonius_arr is None or acquisition_timing is None:
                    print("[ERROR] Raw data acquisition did not return buffers.")
                    attempt_aborted = True
                    break

                print(
                    "[INFO] Acquisition timing "
                    f"requested_frame={acquisition_timing.requested_frame_cycle_time_s:.9f}s "
                    f"actual_frame={acquisition_timing.actual_frame_cycle_time_s:.9f}s "
                    f"requested_clock={acquisition_timing.requested_clock_frequency_hz:.1f}Hz "
                    f"actual_clock={acquisition_timing.actual_clock_frequency_hz:.1f}Hz"
                )

                run_suffix = "" if run_idx == 0 else f"_run_{run_idx + 1:02d}"
                csv_path = export_dir / (
                    f"calibration_data_raw_attempt_{attempt_idx:02d}{run_suffix}.csv"
                )
                with csv_path.open("w", encoding="utf-8") as f:
                    f.write("master,nonius\n")
                    for i in range(n_samples):
                        f.write(f"{int(master_arr[i])},{int(nonius_arr[i])}\n")
                print(f"[INFO] wrote {csv_path}")

                analyze = mu.MU_Calibration_analyzeRawData(
                    calibration,
                    ctypes.cast(master_arr, POINTER(c_uint16)),
                    ctypes.cast(nonius_arr, POINTER(c_uint16)),
                    c_size_t(n_samples),
                )
                if not analyze:
                    print("[ERROR] analyzeRawData returned NULL (raw data not analyzable).")
                    attempt_aborted = True
                    break

                master_residuals, nonius_residuals = _get_relative_adjustments(analyze)
                residuals_stagnated = (
                    _residuals_are_close(previous_master_residuals, master_residuals)
                    and _residuals_are_close(previous_nonius_residuals, nonius_residuals)
                )

                def _ok(x: float) -> bool:
                    return abs(x) <= residual_limit_lsb

                analog_residuals_ok = all(_ok(v) for v in master_residuals) and all(
                    _ok(v) for v in nonius_residuals
                )

                analog_analysis_valid = bool(mu.MU_Calibration_isAnalogAnalysesValid(analyze))
                _append_analog_history(
                    analog_residual_history,
                    label=f"analog_run_{run_idx + 1:02d}",
                    analog_valid=analog_analysis_valid,
                    master_residuals=master_residuals,
                    nonius_residuals=nonius_residuals,
                )

                print(f"\n[INFO] Analog run {run_idx + 1}/{max_analog_runs} residuals (LSB):")
                print(
                    f"  Master: cosGain={master_residuals[0]:+.4f} "
                    f"sinOff={master_residuals[1]:+.4f} "
                    f"cosOff={master_residuals[2]:+.4f} "
                    f"phase={master_residuals[3]:+.4f}"
                )
                print(
                    f"  Nonius: cosGain={nonius_residuals[0]:+.4f} "
                    f"sinOff={nonius_residuals[1]:+.4f} "
                    f"cosOff={nonius_residuals[2]:+.4f} "
                    f"phase={nonius_residuals[3]:+.4f}"
                )

                if not analog_analysis_valid:
                    print("[WARN] Analog analysis is not valid.")
                    analyze_log = _get_analyze_result_log(analyze)
                    if analyze_log:
                        print(analyze_log)

                if analog_residuals_ok:
                    print(f"[INFO] Residuals <= {residual_limit_lsb:.3f} LSB -> stop analog loop")
                    break

                if residuals_stagnated:
                    print(
                        "[WARN] Analog residuals did not change after the previous adjustment. "
                        "This attempt will be treated as bad acquisition data."
                    )
                    attempt_aborted = True
                    break

                adjustable, adjustment_message = _get_adjustment_message(calibration, analyze)
                if not adjustable:
                    print(
                        "[WARN] Analog analyze result reports limited adjustability. "
                        "Trying the SDK analog adjustment directly."
                    )
                    if adjustment_message:
                        print(adjustment_message)

                if not bool(mu.MU_Calibration_adjustAnalogByAnalyzeResult(calibration, analyze)):
                    print("[ERROR] MU_Calibration_adjustAnalogByAnalyzeResult returned False.")
                    if adjustment_message:
                        print(adjustment_message)
                    attempt_aborted = True
                    break

                ret = mu.MU_setCalibration(handle, calibration)
                _log_mu("setCalibration(analog adjustment)", ret, handle)
                if ret != MU_OK:
                    attempt_aborted = True
                    break
                if _write_params_preserving(
                    handle,
                    protected_params,
                    f"analog adjustment run {run_idx + 1}",
                ) != MU_OK:
                    attempt_aborted = True
                    break

                previous_master_residuals = master_residuals
                previous_nonius_residuals = nonius_residuals

            if attempt_aborted:
                try:
                    mu.MU_Calibration_delete(calibration)
                except Exception:
                    pass
                calibration = None
                continue

            if not analog_residuals_ok:
                print(
                    f"[WARN] Analog residuals are still above {residual_limit_lsb:.3f} LSB "
                    f"after {max_analog_runs} runs. Verifying the last adjustment."
                )
                if analyze:
                    mu.MU_CalibrationAnalyzeResult_delete(analyze)
                    analyze = None
                master_arr, nonius_arr, acquisition_timing, rc = _acquire_raw_data(
                    handle,
                    n_samples=n_samples,
                    frame_cycle_time_s=frame_cycle_time_s,
                    clock_frequency_hz=clock_frequency_hz,
                )
                if rc != 0:
                    print(
                        f"[ERROR] Final raw data acquisition/config failed rc={rc} "
                        f"({_mu_last_error(handle)})"
                    )
                    try:
                        mu.MU_Calibration_delete(calibration)
                    except Exception:
                        pass
                    calibration = None
                    continue
                if master_arr is None or nonius_arr is None or acquisition_timing is None:
                    print("[ERROR] Final raw data acquisition did not return buffers.")
                    try:
                        mu.MU_Calibration_delete(calibration)
                    except Exception:
                        pass
                    calibration = None
                    continue

                csv_path = export_dir / f"calibration_data_raw_attempt_{attempt_idx:02d}_final.csv"
                with csv_path.open("w", encoding="utf-8") as f:
                    f.write("master,nonius\n")
                    for i in range(n_samples):
                        f.write(f"{int(master_arr[i])},{int(nonius_arr[i])}\n")
                print(f"[INFO] wrote {csv_path}")

                analyze = mu.MU_Calibration_analyzeRawData(
                    calibration,
                    ctypes.cast(master_arr, POINTER(c_uint16)),
                    ctypes.cast(nonius_arr, POINTER(c_uint16)),
                    c_size_t(n_samples),
                )
                if not analyze:
                    print("[ERROR] Re-analyze after analog adjustment returned NULL.")
                    try:
                        mu.MU_Calibration_delete(calibration)
                    except Exception:
                        pass
                    calibration = None
                    continue

                final_master_residuals, final_nonius_residuals = _get_relative_adjustments(analyze)
                _append_analog_history(
                    analog_residual_history,
                    label="analog_post_adjust_final",
                    analog_valid=bool(mu.MU_Calibration_isAnalogAnalysesValid(analyze)),
                    master_residuals=final_master_residuals,
                    nonius_residuals=final_nonius_residuals,
                )

            spo_tbl = MU_Calibration_NoniusTrackOffsetTable()
            mu.MU_Calibration_getOptimizedNoniusTrackOffsetTable(analyze, byref(spo_tbl))
            if not bool(mu.MU_Calibration_setCurrentNoniusTrackOffsetTable(calibration, byref(spo_tbl))):
                print("[ERROR] MU_Calibration_setCurrentNoniusTrackOffsetTable returned False.")
                try:
                    mu.MU_Calibration_delete(calibration)
                except Exception:
                    pass
                continue

            if analyze:
                mu.MU_CalibrationAnalyzeResult_delete(analyze)
                analyze = None

            analyze = mu.MU_Calibration_analyzeRawData(
                calibration,
                ctypes.cast(master_arr, POINTER(c_uint16)),
                ctypes.cast(nonius_arr, POINTER(c_uint16)),
                c_size_t(n_samples),
            )
            if not analyze:
                print("[ERROR] Final analyzeRawData returned NULL after nonius optimization.")
                try:
                    mu.MU_Calibration_delete(calibration)
                except Exception:
                    pass
                calibration = None
                continue

            metrics = _collect_quality_metrics(
                analyze,
                analog_residual_history=analog_residual_history,
                acquisition_timing=acquisition_timing,
            )
            evaluation = evaluate_quality(
                metrics,
                final_residual_cap_lsb=final_residual_cap_lsb,
                max_phase_margin_pct=max_phase_margin_pct,
            )
            report_path = _write_quality_report(export_dir, attempt_idx, metrics, evaluation)

            print("[INFO] Final calibration quality:")
            print(f"  quality_status={'PASS' if evaluation.ok else 'FAIL'}")
            print(
                f"  analog_valid={metrics.analog_valid} "
                f"nonius_valid={metrics.nonius_valid}"
            )
            print(
                f"  max_abs_analog_residual={metrics.max_abs_analog_residual_lsb:.4f} LSB "
                f"(final cap {final_residual_cap_lsb:.4f})"
            )
            print(
                f"  nonius_phase_margin="
                f"{metrics.max_abs_phase_margin_pct_of_range_limit:.2f}% "
                f"of range limit (max {max_phase_margin_pct:.2f}%)"
            )
            print(
                f"  upper_phase_clearance={metrics.upper_phase_margin_pct:.2f}% "
                f"lower_phase_clearance={metrics.lower_phase_margin_pct:.2f}%"
            )
            print(
                f"  max_abs_phase_error={metrics.max_abs_phase_error_lsb} LSB, "
                f"phase_range_limit={metrics.phase_range_limit_lsb} LSB"
            )
            print(f"  quality_gate_reason={evaluation.reason}")
            if metrics.analyze_log:
                print("[INFO] Analyze result log:")
                print(metrics.analyze_log)
            print(f"[INFO] wrote {report_path}")

            if evaluation.ok:
                ret = mu.MU_setCalibration(handle, calibration)
                _log_mu("setCalibration(final)", ret, handle)
                if ret != MU_OK:
                    return False
                if _write_params_preserving(
                    handle,
                    protected_params,
                    "final calibration",
                ) != MU_OK:
                    return False
                if not _save_mu_config(handle, saved_config_path):
                    return False
                if not _store_to_eeprom_and_set_mode(handle, MU_SSI, protected_params):
                    return False
                return True

            print(
                f"[WARN] Calibration quality is too poor on attempt {attempt_idx}. "
                "Retrying with a new acquisition."
            )
            try:
                mu.MU_Calibration_delete(calibration)
            except Exception:
                pass
            calibration = None

        print(
            f"[ERROR] Calibration failed after {max_calibration_attempts} attempts. "
            "The report files contain the final MU error metrics."
        )
        return False

    finally:
        try:
            if analyze:
                mu.MU_CalibrationAnalyzeResult_delete(analyze)
        except Exception:
            pass
        try:
            if calibration:
                mu.MU_Calibration_delete(calibration)
        except Exception:
            pass
        _close_session(handle)


# =====================================================================================
# CAN controller restart
# =====================================================================================
def restart_controller(can: DriverCan, mic: MicontrolF35_CAN, node: int, can_bitrate: int):
    power_cycled = power_cycle_owon_spe6053(off_seconds=3.0, voltage_v=24.0, current_a=5.0)
    if not power_cycled and mic and mic.added_node:
        try:
            nmt_reset_node_compat(mic.added_node.nmt)
        except Exception as exc:
            print(f"[WARN] Failed to request controller reset: {exc}")
    try:
        can.close_can()
    except Exception as exc:
        print(f"[WARN] Failed to close CAN before restart: {exc}")
    if not power_cycled:
        time.sleep(3.0)

    new_can = DriverCan(can_bitrate=can_bitrate)
    new_mic = MicontrolF35_CAN(can=new_can.can_network, node=node)
    if not new_mic.added_node:
        print("[ERROR] Could not add CAN node after restart.")
        return None, None
    new_mic.clear_errors()
    return new_can, new_mic


def return_controller_to_existing_zero(
    mic: MicontrolF35_CAN,
    rpm: int = ZERO_RETURN_RPM,
) -> None:
    """Move to the already stored controller zero without writing a new zero."""
    mic.clear_errors()
    mic.clear_errors()
    if hasattr(mic, "SSI_encoder"):
        if mic.SSI_encoder(True):
            print("[INFO] SSI encoder enabled before returning to stored zero.")
        else:
            print("[WARN] SSI encoder enable did not report success before zero return.")

    start_pos = mic.get_steering_pos()
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
        "[INFO] Controller state before return to stored zero: "
        f"status={status} direct_position={direct_pos} steering_position={start_pos}"
    )

    if start_pos is not None and abs(int(start_pos)) <= ZERO_POSITION_TOLERANCE_COUNTS:
        print("[INFO] Controller is already at stored steering zero.")
        return

    print("[STATUS] Returning controller to stored steering zero after calibration.")
    mic.set_device_mode_position()
    mic.set_RPM(rpm)
    if hasattr(mic, "set_steering_RPM"):
        mic.set_steering_RPM(rpm)
    mic.enabled(True)
    try:
        mic.set_steering_pos(0)
    except Exception as exc:
        print(f"[WARN] Absolute zero return command failed: {exc}")
        if start_pos is None:
            raise
        print(f"[STATUS] Trying relative zero return by {-int(start_pos)} counts.")
        mic.set_steering_relative(-int(start_pos))

    deadline = time.monotonic() + ZERO_RETURN_TIMEOUT_S
    end_pos = start_pos
    while time.monotonic() < deadline:
        time.sleep(0.25)
        end_pos = mic.get_steering_pos()
        if end_pos is not None and abs(int(end_pos)) <= ZERO_POSITION_TOLERANCE_COUNTS:
            break

    time.sleep(ZERO_RETURN_SETTLE_S)
    end_pos = mic.get_steering_pos()
    print(f"[INFO] Controller steering position after stored-zero return: {end_pos}")
    if end_pos is not None and abs(int(end_pos)) > ZERO_POSITION_TOLERANCE_COUNTS:
        velocity = mic.get_velocity() if hasattr(mic, "get_velocity") else None
        error_code = mic.get_error_code() if hasattr(mic, "get_error_code") else None
        print(
            "[WARN] Controller did not return to stored steering zero: "
            f"position={end_pos} velocity={velocity} error={error_code}"
        )


# =====================================================================================
# Current wait helper
# =====================================================================================
def wait_until_current_reached(
    mic: MicontrolF35_CAN,
    desired_current: int,
    tolerance: int = 100,
    poll_s: float = 0.05,
    timeout_s: Optional[float] = None,
) -> Optional[int]:
    start = time.time()
    while True:
        actual_current = mic.get_actual_current()
        if abs(actual_current - desired_current) <= tolerance:
            print(
                f"[INFO] Current reached: actual={actual_current} "
                f"desired={desired_current} tol={tolerance}"
            )
            return int(actual_current)
        if timeout_s is not None and (time.time() - start) >= timeout_s:
            print(
                f"[ERROR] Current not reached within {timeout_s:.1f}s: "
                f"last_actual={actual_current} desired={desired_current} tol={tolerance}"
            )
            return None
        time.sleep(poll_s)


# =====================================================================================
# MAIN
# =====================================================================================
def main(serial_last4: str = "", can_bitrate: int = 125, node: int = 50):

    # CAN setup
    # === Flash config from SteeringScript.py ===
    can = DriverCan(can_bitrate=can_bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        print("[ERROR] Could not add CAN node.")
        try:
            can.close_can()
        except Exception:
            pass
        return False
    #dsa = DSACompat(mic.added_node)
    #script_path = import_script_via_qr()
    #print(f"[INFO] Using script: {script_path}")

    #steer_mod, apply_fn, arity = load_config_function(script_path)
    print("[INFO] Applying configuration from steering script...")
    #apply_fn(dsa)
    try:
        #can, mic = restart_controller(can, mic, node = 50, can_bitrate=can_bitrate)
        time.sleep(1.0)  # wait for restart

        mic.SSI_encoder(False)

        mic.set_current_mode()
        mic.clear_errors()
        mic.enabled(True)

        desired_current = 3000
        mic.set_desired_current(desired_current)

        mic.set_digital_output(True)  # select enc 0 by default

        time.sleep(60)
        wait_until_current_reached(mic, desired_current, tolerance=100, timeout_s=None)

        ok_enc_1 = calibrate_one_encoder(
            export_dir=EXPORT_DIR_1,
            serial_last4=serial_last4,
            saved_config_path=CALIBRATED_CONFIG_PATH_1,
        )
        time.sleep(1.0)
        print(f"[RESULT] encoder_1 calibration ok={ok_enc_1}")

        mic.set_digital_output(False)  # select enc 1
        mic.clear_errors()
        mic.clear_errors()

        #wait_until_current_reached(mic, desired_current, tolerance=100, timeout_s=None)

        ok_enc_2 = calibrate_one_encoder(
            export_dir=EXPORT_DIR_2,
            serial_last4=serial_last4,
            saved_config_path=CALIBRATED_CONFIG_PATH_2,
        )
        time.sleep(1.0)
        print(f"[RESULT] encoder_2 calibration ok={ok_enc_2}")

        overall_ok = bool(ok_enc_1 and ok_enc_2)
        print(f"[RESULT] full calibration ok={overall_ok}")
        return overall_ok
    finally:
        try:
            mic.enabled(False)
        except Exception:
            pass
        try:
            if mic.SSI_encoder(True):
                print("[INFO] SSI_encoder(True) set after full calibration.")
                mic.clear_errors()
                mic.clear_errors()
                mic.set_device_mode_position()
                mode = mic.get_device_mode() if hasattr(mic, "get_device_mode") else None
                print(
                    "[INFO] Controller changed from calibration current mode to "
                    f"position mode before storing parameters: mode={mode}"
                )
                if mode is not None and mode != 7:
                    print(
                        "[WARN] Controller position-mode readback was not 7 before "
                        f"storing parameters: mode={mode}"
                    )
                if mic.store_parameters():
                    print("[INFO] Controller parameters stored after full calibration.")
                else:
                    print("[WARN] Controller parameters were not stored after full calibration.")
            else:
                print("[WARN] SSI_encoder(True) did not report success after full calibration.")
        except Exception as exc:
            print(f"[WARN] Failed to set SSI_encoder(True) after full calibration: {exc}")
        try:
            mic.clear_errors()
            mic.clear_errors()
        except Exception as exc:
            print(f"[WARN] Failed to clear errors after full calibration: {exc}")
        try:
            restarted_can, restarted_mic = restart_controller(
                can=can,
                mic=mic,
                node=node,
                can_bitrate=can_bitrate,
            )
            if restarted_can and restarted_mic:
                can, mic = restarted_can, restarted_mic
                print("[INFO] Controller restarted after full calibration.")
                print(
                    "[INFO] Stored controller zero may be stale after encoder calibration; "
                    "caller should measure and compensate physical zero shift before "
                    "normal steering use."
                )
            else:
                print("[WARN] Controller restart after full calibration did not complete.")
        except Exception as exc:
            print(f"[WARN] Failed to restart controller after full calibration: {exc}")
        try:
            can.close_can()
        except Exception:
            pass

if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="full calibration")
    try:
        main(serial_last4="")
    finally:
        restore_sigint()
