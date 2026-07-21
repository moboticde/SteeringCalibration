from __future__ import annotations

import re
import types
from pathlib import Path

from drivers import driver_QRreader
from io_helpers import find_product_folder
from main import CalibrationGUI as gui


def _write_product_files(product_dir: Path) -> None:
    gui.write_conf_xlsx_rows(
        product_dir / "ProductSpecifications_V2.xlsx",
        [
            ["CAN Baudrate", 125],
            ["Steering Node ID", 59],
            ["Steering Controller Type", "MiControl F35"],
            ["Zero angle", 270],
        ],
    )
    script_dir = product_dir / "01_SwConfiguration"
    script_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "SteeringScript.py").write_text("# test steering script\n", encoding="utf-8")


def test_resolve_product_family_dir_uses_top_level_product_folder(tmp_path):
    family_dir = tmp_path / "SO-1000"
    unit_dir = family_dir / "SO-1000-284"
    unit_dir.mkdir(parents=True)

    assert gui.resolve_product_family_dir("SO-1000-284", unit_dir, tmp_path) == family_dir


def test_find_product_family_folder_checks_01_products_roots(tmp_path, monkeypatch):
    manufacturing_root = tmp_path / "Manufacturing"
    family_dir = manufacturing_root / "01_Products" / "SO-1000"
    family_dir.mkdir(parents=True)
    monkeypatch.setattr(gui, "MANUFACTURING_ROOT", manufacturing_root)

    result = gui.find_product_family_folder_from_roots(
        "SO-1000-284",
        {"paths": {"product_base": str(tmp_path / "wrong-root")}},
    )

    assert result == family_dir.resolve()


def test_scanned_unit_uses_family_paths_for_specs_script_and_results(tmp_path, monkeypatch):
    gui.STATE.current_product_context = None
    gui.STATE.product_scan_completed = False
    family_dir = tmp_path / "SO-1000"
    unit_dir = family_dir / "SO-1000-284"
    unit_dir.mkdir(parents=True)
    _write_product_files(family_dir)

    monkeypatch.setattr(driver_QRreader, "run_qr_reader", lambda **_kwargs: "SO-1000-284")
    monkeypatch.setattr(find_product_folder, "find_config", lambda _qr_code: str(unit_dir))
    monkeypatch.setattr(
        find_product_folder,
        "config",
        {"paths": {"product_base": str(tmp_path)}},
    )

    context = gui.resolve_product_context()

    assert context.qr_code == "SO-1000-284"
    assert context.product_dir == family_dir.resolve()
    assert context.script_path == family_dir.resolve() / "01_SwConfiguration" / "SteeringScript.py"
    assert gui.find_product_spec_path(context.product_dir) == family_dir.resolve() / "ProductSpecifications_V2.xlsx"

    report = gui.RunAllReport(
        product_dir=context.product_dir,
        qr_code=context.qr_code,
        node=context.steering_node_id,
        desired_angle=context.zero_angle,
    )

    assert report.path == family_dir.resolve() / "04_Results" / "SO-1000-284_status.xlsx"
    assert report.path.is_file()


def test_cached_product_context_reuses_qr_scan_buffer(tmp_path, monkeypatch):
    family_dir = tmp_path / "SO-1000"
    _write_product_files(family_dir)
    context = gui.ProductContext(
        qr_code="SO-1000-284",
        product_dir=family_dir,
        can_bitrate=125,
        steering_node_id=59,
        zero_angle=270.0,
        script_path=family_dir / "01_SwConfiguration" / "SteeringScript.py",
    )
    gui.STATE.set_product_scan_result(
        gui.ProductSpecCache(
            qr_code=context.qr_code,
            product_dir=context.product_dir,
            spec_path=family_dir / "ProductSpecifications_V2.xlsx",
            params={"Steering Node ID": 59, "Steering Controller Type": "MiControl F35"},
            context=context,
            steering_available=True,
            message="cached",
        )
    )
    monkeypatch.setattr(
        driver_QRreader,
        "run_qr_reader",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("QR reader called again")),
    )

    assert gui.get_cached_or_scan_product_context() == context


