from __future__ import annotations

import ctypes
import importlib.util
from pathlib import Path
import sys
import types
import unittest


class _FakeMuFunction:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *args, **kwargs):
        return 0


class _FakeMuLibrary:
    def __getattr__(self, name: str) -> _FakeMuFunction:
        fn = _FakeMuFunction()
        setattr(self, name, fn)
        return fn


def _load_full_calibration_with_fake_hardware():
    original_cdll = ctypes.CDLL
    stub_names = (
        "drivers.driver_arduino",
        "drivers.driver_can",
        "drivers.driver_cam_st",
        "drivers.driver_mc",
        "drivers.driver_miControlF35",
        "drivers.driver_owon",
        "logic.FlashSteeringScript",
        "utils.config_processing",
        "utils.interrupt_guard",
    )
    original_modules = {name: sys.modules.get(name) for name in stub_names}
    ctypes.CDLL = lambda *_args, **_kwargs: _FakeMuLibrary()
    try:
        driver_arduino = types.ModuleType("drivers.driver_arduino")
        driver_arduino.DriverArduino = type("DriverArduino", (), {})
        sys.modules["drivers.driver_arduino"] = driver_arduino

        driver_can = types.ModuleType("drivers.driver_can")
        driver_can.DriverCan = type("DriverCan", (), {})
        sys.modules["drivers.driver_can"] = driver_can

        driver_cam_st = types.ModuleType("drivers.driver_cam_st")
        driver_cam_st.AngleDetection = type("AngleDetection", (), {})
        sys.modules["drivers.driver_cam_st"] = driver_cam_st

        driver_mc = types.ModuleType("drivers.driver_mc")
        driver_mc.DSACompat = type("DSACompat", (), {})
        sys.modules["drivers.driver_mc"] = driver_mc

        driver_micontrol = types.ModuleType("drivers.driver_miControlF35")
        driver_micontrol.MicontrolF35_CAN = type("MicontrolF35_CAN", (), {})
        sys.modules["drivers.driver_miControlF35"] = driver_micontrol

        driver_owon = types.ModuleType("drivers.driver_owon")
        driver_owon.power_cycle_owon_spe6053 = lambda **_kwargs: False
        sys.modules["drivers.driver_owon"] = driver_owon

        steering_script = types.ModuleType("logic.FlashSteeringScript")
        steering_script.import_script_via_qr = lambda: None
        steering_script.load_config_function = lambda _path: (None, None, 0)
        sys.modules["logic.FlashSteeringScript"] = steering_script

        config_processing = types.ModuleType("utils.config_processing")
        config_processing.nmt_reset_node_compat = lambda _nmt: None
        sys.modules["utils.config_processing"] = config_processing

        interrupt_guard = types.ModuleType("utils.interrupt_guard")
        interrupt_guard.install_deferred_keyboard_interrupt = lambda **_kwargs: (lambda: None)
        sys.modules["utils.interrupt_guard"] = interrupt_guard

        module_path = Path(__file__).resolve().parents[1] / "logic" / "FullCalibration.py"
        spec = importlib.util.spec_from_file_location(
            "FullCalibration_test_import",
            module_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load FullCalibration.py for tests.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        ctypes.CDLL = original_cdll
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


fc = _load_full_calibration_with_fake_hardware()


class FullCalibrationProtectionTests(unittest.TestCase):
    def test_zero_related_params_are_protected_during_calibration(self):
        protected = {name for _idx, name in fc.PROTECTED_MU_PARAMS}
        monitored = {name for _idx, name in fc.MONITORED_DERIVED_ZERO_PARAMS}

        self.assertIn("OFF_ABZ", protected)
        self.assertIn("OFF_UVW", protected)
        self.assertIn("PRES_POS", protected)
        self.assertIn("OFF_POS", monitored)
        self.assertIn("OFF_COM", monitored)

    def test_restore_writes_every_protected_param(self):
        calls: list[tuple[int, int, int, int]] = []

        def fake_set_param(_handle, index, high, low, flag):
            calls.append((
                int(index.value),
                int(high.value),
                int(low.value),
                int(flag.value),
            ))
            return fc.MU_OK

        fc.mu.MU_SetParam = fake_set_param
        params = {
            index: fc.ProtectedMuParam(index=index, name=name, high=index + 1, low=index + 2)
            for index, name in fc.PROTECTED_MU_PARAMS
        }
        state = fc.ProtectedZeroState(
            params=params,
            derived_params={},
            real_pres_pos_high=0x11111111,
            real_pres_pos_low=0x22222222,
        )

        self.assertTrue(fc._restore_protected_params(fc.MU_Handle(), state, "unit test"))

        restored_indexes = [index for index, _high, _low, _flag in calls]
        self.assertEqual(restored_indexes, [index for index, _name in fc.PROTECTED_MU_PARAMS])
        self.assertTrue(all(flag == fc.MU_VERIFY.value for _idx, _high, _low, flag in calls))

    def test_return_to_existing_zero_moves_without_saving_zero(self):
        class FakeController:
            def __init__(self) -> None:
                self.position = 42
                self.commands: list[tuple[str, int | bool]] = []
                self.zero_saved = False

            def clear_errors(self):
                pass

            def SSI_encoder(self, enable=True):
                self.commands.append(("ssi", bool(enable)))
                return True

            def get_steering_pos(self):
                return self.position

            def get_ssi_direct_position(self):
                return 123

            def get_ssi_encoder_status(self):
                return 9

            def set_device_mode_position(self):
                self.commands.append(("mode_position", 1))

            def set_RPM(self, rpm):
                self.commands.append(("rpm", int(rpm)))

            def set_steering_RPM(self, rpm):
                self.commands.append(("steering_rpm", int(rpm)))

            def enabled(self, status):
                self.commands.append(("enabled", bool(status)))

            def set_steering_pos(self, position):
                self.commands.append(("position", int(position)))
                self.position = int(position)

            def save_ssi_absolute_zero(self):
                self.zero_saved = True
                return True

        original_sleep = fc.time.sleep
        fc.time.sleep = lambda _seconds: None
        try:
            mic = FakeController()
            fc.return_controller_to_existing_zero(mic)
        finally:
            fc.time.sleep = original_sleep

        self.assertEqual(mic.position, 0)
        self.assertIn(("position", 0), mic.commands)
        self.assertFalse(mic.zero_saved)

    def test_final_eeprom_store_rebuilds_derived_offsets_before_write_all(self):
        calls: list[tuple[str, int | None]] = []

        original_set_param = fc.mu.MU_SetParam
        original_write_cmd = fc.mu.MU_WriteCmdRegister
        try:
            def fake_write_cmd(_handle, command):
                calls.append(("cmd", int(command.value)))
                return fc.MU_OK

            def fake_set_param(_handle, index, _high, low, flag):
                calls.append(("set_param", int(index.value)))
                self.assertEqual(int(low.value), fc.MU_SSI.value)
                self.assertEqual(int(flag.value), fc.MU_WRITE.value)
                return fc.MU_OK

            fc.mu.MU_WriteCmdRegister = fake_write_cmd
            fc.mu.MU_SetParam = fake_set_param

            self.assertTrue(
                fc._store_to_eeprom_and_set_mode(fc.MU_Handle(), fc.MU_SSI, None)
            )
        finally:
            fc.mu.MU_SetParam = original_set_param
            fc.mu.MU_WriteCmdRegister = original_write_cmd

        self.assertEqual(
            calls,
            [
                ("cmd", fc.MU_CMD_CRC_CALC.value),
                ("cmd", fc.MU_CMD_ABS_RESET.value),
                ("cmd", fc.MU_CMD_WRITE_ALL.value),
                ("set_param", fc.MU_MODEA.value),
                ("cmd", fc.MU_CMD_WRITE_ALL.value),
            ],
        )

    def test_encoder_side_zero_compensation_restores_off_pos(self):
        calls: list[tuple[str, int, int, int]] = []

        def param(index, name, low, high=0):
            return fc.ProtectedMuParam(index=index, name=name, high=high, low=low)

        baseline = fc.ProtectedZeroState(
            params={
                fc.MU_OFF_ABZ.value: param(fc.MU_OFF_ABZ.value, "OFF_ABZ", 0x00014EDC),
                fc.MU_OFF_UVW.value: param(fc.MU_OFF_UVW.value, "OFF_UVW", 0),
                fc.MU_PRES_POS.value: param(fc.MU_PRES_POS.value, "PRES_POS", 0),
            },
            derived_params={
                fc.MU_OFF_POS.value: param(fc.MU_OFF_POS.value, "OFF_POS", 0x00FFFFFF),
                fc.MU_OFF_COM.value: param(fc.MU_OFF_COM.value, "OFF_COM", 0x00000580),
            },
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )
        after_abs_reset = fc.ProtectedZeroState(
            params=baseline.params,
            derived_params={
                fc.MU_OFF_POS.value: param(fc.MU_OFF_POS.value, "OFF_POS", 0x000002FF),
                fc.MU_OFF_COM.value: param(fc.MU_OFF_COM.value, "OFF_COM", 0x00000580),
            },
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )
        compensated = fc.ProtectedZeroState(
            params={
                fc.MU_OFF_ABZ.value: param(
                    fc.MU_OFF_ABZ.value,
                    "OFF_ABZ",
                    0xFFD14EDC,
                    high=0xF,
                ),
                fc.MU_OFF_UVW.value: param(fc.MU_OFF_UVW.value, "OFF_UVW", 0),
                fc.MU_PRES_POS.value: param(fc.MU_PRES_POS.value, "PRES_POS", 0),
            },
            derived_params=baseline.derived_params,
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )

        captures = [after_abs_reset, compensated]
        original_capture = fc._capture_protected_params
        original_read_param = fc._read_param
        original_set_param = fc.mu.MU_SetParam
        original_write_params = fc.mu.MU_WriteParams
        original_write_cmd = fc.mu.MU_WriteCmdRegister
        try:
            fc._capture_protected_params = lambda _handle, _label: captures.pop(0)
            fc._read_param = (
                lambda _handle, index, name: param(index, name, 5)
                if index == fc.MU_MPC.value
                else original_read_param(_handle, index, name)
            )

            def fake_set_param(_handle, index, high, low, _flag):
                calls.append(("set_param", int(index.value), int(high.value), int(low.value)))
                return fc.MU_OK

            def fake_write_cmd(_handle, command):
                calls.append(("cmd", int(command.value), 0, 0))
                return fc.MU_OK

            fc.mu.MU_SetParam = fake_set_param
            fc.mu.MU_WriteParams = lambda _handle, _verify, _flags: fc.MU_OK
            fc.mu.MU_WriteCmdRegister = fake_write_cmd

            result = fc._compensate_zero_shift_from_derived_offsets(
                fc.MU_Handle(),
                baseline,
                "unit test",
            )
        finally:
            fc._capture_protected_params = original_capture
            fc._read_param = original_read_param
            fc.mu.MU_SetParam = original_set_param
            fc.mu.MU_WriteParams = original_write_params
            fc.mu.MU_WriteCmdRegister = original_write_cmd

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.params[fc.MU_OFF_ABZ.value].high, 0xF)
        self.assertEqual(result.params[fc.MU_OFF_ABZ.value].low, 0xFFD14EDC)
        self.assertIn(("set_param", fc.MU_OFF_ABZ.value, 0xF, 0xFFD14EDC), calls)
        self.assertIn(("cmd", fc.MU_CMD_WRITE_OFF.value, 0, 0), calls)
        self.assertIn(("cmd", fc.MU_CMD_CRC_CALC.value, 0, 0), calls)
        self.assertIn(("cmd", fc.MU_CMD_ABS_RESET.value, 0, 0), calls)

    def test_encoder_side_zero_compensation_retries_residual_error(self):
        calls: list[tuple[str, int, int, int]] = []

        def param(index, name, low, high=0):
            return fc.ProtectedMuParam(index=index, name=name, high=high, low=low)

        baseline = fc.ProtectedZeroState(
            params={
                fc.MU_OFF_ABZ.value: param(fc.MU_OFF_ABZ.value, "OFF_ABZ", 0x00014EDC),
                fc.MU_OFF_UVW.value: param(fc.MU_OFF_UVW.value, "OFF_UVW", 0),
                fc.MU_PRES_POS.value: param(fc.MU_PRES_POS.value, "PRES_POS", 0),
            },
            derived_params={
                fc.MU_OFF_POS.value: param(fc.MU_OFF_POS.value, "OFF_POS", 0x00FFFFFF),
                fc.MU_OFF_COM.value: param(fc.MU_OFF_COM.value, "OFF_COM", 0x00000580),
            },
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )
        first_measurement = fc.ProtectedZeroState(
            params=baseline.params,
            derived_params={
                fc.MU_OFF_POS.value: param(fc.MU_OFF_POS.value, "OFF_POS", 0x000002FF),
                fc.MU_OFF_COM.value: param(fc.MU_OFF_COM.value, "OFF_COM", 0x00000580),
            },
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )
        first_residual = fc.ProtectedZeroState(
            params={
                fc.MU_OFF_ABZ.value: param(
                    fc.MU_OFF_ABZ.value,
                    "OFF_ABZ",
                    0xFFD14EDC,
                    high=0xF,
                ),
                fc.MU_OFF_UVW.value: param(fc.MU_OFF_UVW.value, "OFF_UVW", 0),
                fc.MU_PRES_POS.value: param(fc.MU_PRES_POS.value, "PRES_POS", 0),
            },
            derived_params={
                fc.MU_OFF_POS.value: param(fc.MU_OFF_POS.value, "OFF_POS", 0x0000001F),
                fc.MU_OFF_COM.value: param(fc.MU_OFF_COM.value, "OFF_COM", 0x00000580),
            },
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )
        second_measurement = first_residual
        second_verified = fc.ProtectedZeroState(
            params={
                fc.MU_OFF_ABZ.value: param(
                    fc.MU_OFF_ABZ.value,
                    "OFF_ABZ",
                    0xFFCF4EDC,
                    high=0xF,
                ),
                fc.MU_OFF_UVW.value: param(fc.MU_OFF_UVW.value, "OFF_UVW", 0),
                fc.MU_PRES_POS.value: param(fc.MU_PRES_POS.value, "PRES_POS", 0),
            },
            derived_params=baseline.derived_params,
            real_pres_pos_high=0,
            real_pres_pos_low=0,
        )

        captures = [first_measurement, first_residual, second_measurement, second_verified]
        original_capture = fc._capture_protected_params
        original_read_param = fc._read_param
        original_set_param = fc.mu.MU_SetParam
        original_write_params = fc.mu.MU_WriteParams
        original_write_cmd = fc.mu.MU_WriteCmdRegister
        try:
            fc._capture_protected_params = lambda _handle, _label: captures.pop(0)
            fc._read_param = (
                lambda _handle, index, name: param(index, name, 5)
                if index == fc.MU_MPC.value
                else original_read_param(_handle, index, name)
            )

            def fake_set_param(_handle, index, high, low, _flag):
                calls.append(("set_param", int(index.value), int(high.value), int(low.value)))
                return fc.MU_OK

            def fake_write_cmd(_handle, command):
                calls.append(("cmd", int(command.value), 0, 0))
                return fc.MU_OK

            fc.mu.MU_SetParam = fake_set_param
            fc.mu.MU_WriteParams = lambda _handle, _verify, _flags: fc.MU_OK
            fc.mu.MU_WriteCmdRegister = fake_write_cmd

            result = fc._compensate_zero_shift_from_derived_offsets(
                fc.MU_Handle(),
                baseline,
                "unit test residual",
            )
        finally:
            fc._capture_protected_params = original_capture
            fc._read_param = original_read_param
            fc.mu.MU_SetParam = original_set_param
            fc.mu.MU_WriteParams = original_write_params
            fc.mu.MU_WriteCmdRegister = original_write_cmd

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.params[fc.MU_OFF_ABZ.value].high, 0xF)
        self.assertEqual(result.params[fc.MU_OFF_ABZ.value].low, 0xFFCF4EDC)
        self.assertIn(("set_param", fc.MU_OFF_ABZ.value, 0xF, 0xFFD14EDC), calls)
        self.assertIn(("set_param", fc.MU_OFF_ABZ.value, 0xF, 0xFFCF4EDC), calls)

    def test_restart_controller_uses_owon_power_cycle(self):
        calls: list[tuple[str, object]] = []

        class FakeCan:
            def close_can(self):
                calls.append(("close_can", True))

        class FakeNode:
            nmt = object()

        class FakeController:
            added_node = FakeNode()

        class NewCan:
            def __init__(self, can_bitrate):
                calls.append(("new_can_bitrate", can_bitrate))
                self.can_network = object()

        class NewController:
            def __init__(self, can, node):
                calls.append(("new_controller_node", node))
                self.added_node = object()

            def clear_errors(self):
                calls.append(("clear_errors", True))

        original_power_cycle = fc.power_cycle_owon_spe6053
        original_nmt_reset = fc.nmt_reset_node_compat
        original_driver_can = fc.DriverCan
        original_micontrol = fc.MicontrolF35_CAN
        try:
            fc.power_cycle_owon_spe6053 = lambda **kwargs: calls.append(("power_cycle", kwargs)) or True
            fc.nmt_reset_node_compat = lambda _nmt: calls.append(("nmt_reset", True))
            fc.DriverCan = NewCan
            fc.MicontrolF35_CAN = NewController

            new_can, new_mic = fc.restart_controller(
                can=FakeCan(),
                mic=FakeController(),
                node=50,
                can_bitrate=125,
            )
        finally:
            fc.power_cycle_owon_spe6053 = original_power_cycle
            fc.nmt_reset_node_compat = original_nmt_reset
            fc.DriverCan = original_driver_can
            fc.MicontrolF35_CAN = original_micontrol

        self.assertIsInstance(new_can, NewCan)
        self.assertIsInstance(new_mic, NewController)
        self.assertIn(
            (
                "power_cycle",
                {"off_seconds": 3.0, "voltage_v": 24.0, "current_a": 5.0},
            ),
            calls,
        )
        self.assertNotIn(("nmt_reset", True), calls)
        self.assertIn(("close_can", True), calls)
        self.assertIn(("clear_errors", True), calls)


if __name__ == "__main__":
    unittest.main()
