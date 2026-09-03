from __future__ import annotations

import argparse
import ctypes
from ctypes import POINTER, c_size_t, c_uint16
from datetime import datetime
from pathlib import Path
import time
from typing import Any

from utils.interrupt_guard import install_deferred_keyboard_interrupt
from logic.calibration_quality import build_quality_report, evaluate_quality


BASE_DIR = Path(__file__).resolve().parent
TEST_EXPORT_DIR = BASE_DIR / "MU" / "calib_logs" / "test_calibration"
DEFAULT_CAN_BITRATE = 125
DEFAULT_NODE_ID = 50
DEFAULT_SPIN_SECONDS = 60.0
DEFAULT_RPM = 1000
ZERO_RETURN_SETTLE_S = 2.0
ZERO_RETURN_TIMEOUT_S = 6.0
ZERO_POSITION_TOLERANCE_COUNTS = 3

_FULL_CALIBRATION_IMPORTS: dict[str, Any] | None = None


def _full_calibration_imports() -> dict[str, Any]:
    global _FULL_CALIBRATION_IMPORTS
    if _FULL_CALIBRATION_IMPORTS is None:
        from logic.FullCalibration import (
            MU_Handle,
            _acquire_raw_data,
            _close_session,
            _collect_quality_metrics,
            _mu_last_error,
            _open_session,
            _select_encoder,
            mu,
        )

        _FULL_CALIBRATION_IMPORTS = {
            "MU_Handle": MU_Handle,
            "_acquire_raw_data": _acquire_raw_data,
            "_close_session": _close_session,
            "_collect_quality_metrics": _collect_quality_metrics,
            "_mu_last_error": _mu_last_error,
            "_open_session": _open_session,
            "_select_encoder": _select_encoder,
            "mu": mu,
        }
    return _FULL_CALIBRATION_IMPORTS


def spin_motor(mic: Any, rpm: int, duration_s: float) -> None:
    print(f"[INFO] Spinning motor at {rpm} RPM for {duration_s:.1f}s")
    mic.clear_errors()
    mic.set_velocity_mode()
    mic.set_RPM(rpm)
    mic.enabled(True)

    start = time.monotonic()
    next_log = start
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration_s:
            break

        if time.monotonic() >= next_log:
            velocity = mic.get_velocity()
            print(
                f"[INFO] Spin progress {elapsed:5.1f}/{duration_s:.1f}s "
                f"velocity={velocity}"
            )
            next_log += 10.0
        time.sleep(0.2)

    print("[INFO] Spin period complete; motor remains enabled for MU acquisition.")


def return_controller_to_zero(mic: Any, rpm: int) -> None:
    initial_pos = mic.get_steering_pos()
    print(f"[INFO] Controller steering position before zero return: {initial_pos}")

    if hasattr(mic, "restore_extended_ssi_mode"):
        try:
            mic.restore_extended_ssi_mode()
        except Exception as exc:
            print(f"[WARN] Failed to restore extended SSI before zero return: {exc}")

    mic.clear_errors()
    mic.clear_errors()
    if mic.SSI_encoder(True):
        print("[INFO] SSI encoder enabled before zero return.")
    else:
        print("[WARN] SSI encoder enable did not report success before zero return.")
    ssi_status = mic.get_ssi_encoder_status()
    ssi_direct_pos = mic.get_ssi_direct_position()
    start_pos = mic.get_steering_pos()
    print(
        "[INFO] Controller SSI state before zero return: "
        f"status={ssi_status} direct_position={ssi_direct_pos} steering_position={start_pos}"
    )

    if start_pos is not None and abs(start_pos) <= ZERO_POSITION_TOLERANCE_COUNTS:
        print("[INFO] Controller is already at steering position 0.")
        return

    print("[STATUS] Returning controller to steering position 0 after test calibration.")

    if hasattr(mic, "prepare_position_motion"):
        if not mic.prepare_position_motion(rpm):
            mode = mic.get_device_mode() if hasattr(mic, "get_device_mode") else None
            error = mic.get_error_code() if hasattr(mic, "get_error_code") else None
            position = mic.get_steering_pos() if hasattr(mic, "get_steering_pos") else None
            raise RuntimeError(
                "Controller is not ready for zero-return position commands: "
                f"mode={mode} error={error} steering_position={position}."
            )
    else:
        mic.set_device_mode_position()
        mic.set_RPM(rpm)
        mic.set_steering_RPM(rpm)
        mic.enabled(True)
    try:
        mic.set_steering_pos(0)
    except Exception as exc:
        print(f"[WARN] Absolute zero return command failed: {exc}")
        if start_pos is None:
            raise
        print(f"[STATUS] Trying relative zero return by {-int(start_pos)} counts.")
        mic.clear_errors()
        if hasattr(mic, "prepare_position_motion") and not mic.prepare_position_motion(rpm):
            raise RuntimeError("Controller is not ready for relative zero-return command.") from exc
        mic.set_steering_relative(-int(start_pos))

    deadline = time.monotonic() + ZERO_RETURN_TIMEOUT_S
    end_pos = start_pos
    while time.monotonic() < deadline:
        time.sleep(0.25)
        end_pos = mic.get_steering_pos()
        if end_pos is not None and abs(end_pos) <= ZERO_POSITION_TOLERANCE_COUNTS:
            break

    time.sleep(ZERO_RETURN_SETTLE_S)
    end_pos = mic.get_steering_pos()
    print(f"[INFO] Controller steering position after zero return: {end_pos}")
    if end_pos is not None and abs(end_pos) > ZERO_POSITION_TOLERANCE_COUNTS:
        velocity = mic.get_velocity()
        error_code = mic.get_error_code()
        print(
            "[WARN] Controller did not return to steering position 0: "
            f"position={end_pos} velocity={velocity} error={error_code}"
        )