def test_non_steering_product_spec_disables_steering(tmp_path, monkeypatch):
    family_dir = tmp_path / "SO-1000"
    unit_dir = family_dir / "SO-1000-284"
    unit_dir.mkdir(parents=True)
    gui.write_conf_xlsx_rows(
        family_dir / "ProductSpecifications_V2.xlsx",
        [
            ["CAN Baudrate", 125],
            ["Traction Node ID", 12],
            ["Traction Controller Type", "Traction"],
        ],
    )

    monkeypatch.setattr(driver_QRreader, "run_qr_reader", lambda **_kwargs: "SO-1000-284")
    monkeypatch.setattr(find_product_folder, "find_config", lambda _qr_code: str(unit_dir))
    monkeypatch.setattr(
        find_product_folder,
        "config",
        {"paths": {"product_base": str(tmp_path)}},
    )

    result = gui.scan_product_context()

    assert result.context is None
    assert result.steering_available is False
    assert "Steering tab disabled" in result.message


def test_default_can_check_tries_standard_and_spec_nodes_before_failure(monkeypatch):
    context = gui.ProductContext(
        qr_code="SO-1000-284",
        product_dir=Path("/tmp/SO-1000"),
        can_bitrate=250,
        steering_node_id=42,
        zero_angle=270.0,
        script_path=Path("/tmp/SO-1000/01_SwConfiguration/SteeringScript.py"),
    )
    calls = []
    monkeypatch.setattr(gui, "get_cached_or_scan_product_context", lambda: context)

    def fake_check(node, **kwargs):
        calls.append((node, kwargs["can_bitrate"]))
        return False, f"missing {node}"

    monkeypatch.setattr(gui, "check_can_connection", fake_check)

    connected, node, bitrate, message, result_context = gui.check_standard_then_product_can_connection()

    assert connected is False
    assert (node, bitrate, result_context) == (42, 250, context)
    assert calls == [(59, 125), (42, 250)]
    assert "missing 59" in message
    assert "missing 42" in message


def test_workflow_tabs_contain_expected_task_buttons():
    def panel(name: str) -> str:
        match = re.search(
            rf'<section class="workflow-panel[^"]*" data-workflow-panel="{name}">(.*?)</section>',
            gui.HTML,
            re.S,
        )
        assert match is not None
        return match.group(1)

    steering_panel = panel("steering")
    traction_panel = panel("traction")
    eol_panel = panel("eol")
    rail_match = re.search(r'<aside class="ux-panel ux-rail">(.*?)</aside>', gui.HTML, re.S)
    assert rail_match is not None
    workflow_rail = rail_match.group(1)

    for task in (
        "run_all",
        "load_script_config",
        "start_zeroing",
        "start_calibration",
        "test_calibration",
        "show_current_zero",
    ):
        assert f'data-task="{task}"' in steering_panel

    assert 'data-task="traction_calibration"' in traction_panel
    assert 'data-task="run_eol"' in eol_panel
    assert 'id="eol-last-report"' in workflow_rail
    assert 'id="eol-last-report"' not in eol_panel
    assert 'data-task="run_eol"' not in steering_panel
    assert "steering_available" in gui.HTML
    assert "This product specification has no steering information." in gui.HTML
    assert 'id="scan-option"' in gui.HTML
    assert 'value="qr_camera"' in gui.HTML
    assert 'value="qr_scanner"' in gui.HTML
    assert 'value="barcode_scanner"' in gui.HTML
    assert 'value="manual"' in gui.HTML
    assert "/scan-product" in gui.HTML
    assert "/scan-option" in gui.HTML
    assert "/eol-report" in gui.HTML
    assert "eol_report_name" in gui.HTML
    assert "conf_workflow_status" in gui.HTML
    assert "connects-next" in gui.HTML
    assert 'data-step="test_calibration"' in gui.HTML
    assert "<h2>Test Calibration</h2>" in gui.HTML
    assert 'data-step="show_current_zero"' in gui.HTML
    assert "<h2>Show Current Zero</h2>" in gui.HTML


