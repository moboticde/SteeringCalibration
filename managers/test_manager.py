# test_manager.py
import time
import pandas as pd
import math
import importlib
import os
from operator import methodcaller
from datetime import datetime
from pathlib import Path
from processing.data_processing import DataProcessing
from processing.plot_generator import PlotGenerator
from logic.traction import traction_feedback, update_timeteration
from logic.TractionHC import traction_feedback_hc
from logic.brake import measure_braking
from logic.steering_app import steering_feedback, update_sttimeite

from utils.utils import safe_execute, error_prompt


ZERO_VISUAL_TOLERANCE_DEG = 1.0
ZERO_POSITION_TOLERANCE_COUNTS = 3
ZERO_MOVE_RPM = 1000
ZERO_MOVE_SETTLE_S = 2.0
ZERO_MOVE_TIMEOUT_S = 25.0
ANGLE_SETTLE_S = 2.0
ANGLE_SAMPLES = 20
ANGLE_TIMEOUT_S = 20.0
ANGLE_READ_ATTEMPTS = 2
CONF_REQUIRED_COLUMNS = ("Serial number", "Configuration", "Write Zero", "Calibration")
CONF_REQUIRED_OK_SEQUENCE = ("Calibration", "Write Zero", "Configuration")


class TestRunner:
    def __init__(self, arduino, controller=None, config=None, motor_number=None, multimeter=None, unit_serial_number=None, tester_name=None):
        """
        Initialize TestRunner with Arduino and commonly used test parameters.
        """
        self.arduino = arduino
        self.controller = controller
        self.config = config
        self.motor_number = motor_number
        self.multimeter = multimeter
        self.unit_serial_number = unit_serial_number
        self.dp = DataProcessing()
        self.pg = PlotGenerator()
        self.tester_name = tester_name

    @staticmethod
    def _to_float(value, default=None):
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _to_int(value, default=None):
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _angle_error_deg(measured_angle, desired_angle):
        return abs((float(measured_angle) - float(desired_angle) + 180.0) % 360.0 - 180.0)

    def _product_parameter(self, *names, default=None):
        if not self.config:
            return default
        for name in names:
            value = self.config.get_product_parameter(name, default=None)
            if value is not None and not (isinstance(value, float) and math.isnan(value)):
                return value
        return default

    @staticmethod
    def _safe_filename_token(value, fallback="barcode"):
        text = str(value or "").strip()
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)
        safe = safe.strip("._")
        return safe[:80] or fallback

    @staticmethod
    def _conf_status_ok(value):
        return str(value or "").strip().lower() == "ok"

    def _conf_status_candidates(self):
        if not self.config:
            return []

        base_path = getattr(self.config, "BASE_PATH", None) or getattr(self.config, "path", None)
        if not base_path:
            return []

        result_dir = Path(base_path) / "04_Results"
        candidates = []
        if self.unit_serial_number:
            token = self._safe_filename_token(self.unit_serial_number)
            candidates.append(result_dir / f"{token}_status.xlsx")
            candidates.append(result_dir / f"{token}_done.xlsx")
        elif result_dir.is_dir():
            candidates.extend(
                sorted(
                    [*result_dir.glob("*_status.xlsx"), *result_dir.glob("*_done.xlsx")],
                    key=os.path.getmtime,
                    reverse=True,
                )
            )

        unique = []
        seen = set()
        for candidate in candidates:
            resolved = os.fspath(candidate)
            if resolved not in seen:
                unique.append(candidate)
                seen.add(resolved)
        return unique

    def _read_conf_status_sheet(self):
        errors = []
        for path in self._conf_status_candidates():
            if not path.is_file():
                errors.append(f"{path} does not exist")
                continue
            try:
                return path, pd.read_excel(path, sheet_name="conf", engine="openpyxl")
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        detail = "\n  - ".join(errors) if errors else "No status workbook candidates found."
        raise RuntimeError(
            "Configuration status workbook could not be read. "
            "Run the Configuration, Write Zero, and Calibration process first.\n"
            f"  - {detail}"
        )

    def verify_configuration_processes_done(self):
        """
        Confirm that the latest calibration status row has a serial number and
        Calibration, Write Zero, and Configuration are all OK.
        """
        path, df = self._read_conf_status_sheet()
        missing = [column for column in CONF_REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise RuntimeError(
                f"Configuration status workbook is missing columns: {', '.join(missing)}. "
                f"Workbook: {path}"
            )

        status_rows = df.dropna(how="all")
        if status_rows.empty:
            raise RuntimeError(
                "Configuration process is not complete. The 'conf' sheet has no status rows. "
                f"Workbook: {path}"
            )

        latest_row = status_rows.iloc[-1]
        serial_value = latest_row.get("Serial number", "")
        serial = "" if pd.isna(serial_value) else str(serial_value).strip()
        if serial and serial != "-" and all(
            self._conf_status_ok(latest_row.get(column))
            for column in CONF_REQUIRED_OK_SEQUENCE
        ):
            print(f"[INFO] Configuration status verified for serial number {serial}: {path}")
            return True

        summary_columns = ["Serial number", *CONF_REQUIRED_OK_SEQUENCE]
        summary = latest_row[summary_columns].fillna("-").to_frame().T.to_string(index=False)
        raise RuntimeError(
            "Configuration process is not complete. The latest row in the 'conf' sheet must "
            "have a serial number and Calibration, Write Zero, and Configuration all OK. "
            f"Workbook: {path}\nLatest row:\n{summary}"
        )

    def _read_camera_angle_deg(self, context):
        from drivers.driver_cam_st import AngleDetection

        for attempt in range(1, ANGLE_READ_ATTEMPTS + 1):
            print(f"[STATUS] Waiting {ANGLE_SETTLE_S:.1f}s for camera angle to stabilize.")
            time.sleep(ANGLE_SETTLE_S)
            print(
                f"[STATUS] Reading camera angle for {context} "
                f"({ANGLE_SAMPLES} samples, timeout {ANGLE_TIMEOUT_S:.0f}s, "
                f"attempt {attempt}/{ANGLE_READ_ATTEMPTS})."
            )
            angle = AngleDetection(
                debug=False,
                return_after=ANGLE_SAMPLES,
                timeout_s=ANGLE_TIMEOUT_S,
            )
            if angle is not None:
                print(f"[INFO] Camera angle for {context}: {float(angle):.2f} deg")
                return float(angle)
            if attempt < ANGLE_READ_ATTEMPTS:
                print("[WARN] Camera angle was not detected; retrying once.")

        raise RuntimeError(
            f"Could not measure steering angle during {context}. "
            "Check that the webcam is connected, accessible, not already in use, "
            "and that the marker is visible."
        )

    def _move_controller_to_zero(self, context="zero check", rpm=ZERO_MOVE_RPM):
        if not hasattr(self.controller, "get_steering_pos"):
            raise RuntimeError("Controller does not support steering zero position reads.")

        initial_pos = self.controller.get_steering_pos()
        print(f"[INFO] Controller steering position before {context}: {initial_pos}")

        try:
            self.controller.clear_errors()
            self.controller.clear_errors()
        except Exception:
            pass

        if hasattr(self.controller, "SSI_encoder"):
            if self.controller.SSI_encoder(True):
                print("[INFO] SSI encoder enabled before zero check.")
            else:
                print("[WARN] SSI encoder enable did not report success before zero check.")

        start_pos = self.controller.get_steering_pos()
        if start_pos is not None and abs(int(start_pos)) <= ZERO_POSITION_TOLERANCE_COUNTS:
            print(
                "[INFO] Controller is already at steering position 0; "
                f"position={start_pos} counts."
            )
            return int(start_pos)

        print("[STATUS] Commanding controller steering position 0.")
        self.controller.set_device_mode_position()
        if hasattr(self.controller, "set_RPM"):
            self.controller.set_RPM(rpm)
        if hasattr(self.controller, "set_steering_RPM"):
            self.controller.set_steering_RPM(rpm)
        self.controller.enabled(True)

        try:
            self.controller.set_steering_pos(0)
        except Exception as exc:
            if start_pos is None or not hasattr(self.controller, "set_steering_relative"):
                raise
            print(f"[WARN] Absolute zero move command failed: {exc}")
            print(f"[STATUS] Trying relative zero move by {-int(start_pos)} counts.")
            self.controller.set_steering_relative(-int(start_pos))

        deadline = time.monotonic() + ZERO_MOVE_TIMEOUT_S
        steering_pos = start_pos
        velocity = None
        while time.monotonic() < deadline:
            time.sleep(0.25)
            steering_pos = self.controller.get_steering_pos()
            if hasattr(self.controller, "get_velocity"):
                velocity = self.controller.get_velocity()
            if (
                steering_pos is not None
                and abs(int(steering_pos)) <= ZERO_POSITION_TOLERANCE_COUNTS
                and (velocity is None or abs(int(velocity)) <= 1)
            ):
                break

        time.sleep(ZERO_MOVE_SETTLE_S)
        steering_pos = self.controller.get_steering_pos()
        print(
            f"[INFO] Controller steering position after {context}: "
            f"{steering_pos} velocity={velocity}"
        )
        if steering_pos is None:
            raise RuntimeError("Controller steering position could not be read after zero move.")
        if abs(int(steering_pos)) > ZERO_POSITION_TOLERANCE_COUNTS:
            error_code = self.controller.get_error_code() if hasattr(self.controller, "get_error_code") else None
            raise RuntimeError(
                "Controller did not reach steering position 0: "
                f"position={steering_pos} velocity={velocity} error={error_code}."
            )
        return int(steering_pos)

    def test_calibration(self, info, product_parameters):
        TestCalibration = importlib.import_module("tests.TestCalibration")
        controller_firmware = str(info.get("controller_firmware", ""))
        rows = []
        columns = [
            "Encoder",
            "phase_margin_pct",
            "nonius_phase_margin_pct",
            "nonius_upper_phase_margin_pct",
            "nonius_lower_phase_margin_pct",
            "Specification",
            "Result",
            "Match",
            "Details",
            "Report Path",
        ]

        if not hasattr(self.controller, "SSI_encoder"):
            return pd.DataFrame([{
                "Encoder": "",
                "phase_margin_pct": "",
                "nonius_phase_margin_pct": "",
                "nonius_upper_phase_margin_pct": "",
                "nonius_lower_phase_margin_pct": "",
                "Specification": "nonius_phase_margin_pct <= 50%; upper/lower clearances are informational",
                "Result": "Skipped",
                "Match": "",
                "Details": f"Unsupported controller: {controller_firmware}",
                "Report Path": "",
            }], columns=columns)

        rpm = self._to_int(
            self._product_parameter("Test Calibration RPM", "Calibration Test RPM", default=None),
            getattr(TestCalibration, "DEFAULT_RPM", 1000),
        )
        spin_seconds = self._to_float(
            self._product_parameter("Test Calibration Spin Seconds", "Test Calibration Duration", default=None),
            getattr(TestCalibration, "DEFAULT_SPIN_SECONDS", 60.0),
        )
        n_samples = self._to_int(
            self._product_parameter("Test Calibration Samples", default=None),
            64000,
        )
        frame_cycle_time_s = self._to_float(
            self._product_parameter("Test Calibration Frame Cycle Time s", default=None),
            187.5e-6,
        )
        clock_frequency_hz = self._to_float(
            self._product_parameter("Test Calibration Clock Frequency Hz", default=None),
            2.0e6,
        )
        final_residual_cap_lsb = self._to_float(
            self._product_parameter("Calibration Final Residual Cap LSB", default=None),
            20.0,
        )
        max_phase_margin_pct = 50.0
        serial_last4 = str(product_parameters.get("MU Serial Last4") or "").strip()

        try:
            if self.controller.SSI_encoder(False):
                print("[INFO] SSI_encoder(False) set for TestCalibration MU acquisition.")
            else:
                raise RuntimeError("SSI_encoder(False) did not report success.")

            TestCalibration.spin_motor(self.controller, rpm=rpm, duration_s=spin_seconds)

            encoder_results = []
            for enc_idx in (0, 1):
                result = TestCalibration.check_encoder_quality_result(
                    mic=self.controller,
                    enc_idx=enc_idx,
                    export_dir=TestCalibration.TEST_EXPORT_DIR / f"enc_{enc_idx + 1}",
                    serial_last4=serial_last4,
                    n_samples=n_samples,
                    frame_cycle_time_s=frame_cycle_time_s,
                    clock_frequency_hz=clock_frequency_hz,
                    final_residual_cap_lsb=final_residual_cap_lsb,
                    max_phase_margin_pct=max_phase_margin_pct,
                )
                ok = bool(result.get("ok"))
                encoder_results.append(ok)
                rows.append({
                    "Encoder": f"encoder_{enc_idx + 1}",
                    "phase_margin_pct": result.get("phase_margin_pct", ""),
                    "nonius_phase_margin_pct": result.get("nonius_phase_margin_pct", ""),
                    "nonius_upper_phase_margin_pct": result.get("nonius_upper_phase_margin_pct", ""),
                    "nonius_lower_phase_margin_pct": result.get("nonius_lower_phase_margin_pct", ""),
                    "Specification": f"nonius_phase_margin_pct <= {max_phase_margin_pct}%; upper/lower clearances are informational",
                    "Result": "PASS" if ok else "FAIL",
                    "Match": ok,
                    "Details": result.get("error", ""),
                    "Report Path": result.get("report_path", ""),
                })
                print(
                    "[RESULT] calibration sheet row -> "
                    f"encoder_{enc_idx + 1} "
                    f"phase_margin={result.get('phase_margin_pct', '')} "
                    f"nonius_phase_margin={result.get('nonius_phase_margin_pct', '')} "
                    f"result={'PASS' if ok else 'FAIL'}"
                )

            overall_ok = all(encoder_results)
            rows.append({
                "Encoder": "overall",
                "phase_margin_pct": "",
                "nonius_phase_margin_pct": "",
                "nonius_upper_phase_margin_pct": "",
                "nonius_lower_phase_margin_pct": "",
                "Specification": "Both encoders PASS",
                "Result": "PASS" if overall_ok else "FAIL",
                "Match": bool(overall_ok),
                "Details": "",
                "Report Path": "",
            })

        except Exception as exc:
            rows.append({
                "Encoder": "overall",
                "phase_margin_pct": "",
                "nonius_phase_margin_pct": "",
                "nonius_upper_phase_margin_pct": "",
                "nonius_lower_phase_margin_pct": "",
                "Specification": f"nonius_phase_margin_pct <= {max_phase_margin_pct}%; upper/lower clearances are informational",
                "Result": "ERROR",
                "Match": False,
                "Details": str(exc),
                "Report Path": "",
            })
        finally:
            try:
                self.controller.set_desired_current(0)
            except Exception:
                pass
            try:
                self.controller.set_RPM(0)
            except Exception:
                pass
            try:
                self.controller.enabled(False)
            except Exception:
                pass
            try:
                if self.controller.SSI_encoder(True):
                    print("[INFO] SSI_encoder(True) set after TestCalibration.")
                    try:
                        self.controller.clear_errors()
                        self.controller.clear_errors()
                        self.controller.set_device_mode_position()
                        mode = self.controller.get_device_mode() if hasattr(self.controller, "get_device_mode") else None
                        print(
                            "[INFO] Controller changed from calibration current mode to "
                            f"position mode before storing parameters: mode={mode}"
                        )
                    except Exception as exc:
                        print(f"[WARN] Failed to prepare position mode before storing parameters: {exc}")
                    if hasattr(self.controller, "store_parameters"):
                        if self.controller.store_parameters():
                            print("[INFO] Controller parameters stored after TestCalibration.")
                        else:
                            print("[WARN] Controller parameters were not stored after TestCalibration.")
                else:
                    print("[WARN] SSI_encoder(True) did not report success after TestCalibration.")
            except Exception as exc:
                print(f"[WARN] Failed to restore SSI encoder after TestCalibration: {exc}")
            try:
                self.controller.clear_errors()
                self.controller.clear_errors()
            except Exception:
                pass
            try:
                can_driver = info.get("can")
                node = info.get("node")
                can_bitrate = info.get("can_bitrate")
                if can_driver is not None and node is not None and can_bitrate:
                    from logic.FullCalibration import restart_controller

                    restarted_can, restarted_controller = restart_controller(
                        can=can_driver,
                        mic=self.controller,
                        node=int(node),
                        can_bitrate=int(float(can_bitrate)),
                    )
                    if restarted_can and restarted_controller:
                        info["can"] = restarted_can
                        info["controller"] = restarted_controller
                        self.controller = restarted_controller
                        print("[INFO] Controller restarted after TestCalibration.")
                    else:
                        print("[WARN] Controller restart after TestCalibration did not complete.")
                else:
                    print("[WARN] Missing CAN restart metadata after TestCalibration; using existing controller.")
            except Exception as exc:
                print(f"[WARN] Failed to restart controller after TestCalibration: {exc}")
            try:
                TestCalibration.return_controller_to_zero(self.controller, rpm=rpm)
            except Exception as exc:
                print(f"[WARN] Failed to return controller to zero after TestCalibration: {exc}")
            try:
                self.controller.set_RPM(0)
            except Exception:
                pass
            try:
                self.controller.enabled(False)
            except Exception:
                pass

        return pd.DataFrame(rows, columns=columns)

    def show_current_zero(self):
        rows = []
        zero_spec = self._to_float(self._product_parameter("Zero angle", default=None), default=None)
        tolerance_deg = self._to_float(
            self._product_parameter("Zero angle tolerance", "Zero tolerance", default=None),
            default=ZERO_VISUAL_TOLERANCE_DEG,
        )

        try:
            if zero_spec is None:
                raise RuntimeError("Missing product specification parameter 'Zero angle'.")

            steering_pos = self._move_controller_to_zero(context="show current zero")
            visual_angle = self._read_camera_angle_deg("show current zero")
            visual_error = self._angle_error_deg(visual_angle, zero_spec)
            position_ok = abs(steering_pos) <= ZERO_POSITION_TOLERANCE_COUNTS
            visual_ok = visual_error <= tolerance_deg

            rows.append({
                "Parameters": "Controller zero position",
                "Current Zero": steering_pos,
                "Product Specification": 0,
                "Tolerance": f"+/-{ZERO_POSITION_TOLERANCE_COUNTS} counts",
                "Difference": abs(steering_pos),
                "Match": bool(position_ok),
                "Details": "",
            })
            rows.append({
                "Parameters": "Visual zero angle",
                "Current Zero": round(float(visual_angle), 2),
                "Product Specification": round(float(zero_spec), 2),
                "Tolerance": f"+/-{float(tolerance_deg):.2f} deg",
                "Difference": round(float(visual_error), 2),
                "Match": bool(visual_ok),
                "Details": "",
            })

            print(
                "[RESULT] Show current zero -> "
                f"controller_position={steering_pos} "
                f"visual_angle={visual_angle:.2f} "
                f"target_angle={zero_spec:.2f} "
                f"visual_error={visual_error:.2f} "
                f"visual_tolerance={tolerance_deg:.2f}"
            )

        except Exception as exc:
            rows.append({
                "Parameters": "Show current zero",
                "Current Zero": "",
                "Product Specification": "" if zero_spec is None else zero_spec,
                "Tolerance": f"+/-{float(tolerance_deg):.2f} deg",
                "Difference": "",
                "Match": False,
                "Details": str(exc),
            })
        finally:
            try:
                self.controller.enabled(False)
            except Exception:
                pass

        return pd.DataFrame(
            rows,
            columns=[
                "Parameters",
                "Current Zero",
                "Product Specification",
                "Tolerance",
                "Difference",
                "Match",
                "Details",
            ],
        )
    """
    def check_brake(self):

        if not self.config:
            raise ValueError("Config not available; cannot verify motor part number.")

        expected_part = self.config.get_product_parameter("Motor Part Number", default=None)
        motor_text = str(self.motor_number or "")

        if not expected_part:
            raise ValueError("Missing parameter 'Motor Part Number' in config; cannot verify motor.")
        if not motor_text:
            raise ValueError("Missing motor serial number; cannot verify motor.")

        # Normalize by removing non-alphanumeric characters to allow partial matches.
        expected_clean = "".join(ch for ch in str(expected_part) if ch.isalnum()).upper()
        motor_clean = "".join(ch for ch in motor_text if ch.isalnum()).upper()

        if expected_clean not in motor_clean:
            raise ValueError(f"Wrong Part: expected motor number containing '{expected_part}'.")

        return True
    """
    def activate_relays_for_operation(self, motor_voltage):
        command = 'q1=1,q2=1,q3=1,q6=1'
        if motor_voltage == 48:
            command += ',q7=1'
        if not self.arduino.send_and_confirm_relay_state(command):
            print("[ERROR] Failed to activate relays for operation.")
            return False
        #print("[INFO] Relays successfully activated for operation.")
        return True
    
    # For MiControl
    def motor_test_tr(self, setpoint_list, time_values_list):
        test_data = pd.DataFrame()
        self.controller.set_velocity_mode()
        self.controller.enabled(True)

        total_duration = sum(float(value) for value in time_values_list)
        print(f"[STATUS] Running traction motor feedback test: {len(setpoint_list)} setpoints, about {total_duration:.1f}s.")
        for index, (setpoint, time_value) in enumerate(zip(setpoint_list, time_values_list), start=1):
            if os.getenv("ST_DEBUG"):
                print(f"[DEBUG] Traction setpoint {index}/{len(setpoint_list)}: {setpoint} RPM for {time_value}s")
            data = traction_feedback(self.controller, setpoint, time_value, self.multimeter)
            test_data = pd.concat([test_data, data], ignore_index=True)

        self.controller.enabled(False)
        update_timeteration(0)
        return test_data
    
    # For Elmo
    def motor_test_tr_hc(self, setpoint_list, time_values_list):
        test_data = pd.DataFrame()
        self.controller.set_velocity_mode()
        self.controller.enabled(True)

        total_duration = sum(float(value) for value in time_values_list)
        print(f"[STATUS] Running traction motor feedback test: {len(setpoint_list)} setpoints, about {total_duration:.1f}s.")
        for index, (setpoint, time_value) in enumerate(zip(setpoint_list, time_values_list), start=1):
            if os.getenv("ST_DEBUG"):
                print(f"[DEBUG] Traction setpoint {index}/{len(setpoint_list)}: {setpoint} RPM for {time_value}s")
            data = traction_feedback_hc(self.controller, setpoint, time_value, self.multimeter)
            test_data = pd.concat([test_data, data], ignore_index=True)

        self.controller.enabled(False)
        update_timeteration(0)
        return test_data
    
    def motor_test_st(self, setpoint_list, time_values_list):
        test_data = pd.DataFrame()
        self.controller.set_velocity_mode()
        self.controller.enabled(True)

        total_duration = sum(float(value) for value in time_values_list)
        print(f"[STATUS] Running steering motor feedback test: {len(setpoint_list)} setpoints, about {total_duration:.1f}s.")
        for index, (setpoint, time_value) in enumerate(zip(setpoint_list, time_values_list), start=1):
            if os.getenv("ST_DEBUG"):
                print(f"[DEBUG] Steering motor setpoint {index}/{len(setpoint_list)}: {setpoint} RPM for {time_value}s")
            data = traction_feedback(self.controller, setpoint, time_value, self.multimeter)
            test_data = pd.concat([test_data, data], ignore_index=True)

        self.controller.enabled(False)
        update_timeteration(0)
        return test_data

    @staticmethod
    def _result_table_failed(df):
        if df is None or not hasattr(df, "columns"):
            return True
        if "Match" in df.columns:
            for value in df["Match"].tolist():
                if value is False or str(value).strip().lower() == "false":
                    return True
        if "Result" in df.columns:
            bad_results = {"fail", "error"}
            for value in df["Result"].tolist():
                if str(value).strip().lower() in bad_results:
                    return True
        return False

    def _controller_position_ready_or_raise(self, rpm=ZERO_MOVE_RPM):
        if hasattr(self.controller, "prepare_position_motion"):
            if self.controller.prepare_position_motion(rpm):
                return
            mode = self.controller.get_device_mode() if hasattr(self.controller, "get_device_mode") else None
            error = self.controller.get_error_code() if hasattr(self.controller, "get_error_code") else None
            position = self.controller.get_steering_pos() if hasattr(self.controller, "get_steering_pos") else None
            raise RuntimeError(
                "Controller is not ready for steering position commands: "
                f"mode={mode} error={error} steering_position={position}."
            )

        self.controller.set_position_zero()
        self.controller.enabled(True)
        self.controller.set_device_mode_position()

    def steering_app_test(self, position_list):
        test_data = pd.DataFrame()
        try:
            self._controller_position_ready_or_raise(rpm=1000)

            print(f"[STATUS] Running steering app position test: {len(position_list)} setpoints.")
            for index, position in enumerate(position_list, start=1):
                if os.getenv("ST_DEBUG"):
                    print(f"[DEBUG] Steering app setpoint {index}/{len(position_list)}: {position:.3f} deg")
                data = steering_feedback(self.controller, 1000, position, 0.1)
                test_data = pd.concat([test_data, data], ignore_index=False)

            return test_data
        finally:
            try:
                self.controller.enabled(False)
            except Exception:
                pass
            update_sttimeite(0)

    def collect_general_info(self):
        """Create one 'general' sheet: Parameters | Controller | Specification | Match (bool for 4 keys)."""

        rows, mismatches = [], []  # <-- define before append

        now = datetime.now()
        rows.append({"Parameters": "Test date",       "Controller": now.strftime("%Y-%m-%d"), "Specification": "", "Match": ""})
        rows.append({"Parameters": "Test time",       "Controller": now.strftime("%H:%M:%S"), "Specification": "", "Match": ""})
        who = (self.tester_name or "").strip()
        rows.append({"Parameters": "Test performed by","Controller": who, "Specification": "", "Match": ""})

        # ---- compare only these ----
        compare_keys = ["SW Configuration", "HW Version", "MPU Version Number", "Steering Extended SSI"]
        # ---- append (no compare) ----
        extra_keys   = ["Controller Serial Number", "Motor Serial Number",
                        "Brake Count", "Running Seconds"]

        # -- tiny helpers --
        def get_or(fn, default=None):
            try: return fn()
            except: return default

        def txt(x):  # for display
            return "" if x is None else str(x)

        empty_set = {"", "none", "nan", "null", "false", "0","0.0", "—", "-"}
        def empty(x):
            return ("" if x is None else str(x).strip().lower()) in empty_set

        def simple_match(a, b):
            # treat empty-ish as equal; else numeric equal if possible; else case-insensitive string equal
            if empty(a) and empty(b): return True
            try: return float(a) == float(b)
            except: return str(a).strip().lower() == str(b).strip().lower()

        # -- controller values --
        calls = {
            "SW Configuration":         methodcaller("get_SW_version"),
            "HW Version":               methodcaller("get_HW_version"),
            "MPU Version Number":       methodcaller("get_MPU_version"),
            "Steering Extended SSI":    methodcaller("get_extended_ssi"),
            "Controller Serial Number": methodcaller("get_Serial_number"),
            "Brake Count":              methodcaller("get_Brake_count"),
            "Running Seconds":          methodcaller("get_Running_seconds"),
        }
        ctrl = {k: get_or(lambda c=calls[k]: c(self.controller)) for k in calls}
        ctrl["Motor Serial Number"] = self.motor_number

        # -- specs only for compare_keys --
        params_dict = getattr(self.config, "parameters", {}) or {}
        spec = {k: (params_dict.get(k) if k in params_dict
                    else get_or(lambda k=k: self.config.get_product_parameter(k, default=None)))
                for k in compare_keys}

        # -- rows + mismatches --
        for k in compare_keys:
            cv, sv = ctrl.get(k), spec.get(k)
            m = simple_match(cv, sv)
            rows.append({"Parameters": k, "Controller": txt(cv), "Specification": txt(sv), "Match": bool(m)})
            if not m:
                mismatches.append(f"{k} mismatch: Controller={txt(cv)}, Expected={txt(sv)}")

        for k in extra_keys:
            rows.append({"Parameters": k, "Controller": txt(ctrl.get(k)), "Specification": "", "Match": ""})

        who = (self.tester_name or "").strip()
        rows.append({"Parameters": "Test performed by","Controller": who, "Specification": "", "Match": ""})

        if mismatches:
            error_prompt("Parameter mismatches found:\n  - " + "\n  - ".join(mismatches))

        df = pd.DataFrame(rows, columns=["Parameters", "Controller", "Specification", "Match"])
        return df

    def run_brake_test(self, max_rpm, total_measure_time, brake_activation_time):
        self.controller.set_velocity_mode()
        self.controller.enabled(True)

        self.controller.set_RPM(max_rpm)

        test_data = measure_braking(
            max_rpm, total_measure_time, brake_activation_time, 0.01,
            self.arduino, self.controller, self.multimeter
        )

        # Set RPM to 0 and disable brake
        self.controller.set_RPM(0)
        self.arduino.set_relay_state('q3=1')

        self.controller.enabled(False)

        return test_data


    def run_EOL_test(self, controllers_info, product_parameters):
        """
        Executes EOL testing for multiple controllers (e.g., traction and steering) in one call.

        Parameters:
        - controllers_info: list of dicts, each with keys:
            'controller', 'is_steering', 'setpoint', 'time', 'position'
        - product_parameters: expected parameters for comparison

        This function runs all tests and generates a single combined HTML report.
        """
        plot_sections = []  # Holds plot fragments for final report
        brake_verified = False  # Only verify brake for traction motors
        self.verify_configuration_processes_done()

        for info in controllers_info:
            self.controller = info["controller"]  # Switch controller context
            label = "steering" if info["is_steering"] else "traction"
            controller_firmware = str(info.get("controller_firmware"))
            
            if "MiControlF37" in controller_firmware or "MiControlF35" in controller_firmware:  
                # --- STEP 1: Device metadata and config checks ---
                results = safe_execute(
                self.collect_general_info,
                spinner_text=f"Reading {label} parameters"
            )

                self.config.save_results_to_excel(results, f"general_{label}")

            # --- STEP 2: Run specific tests based on controller role ---
            if info["is_steering"]:
                # Steering calibration quality check before app/position testing.
                calibration_results = self.test_calibration(info, product_parameters)
                self.config.save_results_to_excel(calibration_results, "calibration")
                if self._result_table_failed(calibration_results):
                    raise RuntimeError(
                        "Steering EOL stopped because calibration quality failed. "
                        "See the 'calibration' sheet and test_calibration_report files; "
                        "position and motor tests were not run."
                    )

                # Steering APP test: position control feedback
                app_results = self.steering_app_test(info["position"])
                self.config.save_results_to_excel(app_results, "steering_app")

                # Steering motor test: velocity control
                motor_results = self.motor_test_st(info["setpoint"], info["time"])
                self.config.save_results_to_excel(motor_results, "steering_test")

                # Verify the stored current zero against the product zero angle.
                zero_results = self.show_current_zero()
                self.config.save_results_to_excel(zero_results, "zero")
                zero_failed = (
                    "Match" in zero_results.columns
                    and any(value is False or str(value).strip().lower() == "false" for value in zero_results["Match"].tolist())
                )
                if zero_failed:
                    error_prompt(
                        "Current zero does not match product specification. "
                        "See the 'zero' sheet for measured values and tolerance."
                    )

            else:
                # Traction motor: verify brake/motor pairing once.
                #if not brake_verified:
                #    self.check_brake()
                #    brake_verified = True

                if "Elmo" in controller_firmware:
                    # Traction motor test for Elmo
                    motor_results = self.motor_test_tr_hc(info["setpoint"], info["time"])
                    self.config.save_results_to_excel(motor_results, "traction_test")
                else:
                    # Traction motor test for MiControl
                    motor_results = self.motor_test_tr(info["setpoint"], info["time"])
                    self.config.save_results_to_excel(motor_results, "traction_test")
                    
                # Brake test – forward
                brake_fwd = self.run_brake_test(1700, 5, 2)
                self.config.save_results_to_excel(brake_fwd, "brake_test_forward")
                time.sleep(1)
                # Brake test – backward
                brake_bwd = self.run_brake_test(-1700, 5, 2)
                self.config.save_results_to_excel(brake_bwd, "brake_test_backward")

        # --- STEP 3: Final report ---
        metadata = self.config.get_metadata(self.dp)
    
        plot_sections = []
        # Combined motor & steering app sections from Excel
        plot_sections.extend(self.config.extract_motor_combined_feedback(self.dp, self.pg))
        # Brake sections from Excel
        torque = self.config.get_product_parameter("Nominal Brake Torque", default=11)
        plot_sections.extend(self.config.extract_brake_feedback(self.dp, self.pg, brake_torque=torque))

        self.config.render_tabs_html(self.unit_serial_number, plot_sections, metadata)
        eol_ok = self.config.rename_status_to_done_if_eol_ok()
        if eol_ok:
            print("[RESULT] eol_status ok=True")
        else:
            print("[RESULT] eol_status ok=False")
        return eol_ok