def check_encoder_quality_result(
    mic: Any,
    enc_idx: int,
    export_dir: Path,
    serial_last4: str,
    n_samples: int,
    frame_cycle_time_s: float,
    clock_frequency_hz: float,
    final_residual_cap_lsb: float,
    max_phase_margin_pct: float,
) -> dict[str, Any]:
    # Read-only quality check: no MU_setCalibration, adjustment, WriteParams, or EEPROM write.
    fc = _full_calibration_imports()
    MU_Handle = fc["MU_Handle"]
    _acquire_raw_data = fc["_acquire_raw_data"]
    _close_session = fc["_close_session"]
    _collect_quality_metrics = fc["_collect_quality_metrics"]
    _mu_last_error = fc["_mu_last_error"]
    _open_session = fc["_open_session"]
    _select_encoder = fc["_select_encoder"]
    mu = fc["mu"]

    export_dir.mkdir(parents=True, exist_ok=True)
    _select_encoder(mic, enc_idx)

    handle = MU_Handle()
    if not _open_session(handle, serial_last4):
        _close_session(handle)
        return {
            "encoder": enc_idx + 1,
            "ok": False,
            "error": "Could not open MU session.",
        }

    calibration = None
    analyze = None
    try:
        print(f"[INFO] Checking encoder_{enc_idx + 1} calibration quality")
        print("[INFO] Objective check only: reading existing calibration and analyzing new raw data.")
        ret = int(mu.MU_ReadParams(handle))
        if ret != 0:
            error = f"MU_ReadParams failed rc={ret} ({_mu_last_error(handle)})"
            print(f"[ERROR] {error}")
            return {
                "encoder": enc_idx + 1,
                "ok": False,
                "error": error,
            }

        calibration = mu.MU_getCalibration(handle)
        if not calibration:
            print("[ERROR] MU_getCalibration returned NULL")
            return {
                "encoder": enc_idx + 1,
                "ok": False,
                "error": "MU_getCalibration returned NULL.",
            }

        master_arr, nonius_arr, acquisition_timing, rc = _acquire_raw_data(
            handle,
            n_samples=n_samples,
            frame_cycle_time_s=frame_cycle_time_s,
            clock_frequency_hz=clock_frequency_hz,
        )
        if rc != 0:
            error = f"Raw data acquisition/config failed rc={rc} ({_mu_last_error(handle)})"
            print(f"[ERROR] {error}")
            return {
                "encoder": enc_idx + 1,
                "ok": False,
                "error": error,
            }
        if master_arr is None or nonius_arr is None or acquisition_timing is None:
            print("[ERROR] Raw data acquisition did not return buffers.")
            return {
                "encoder": enc_idx + 1,
                "ok": False,
                "error": "Raw data acquisition did not return buffers.",
            }

        analyze = mu.MU_Calibration_analyzeRawData(
            calibration,
            ctypes.cast(master_arr, POINTER(c_uint16)),
            ctypes.cast(nonius_arr, POINTER(c_uint16)),
            c_size_t(n_samples),
        )
        if not analyze:
            print("[ERROR] analyzeRawData returned NULL.")
            return {
                "encoder": enc_idx + 1,
                "ok": False,
                "error": "analyzeRawData returned NULL.",
            }

        metrics = _collect_quality_metrics(
            analyze,
            analog_residual_history=[],
            acquisition_timing=acquisition_timing,
        )
        evaluation = evaluate_quality(
            metrics,
            final_residual_cap_lsb=final_residual_cap_lsb,
            max_phase_margin_pct=max_phase_margin_pct,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = export_dir / f"test_calibration_report_{timestamp}.txt"
        report_path.write_text(
            build_quality_report(1, metrics, evaluation),
            encoding="utf-8",
        )

        nonius_phase_margin_pct = float(metrics.max_abs_phase_margin_pct_of_range_limit)
        phase_margin_ok = nonius_phase_margin_pct <= float(max_phase_margin_pct)
        ok = bool(evaluation.ok)

        print(f"[RESULT] encoder_{enc_idx + 1} quality={'PASS' if ok else 'FAIL'}")
        print(
            f"[RESULT] encoder_{enc_idx + 1} "
            f"max_abs_analog_residual={metrics.max_abs_analog_residual_lsb:.4f} LSB"
        )
        print(
            f"[RESULT] encoder_{enc_idx + 1} "
            f"nonius_phase_margin={nonius_phase_margin_pct:.3f}% "
            f"of range_limit"
        )
        print(
            f"[RESULT] encoder_{enc_idx + 1} "
            f"nonius_phase_clearance upper/lower="
            f"{metrics.upper_phase_margin_pct:.3f}%/{metrics.lower_phase_margin_pct:.3f}%"
        )
        print(
            f"[RESULT] encoder_{enc_idx + 1} threshold={max_phase_margin_pct:.3f}% "
            f"nonius_phase_margin_ok={phase_margin_ok}"
        )
        print(f"[RESULT] encoder_{enc_idx + 1} quality_gate_reason={evaluation.reason}")
        print(f"[INFO] wrote {report_path}")
        return {
            "encoder": enc_idx + 1,
            "ok": ok,
            "phase_margin_pct": nonius_phase_margin_pct,
            "nonius_phase_margin_pct": nonius_phase_margin_pct,
            "nonius_upper_phase_margin_pct": float(metrics.upper_phase_margin_pct),
            "nonius_lower_phase_margin_pct": float(metrics.lower_phase_margin_pct),
            "max_allowed_phase_margin_pct": float(max_phase_margin_pct),
            "phase_margin_ok": phase_margin_ok,
            "nonius_phase_margin_ok": phase_margin_ok,
            "report_path": str(report_path),
            "error": "" if ok else evaluation.reason,
        }

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
        mic.clear_errors()


def check_encoder_quality(
    mic: Any,
    enc_idx: int,
    export_dir: Path,
    serial_last4: str,
    n_samples: int,
    frame_cycle_time_s: float,
    clock_frequency_hz: float,
    final_residual_cap_lsb: float,
    max_phase_margin_pct: float,
) -> bool:
    result = check_encoder_quality_result(
        mic=mic,
        enc_idx=enc_idx,
        export_dir=export_dir,
        serial_last4=serial_last4,
        n_samples=n_samples,
        frame_cycle_time_s=frame_cycle_time_s,
        clock_frequency_hz=clock_frequency_hz,
        final_residual_cap_lsb=final_residual_cap_lsb,
        max_phase_margin_pct=max_phase_margin_pct,
    )
    return bool(result.get("ok"))


def main(
    serial_last4: str = "",
    can_bitrate: int = DEFAULT_CAN_BITRATE,
    node: int = DEFAULT_NODE_ID,
    rpm: int = DEFAULT_RPM,
    spin_seconds: float = DEFAULT_SPIN_SECONDS,
    n_samples: int = 64000,
    frame_cycle_time_s: float = 187.5e-6,
    clock_frequency_hz: float = 2.0e6,
    final_residual_cap_lsb: float = 20.0,
    max_phase_margin_pct: float = 50.0,
) -> bool:
    from drivers.driver_can import DriverCan
    from drivers.driver_miControlF35 import MicontrolF35_CAN
    from logic.FullCalibration import restart_controller

    can = DriverCan(can_bitrate=can_bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        print("[ERROR] Could not add CAN node.")
        can.close_can()
        return False

    try:
        if mic.SSI_encoder(False):
            print("[INFO] SSI_encoder(False) set for MU acquisition.")
        else:
            print("[ERROR] SSI_encoder(False) did not report success.")
            return False

        spin_motor(mic, rpm=rpm, duration_s=spin_seconds)

        ok_enc_1 = check_encoder_quality(
            mic=mic,
            enc_idx=0,
            export_dir=TEST_EXPORT_DIR / "enc_1",
            serial_last4=serial_last4,
            n_samples=n_samples,
            frame_cycle_time_s=frame_cycle_time_s,
            clock_frequency_hz=clock_frequency_hz,
            final_residual_cap_lsb=final_residual_cap_lsb,
            max_phase_margin_pct=max_phase_margin_pct,
        )
        ok_enc_2 = check_encoder_quality(
            mic=mic,
            enc_idx=1,
            export_dir=TEST_EXPORT_DIR / "enc_2",
            serial_last4=serial_last4,
            n_samples=n_samples,
            frame_cycle_time_s=frame_cycle_time_s,
            clock_frequency_hz=clock_frequency_hz,
            final_residual_cap_lsb=final_residual_cap_lsb,
            max_phase_margin_pct=max_phase_margin_pct,
        )

        overall_ok = bool(ok_enc_1 and ok_enc_2)
        print(f"[RESULT] test calibration ok={overall_ok}")
        return overall_ok
    finally:
        try:
            mic.set_desired_current(0)
        except Exception:
            pass
        try:
            mic.set_RPM(0)
        except Exception:
            pass
        try:
            mic.enabled(False)
        except Exception:
            pass
        try:
            if mic.SSI_encoder(True):
                print("[INFO] SSI_encoder(True) set.")
                if mic.store_parameters():
                    print("[INFO] Controller parameters stored after SSI_encoder(True).")
                else:
                    print("[WARN] Controller parameters were not stored after SSI_encoder(True).")
            else:
                print("[WARN] SSI_encoder(True) did not report success.")
        except Exception as exc:
            print(f"[WARN] Failed to set SSI_encoder(True): {exc}")
        try:
            mic.clear_errors()
            mic.clear_errors()
        except Exception as exc:
            print(f"[WARN] Failed to clear errors during cleanup: {exc}")
        try:
            restarted_can, restarted_mic = restart_controller(
                can=can,
                mic=mic,
                node=node,
                can_bitrate=can_bitrate,
            )
            if restarted_can and restarted_mic:
                can, mic = restarted_can, restarted_mic
                print("[INFO] Controller restarted after test calibration.")
            else:
                print("[WARN] Controller restart after test calibration did not complete.")
        except Exception as exc:
            print(f"[WARN] Failed to restart controller after test calibration: {exc}")
        try:
            mic.set_RPM(0)
        except Exception:
            pass
        try:
            mic.enabled(False)
        except Exception:
            pass
        try:
            can.close_can()
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spin the steering motor, then check existing iC-MU calibration quality."
    )
    parser.add_argument("--serial-last4", default="", help="Last 4 chars of the MU adapter serial.")
    parser.add_argument("--can-bitrate", type=int, default=DEFAULT_CAN_BITRATE, help="CAN bitrate in kbit/s.")
    parser.add_argument("--node", type=int, default=DEFAULT_NODE_ID, help="MiControl CAN node ID.")
    parser.add_argument("--rpm", type=int, default=DEFAULT_RPM, help="Motor RPM during the test.")
    parser.add_argument("--spin-seconds", type=float, default=DEFAULT_SPIN_SECONDS, help="Spin duration before quality acquisition.")
    parser.add_argument("--samples", type=int, default=64000, help="Raw samples per encoder.")
    parser.add_argument("--frame-cycle-time-s", type=float, default=187.5e-6, help="Requested MU frame cycle time.")
    parser.add_argument("--clock-frequency-hz", type=float, default=2.0e6, help="Requested MU clock frequency.")
    parser.add_argument("--final-residual-cap-lsb", type=float, default=20.0, help="Quality gate residual cap.")
    parser.add_argument("--max-phase-margin-pct", type=float, default=50.0, help="Quality gate nonius phase margin cap.")
    return parser.parse_args()


if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="test calibration")
    try:
        args = parse_args()
        raise SystemExit(
            0
            if main(
                serial_last4=args.serial_last4,
                can_bitrate=args.can_bitrate,
                node=args.node,
                rpm=args.rpm,
                spin_seconds=args.spin_seconds,
                n_samples=args.samples,
                frame_cycle_time_s=args.frame_cycle_time_s,
                clock_frequency_hz=args.clock_frequency_hz,
                final_residual_cap_lsb=args.final_residual_cap_lsb,
                max_phase_margin_pct=args.max_phase_margin_pct,
            )
            else 1
        )
    finally:
        restore_sigint()