def test_run_all_report_adds_date_and_preserves_legacy_rows(tmp_path):
    product_dir = tmp_path / "SO-1000"
    status_path = product_dir / "04_Results" / "SO-1000-284_status.xlsx"
    gui.write_conf_xlsx_rows(
        status_path,
        [
            list(gui.LEGACY_RUN_ALL_REPORT_COLUMNS),
            ["SN123", "OK", "OK", "-"],
        ],
    )

    report = gui.RunAllReport(
        product_dir=product_dir,
        qr_code="SO-1000-284",
        node=59,
        desired_angle=270.0,
    )

    rows = gui.read_conf_xlsx_rows(report.path)
    assert rows[0] == list(gui.RUN_ALL_REPORT_COLUMNS)
    assert rows[1] == ["", "SN123", "OK", "OK", "-"]
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", rows[2][0])


def test_read_conf_xlsx_rows_ignores_transient_invalid_workbook(tmp_path, capsys):
    status_path = tmp_path / "SO-1000-284_status.xlsx"
    status_path.write_text("workbook is being replaced", encoding="utf-8")

    assert gui.read_conf_xlsx_rows(status_path) == []
    assert "Could not read existing result workbook" not in capsys.readouterr().out


def test_eol_sequence_accepts_required_steps_across_rows_in_order():
    rows = [
        list(gui.RUN_ALL_REPORT_COLUMNS),
        ["2026-07-10 10:00:00", "SN123", "OK", "-", "-"],
        ["2026-07-10 11:00:00", "SN123", "-", "OK", "-"],
        ["2026-07-10 12:00:00", "SN123", "-", "-", "OK"],
    ]

    ok, message = gui.eol_sequence_status_from_rows(rows)
    status = gui.conf_workflow_status_from_rows(rows)

    assert ok is True
    assert "EOL enabled" in message
    assert status["load_script_config"]["state"] == "pass"
    assert status["start_zeroing"]["state"] == "pass"
    assert status["start_calibration"]["state"] == "pass"
    assert status["start_calibration"]["time"] == "2026-07-10 12:00:00"


def test_eol_done_workbook_is_reported_as_last_report(tmp_path):
    product_dir = tmp_path / "SO-1000"
    done_path = gui.done_workbook_path_for_qr(product_dir, "SO-1000-284")
    gui.write_conf_xlsx_rows(done_path, [["done"], ["ok"]])

    ok, message, path = gui.eol_sequence_status_for_product(product_dir, "SO-1000-284")

    assert ok is True
    assert done_path.name == "SO-1000-284_done.xlsx"
    assert done_path.name in message
    assert path == str(done_path)
    assert gui.eol_done_report_for_product(product_dir, "SO-1000-284") == done_path


def test_eol_sequence_rejects_calibration_before_zero_without_later_calibration():
    rows = [
        list(gui.RUN_ALL_REPORT_COLUMNS),
        ["2026-07-10 10:00:00", "SN123", "OK", "-", "-"],
        ["2026-07-10 11:00:00", "SN123", "-", "-", "OK"],
        ["2026-07-10 12:00:00", "SN123", "-", "OK", "-"],
    ]

    ok, message = gui.eol_sequence_status_from_rows(rows)

    assert ok is False
    assert "Calibration" in message


def test_traction_calibration_script_selection_uses_dd_numbers_only():
    assert gui.choose_traction_calibration_script("motor BL167/25_SB extra").name == "ST_Calibration.py"
    assert gui.choose_traction_calibration_script("1126788").name == "DD_Calibration.py"
    assert gui.choose_traction_calibration_script("part bl167/25").name == "ST_Calibration.py"
    assert gui.choose_traction_calibration_script("1058534").name == "DD_Calibration.py"
    assert gui.choose_traction_calibration_script("unknown motor").name == "ST_Calibration.py"
    assert gui.choose_traction_calibration_program("1126788") == "DD"
    assert gui.choose_traction_calibration_program("unknown motor") == "ST"


def test_run_eol_defaults_qr_camera_so_product_and_motor_zero(monkeypatch):
    captured: dict[str, object] = {}
    original_barcode = gui.STATE.current_barcode
    original_scan_option = gui.STATE.scan_option
    try:
        gui.STATE.current_barcode = "SO-1000-284"
        gui.STATE.scan_option = gui.SCAN_OPTION_QR_CAMERA

        def fake_run_mobotic_eol(**kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(gui, "run_mobotic_eol", fake_run_mobotic_eol)

        assert gui.run_task("run_eol", {"tester_name": "Tester"}) is True
    finally:
        gui.STATE.current_barcode = original_barcode
        gui.STATE.scan_option = original_scan_option

    assert captured["unit_serial_number"] == "SO-1000-284"
    assert captured["motor_number"] == "0"
    assert captured["tester_name"] == "Tester"


def test_so_eol_wrapper_runs_test_calibration_then_restores_ssi_and_clears_errors(monkeypatch):
    calls: list[object] = []

    class FakeController:
        def SSI_encoder(self, enabled):
            calls.append(("ssi", enabled))
            return True

        def clear_errors(self):
            calls.append("clear_errors")

    class FakeTestRunner:
        def test_calibration(self, _info, _product_parameters):
            calls.append("original_test_calibration")
            self.controller = FakeController()
            return "original-result"

        def _controller_position_ready_or_raise(self, rpm=1000):
            calls.append(("position_ready", rpm))

    fake_test_manager = types.SimpleNamespace(
        TestRunner=FakeTestRunner,
    )
    fake_managers = types.SimpleNamespace(test_manager=fake_test_manager)

    def fake_import(name, *args, **kwargs):
        if name == "managers":
            return fake_managers
        if name == "managers.test_manager":
            return fake_test_manager
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr(gui, "_external_eol_import_scope", lambda: gui.contextlib.nullcontext())
    monkeypatch.setattr(gui, "_patch_eol_product_family_resolution", lambda: None)
    monkeypatch.setattr("builtins.__import__", fake_import)

    def fake_load_eol_case_module():
        return types.SimpleNamespace(
            main=lambda **_kwargs: fake_test_manager.TestRunner().test_calibration({}, {})
        )

    monkeypatch.setattr(gui, "_load_eol_case_module", fake_load_eol_case_module)

    result = gui._run_eol_case_program(
        tester_name="Tester",
        unit_serial_number="SO-1000-284",
        motor_number="0",
    )

    assert result == "original-result"
    assert calls == [
        "original_test_calibration",
        ("ssi", True),
        "clear_errors",
        "clear_errors",
    ]


def test_so_eol_wrapper_zero_returns_only_after_pass_and_relay_restart(monkeypatch):
    calls: list[object] = []

    class FakeController:
        def __init__(self, name="controller"):
            self.name = name
            self.added_node = object()

        def restore_extended_ssi_mode(self):
            calls.append(("restore_frame", self.name))

        def SSI_encoder(self, enabled):
            calls.append(("ssi", self.name, enabled))
            return True

        def clear_errors(self):
            calls.append(("clear_errors", self.name))

        def get_ssi_encoder_status(self):
            return 9

        def get_error_code(self):
            return 0

        def get_steering_pos(self):
            return 0

    class FakeExistingCan:
        def close_can(self):
            calls.append("close_existing_can")

    class FakeCan:
        def __init__(self, can_bitrate):
            calls.append(("new_can", can_bitrate))
            self.can_network = object()

    class FakeMicontrol:
        def __init__(self, can, node):
            calls.append(("new_controller", node))
            self.name = "reconnected"
            self.added_node = object()

        def restore_extended_ssi_mode(self):
            calls.append(("restore_frame", self.name))

        def SSI_encoder(self, enabled):
            calls.append(("ssi", self.name, enabled))
            return True

        def clear_errors(self):
            calls.append(("clear_errors", self.name))

        def get_ssi_encoder_status(self):
            return 9

        def get_error_code(self):
            return 0

        def get_steering_pos(self):
            return 0

    class FakeArduino:
        def _set_relays_bits(self, mask):
            calls.append(("relay", mask))
            return True

    fake_test_calibration = types.SimpleNamespace()

    def fake_return_controller_to_zero(controller, rpm=1000):
        calls.append(("zero_return", getattr(controller, "name", "?"), rpm))

    fake_test_calibration.return_controller_to_zero = fake_return_controller_to_zero

    class FakeTestRunner:
        def __init__(self):
            self.arduino = FakeArduino()
            self.controller = FakeController("initial")

        def test_calibration(self, _info, _product_parameters):
            calls.append("original_test_calibration")
            fake_test_calibration.return_controller_to_zero(self.controller, rpm=777)
            return types.SimpleNamespace(columns=["Match"])

        @staticmethod
        def _result_table_failed(_result):
            return False

        def _controller_position_ready_or_raise(self, rpm=1000):
            calls.append(("position_ready", rpm))

    fake_test_manager = types.SimpleNamespace(TestRunner=FakeTestRunner)
    fake_managers = types.SimpleNamespace(test_manager=fake_test_manager)
    fake_full_calibration = types.SimpleNamespace(restart_controller=lambda *_args, **_kwargs: None)
    fake_driver_can = types.SimpleNamespace(DriverCan=FakeCan)
    fake_driver_micontrol = types.SimpleNamespace(MicontrolF35_CAN=FakeMicontrol)

    def fake_import(name, *args, **kwargs):
        if name == "managers":
            return fake_managers
        if name == "managers.test_manager":
            return fake_test_manager
        return original_import(name, *args, **kwargs)

    def fake_import_module(name, *args, **kwargs):
        if name == "logic.FullCalibration":
            return fake_full_calibration
        if name == "tests.TestCalibration":
            return fake_test_calibration
        if name == "drivers.driver_can":
            return fake_driver_can
        if name == "drivers.driver_miControlF35":
            return fake_driver_micontrol
        return original_import_module(name, *args, **kwargs)

    original_import = __import__
    original_import_module = gui.importlib.import_module
    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr(gui.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(gui.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))

    gui._patch_eol_so_test_calibration_restore("SO-1000-284", "0")

    runner = fake_test_manager.TestRunner()
    info = {"can": FakeExistingCan(), "node": 50, "can_bitrate": 125, "controller": runner.controller}
    result = runner.test_calibration(info, {})

    assert result.columns == ["Match"]
    assert info["controller"].name == "reconnected"
    assert calls.index(("relay", 0)) < calls.index(("relay", gui.controller_power_relay_mask()))
    assert calls.index(("relay", gui.controller_power_relay_mask())) < calls.index(("zero_return", "reconnected", 777))
    assert calls.index(("zero_return", "reconnected", 777)) < calls.index(("sleep", 2.0))
    assert ("zero_return", "initial", 777) not in calls


def test_load_test_calibration_module_prefers_tests_package(monkeypatch):
    calls: list[str] = []
    fake_module = types.SimpleNamespace(main=lambda **_kwargs: True)

    def fake_import_module(name):
        calls.append(name)
        if name == "tests.TestCalibration":
            return fake_module
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr(gui.importlib, "import_module", fake_import_module)

    assert gui.load_test_calibration_module() is fake_module
    assert calls == ["tests.TestCalibration"]


def test_run_task_test_calibration_uses_package_module_and_restores_controller(monkeypatch):
    context = gui.ProductContext(
        qr_code="SO-1000-284",
        product_dir=Path("/tmp/SO-1000"),
        can_bitrate=250,
        steering_node_id=42,
        zero_angle=270.0,
        script_path=Path("/tmp/SO-1000/01_SwConfiguration/SteeringScript.py"),
    )
    calls: list[object] = []

    def fake_main(**kwargs):
        calls.append(("main", kwargs["can_bitrate"], kwargs["node"]))
        return True

    monkeypatch.setattr(gui, "get_cached_or_scan_product_context", lambda: context)
    monkeypatch.setattr(gui, "ensure_controller_ready_for_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gui,
        "load_test_calibration_module",
        lambda: types.SimpleNamespace(main=fake_main),
    )
    monkeypatch.setattr(
        gui,
        "wait_for_power_cycle_after_test_calibration",
        lambda _power_cycle_wait_fn: calls.append("power_cycle"),
    )
    monkeypatch.setattr(
        gui,
        "restore_standalone_test_calibration_controller",
        lambda **kwargs: calls.append(("restore", kwargs["can_bitrate"], kwargs["node"])),
    )

    assert gui.run_task("test_calibration") is True
    assert calls == [
        ("main", 250, 42),
        "power_cycle",
        ("restore", 250, 42),
    ]


def test_test_calibration_zero_return_restores_ssi_and_prepares_motion(monkeypatch):
    from tests import TestCalibration

    calls: list[object] = []
    positions = iter([12, 12, 0, 0])

    class FakeController:
        def get_steering_pos(self):
            calls.append("get_pos")
            return next(positions)

        def restore_extended_ssi_mode(self):
            calls.append("restore_ssi_frame")
            return True

        def clear_errors(self):
            calls.append("clear_errors")

        def SSI_encoder(self, enabled):
            calls.append(("ssi", enabled))
            return True

        def get_ssi_encoder_status(self):
            return 9

        def get_ssi_direct_position(self):
            return 0

        def prepare_position_motion(self, rpm):
            calls.append(("prepare_position_motion", rpm))
            return True

        def set_steering_pos(self, value):
            calls.append(("set_steering_pos", value))

    monkeypatch.setattr(TestCalibration.time, "sleep", lambda _seconds: None)

    TestCalibration.return_controller_to_zero(FakeController(), rpm=1000)

    assert calls[:5] == [
        "get_pos",
        "restore_ssi_frame",
        "clear_errors",
        "clear_errors",
        ("ssi", True),
    ]
    assert ("prepare_position_motion", 1000) in calls
    assert calls.index(("prepare_position_motion", 1000)) < calls.index(("set_steering_pos", 0))


def test_parse_attempt_9_calibration_zero_passes_only_when_offsets_are_zero():
    output = """
Running Calibration Attempt 8...
SinOff: 1 | CosOff: 0 | GainC: 0 | Harm4: 0 | RPM: 100
Running Calibration Attempt 9...
SinOff: 0 | CosOff: 0 | GainC: 0 | Harm4: 0 | RPM: 100
"""

    ok, params = gui.parse_attempt_9_calibration_zero(output)

    assert ok is True
    assert params == {"SinOff": 0, "CosOff": 0, "GainC": 0, "Harm4": 0, "RPM": 100}


def test_parse_attempt_9_calibration_zero_fails_for_nonzero_or_missing_attempt():
    nonzero_output = """
Running Calibration Attempt 9...
SinOff: 0 | CosOff: -1 | GainC: 0 | Harm4: 0 | RPM: 100
"""
    missing_output = """
Running Calibration Attempt 8...
SinOff: 0 | CosOff: 0 | GainC: 0 | Harm4: 0 | RPM: 100
"""

    assert gui.parse_attempt_9_calibration_zero(nonzero_output)[0] is False
    assert gui.parse_attempt_9_calibration_zero(missing_output) == (False, None)


def test_append_traction_calibration_log_creates_and_appends_rows(tmp_path):
    workbook = tmp_path / "Calibration.xlsx"

    gui.append_traction_calibration_log(
        workbook_path=workbook,
        calibration_date="2026-07-09 12:00:00",
        barcode="MOTOR-1",
        program="ST",
        status="FAIL",
    )
    gui.append_traction_calibration_log(
        workbook_path=workbook,
        calibration_date="2026-07-09 12:05:00",
        barcode="1126788",
        program="DD",
        status="PASS",
    )

    assert gui.read_conf_xlsx_rows(workbook) == [
        list(gui.TRACTION_CALIBRATION_COLUMNS),
        ["2026-07-09 12:00:00", "MOTOR-1", "ST", "FAIL"],
        ["2026-07-09 12:05:00", "1126788", "DD", "PASS"],
    ]


def test_run_traction_calibration_logs_fail_on_subprocess_error(tmp_path, monkeypatch):
    calibration_root = tmp_path / "TrCalibration"
    calibration_root.mkdir()
    (calibration_root / "DD_Calibration.py").write_text("# fake\n", encoding="utf-8")
    workbook = tmp_path / "Calibration.xlsx"

    class Completed:
        returncode = 2
        stdout = """
Running Calibration Attempt 9...
SinOff: 0 | CosOff: 0 | GainC: 0 | Harm4: 0 | RPM: 100
"""
        stderr = "failed\n"

    monkeypatch.setattr(gui, "TRACTION_CALIBRATION_ROOT", calibration_root)
    monkeypatch.setattr(gui, "TRACTION_CALIBRATION_WORKBOOK", workbook)
    monkeypatch.setattr(gui.subprocess, "run", lambda *_args, **_kwargs: Completed())

    assert gui.run_traction_calibration("1126788") is False
    assert gui.read_conf_xlsx_rows(workbook)[1] == [
        gui.read_conf_xlsx_rows(workbook)[1][0],
        "1126788",
        "DD",
        "FAIL",
    ]


def test_scan_option_parser_accepts_known_options():
    assert gui.parse_scan_option("qr_camera") == "qr_camera"
    assert gui.parse_scan_option("qr_scanner") == "qr_scanner"
    assert gui.parse_scan_option("barcode_scanner") == "barcode_scanner"
    assert gui.parse_scan_option("manual") == "manual"


def test_changing_scan_option_resets_cached_scan_and_prompts_again():
    state = gui.STATE
    original_values = {
        "scan_option": state.scan_option,
        "relay_connection_ok": state.relay_connection_ok,
        "product_scan_running": state.product_scan_running,
        "product_scan_completed": state.product_scan_completed,
        "awaiting_product_scan": state.awaiting_product_scan,
        "product_scan_message": state.product_scan_message,
        "steering_available": state.steering_available,
        "current_product_context": state.current_product_context,
        "current_product_params": state.current_product_params,
        "current_product_spec_path": state.current_product_spec_path,
        "current_product_dir": state.current_product_dir,
        "current_barcode": state.current_barcode,
        "current_report": state.current_report,
    }
    try:
        state.scan_option = "qr_camera"
        state.relay_connection_ok = True
        state.product_scan_running = False
        state.product_scan_completed = True
        state.awaiting_product_scan = False
        state.steering_available = True
        state.current_barcode = "SO-1000-284"
        state.current_product_params = {"Steering Node ID": 50}

        state.set_scan_option("manual")

        assert state.scan_option == "manual"
        assert state.product_scan_completed is False
        assert state.awaiting_product_scan is True
        assert state.steering_available is None
        assert state.current_barcode == ""
        assert state.current_product_params == {}
    finally:
        for key, value in original_values.items():
            setattr(state, key, value)
