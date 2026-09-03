from __future__ import annotations

import unittest
from pathlib import Path

from main import CalibrationGUI as gui


class CanInterfaceMessageTests(unittest.TestCase):
    def test_missing_socketcan_interface_is_reported_as_setup_failure(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )

        message = gui._can_interface_setup_failure_message(
            'CAN connection failed for node 59. (Could not inspect CAN interface can0: Device "can0" does not exist.)',
            'CAN connection failed for node 50. (Could not inspect CAN interface can0: Device "can0" does not exist.)',
            context,
        )

        self.assertIsNotNone(message)
        assert message is not None
        self.assertIn("CAN interface setup failed", message)
        self.assertIn("Product specification was read correctly", message)
        self.assertIn("Steering Node ID is 50", message)
        self.assertIn("can0 does not exist", message)
        self.assertNotIn("CAN node ID is unknown", message)

    def test_configuration_start_tries_standard_node_after_relays(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_check_candidates = gui._check_configuration_can_candidates
        original_check = gui.check_can_connection
        original_recover = gui.recover_can_interface_after_failure
        original_detach = gui._detach_manual_can_for_power_change
        original_can_ok = gui.STATE.can_connection_ok
        original_can_node = gui.STATE.can_connection_node
        original_can_bitrate = gui.STATE.can_connection_bitrate
        original_manual_mic = gui.STATE.manual_mic
        try:
            gui.STATE.can_connection_ok = False
            gui.STATE.can_connection_node = None
            gui.STATE.can_connection_bitrate = None
            gui.STATE.manual_mic = None
            gui._check_configuration_can_candidates = lambda *_args, **_kwargs: calls.append(("preflight",)) or (_ for _ in ()).throw(AssertionError("preflight should not run"))
            gui._detach_manual_can_for_power_change = lambda message: calls.append(("detach", message))
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (True, "CAN connected to node 59.")
            gui.recover_can_interface_after_failure = lambda **kwargs: calls.append(("recover", kwargs)) or (False, "should not recover")

            gui.ensure_controller_ready_for_configuration(context)
        finally:
            gui._check_configuration_can_candidates = original_check_candidates
            gui.check_can_connection = original_check
            gui.recover_can_interface_after_failure = original_recover
            gui._detach_manual_can_for_power_change = original_detach
            gui.STATE.can_connection_ok = original_can_ok
            gui.STATE.can_connection_node = original_can_node
            gui.STATE.can_connection_bitrate = original_can_bitrate
            gui.STATE.manual_mic = original_manual_mic

        self.assertEqual([call[0] for call in calls], ["detach", "check"])
        self.assertEqual(calls[1][1][0], 59)
        self.assertEqual(calls[1][2]["can_bitrate"], 125)
        self.assertIs(calls[1][2]["context"], context)

    def test_task_can_start_uses_recovery_after_failed_first_connect(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=250,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_recover = gui.recover_can_interface_after_failure
        original_detach = gui._detach_manual_can_for_power_change
        original_sleep = gui.time.sleep
        original_can_ok = gui.STATE.can_connection_ok
        original_can_node = gui.STATE.can_connection_node
        original_can_bitrate = gui.STATE.can_connection_bitrate
        original_manual_mic = gui.STATE.manual_mic
        try:
            gui.STATE.can_connection_ok = False
            gui.STATE.can_connection_node = None
            gui.STATE.can_connection_bitrate = None
            gui.STATE.manual_mic = None
            gui._detach_manual_can_for_power_change = lambda message: calls.append(("detach", message))

            def fake_check(*args, **kwargs):
                calls.append(("check", args, kwargs))
                return (
                    (False, "CAN interface can0 bitrate is None.")
                    if len([call for call in calls if call[0] == "check"]) == 1
                    else (True, "CAN connected to node 50.")
                )

            gui.check_can_connection = fake_check
            gui.recover_can_interface_after_failure = (
                lambda **kwargs: calls.append(("recover", kwargs)) or (True, "Configured can0.")
            )
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            gui.ensure_controller_ready_for_task(context, "Calibration")
        finally:
            gui.check_can_connection = original_check
            gui.recover_can_interface_after_failure = original_recover
            gui._detach_manual_can_for_power_change = original_detach
            gui.time.sleep = original_sleep
            gui.STATE.can_connection_ok = original_can_ok
            gui.STATE.can_connection_node = original_can_node
            gui.STATE.can_connection_bitrate = original_can_bitrate
            gui.STATE.manual_mic = original_manual_mic

        self.assertEqual([call[0] for call in calls], ["detach", "check", "recover", "sleep", "check"])
        recover_call = calls[2][1]
        self.assertEqual(recover_call["can_bitrate"], 250)
        retry_check = calls[4]
        self.assertEqual(retry_check[1][0], 50)
        self.assertEqual(retry_check[2]["can_bitrate"], 250)
        self.assertIs(retry_check[2]["context"], context)

    def test_task_can_start_skips_when_product_node_is_already_connected(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_recover = gui.recover_can_interface_after_failure
        original_can_ok = gui.STATE.can_connection_ok
        original_can_node = gui.STATE.can_connection_node
        original_can_bitrate = gui.STATE.can_connection_bitrate
        original_manual_mic = gui.STATE.manual_mic
        try:
            gui.STATE.can_connection_ok = True
            gui.STATE.can_connection_node = 50
            gui.STATE.can_connection_bitrate = 125
            gui.STATE.manual_mic = object()
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (False, "should not connect")
            gui.recover_can_interface_after_failure = lambda **kwargs: calls.append(("recover", kwargs)) or (False, "should not recover")

            gui.ensure_task_can_connected(context, "Write Zero")
        finally:
            gui.check_can_connection = original_check
            gui.recover_can_interface_after_failure = original_recover
            gui.STATE.can_connection_ok = original_can_ok
            gui.STATE.can_connection_node = original_can_node
            gui.STATE.can_connection_bitrate = original_can_bitrate
            gui.STATE.manual_mic = original_manual_mic

        self.assertEqual(calls, [])

    def test_load_script_config_loads_script_then_writes_config_on_product_node(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=250,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_load_script = gui.load_steering_script_with_node_fallback
        original_restart = gui.restart_controller_with_relays_for_task
        original_load_config = gui.run_load_config
        original_validate = gui.run_configuration_controller_validation_status
        try:
            gui.load_steering_script_with_node_fallback = lambda _context: calls.append(("script", _context)) or {"script_path": "SteeringScript.py"}
            gui.restart_controller_with_relays_for_task = lambda _context, reason: calls.append(("restart", _context, reason)) or True
            gui.run_load_config = lambda *, node, can_bitrate, manage_relays=True: calls.append(("write_just_conf", node, can_bitrate, manage_relays)) or True
            gui.run_configuration_controller_validation_status = lambda *, node, can_bitrate: calls.append(("validate", node, can_bitrate)) or (True, "No error")

            result = gui.run_load_script_config_details(context)
        finally:
            gui.load_steering_script_with_node_fallback = original_load_script
            gui.restart_controller_with_relays_for_task = original_restart
            gui.run_load_config = original_load_config
            gui.run_configuration_controller_validation_status = original_validate

        self.assertTrue(result["ok"])
        self.assertEqual(
            calls,
            [
                ("script", context),
                ("restart", context, "Steering script loaded; applying product node ID."),
                ("write_just_conf", 50, 250, False),
                ("validate", 50, 250),
            ],
        )

    def test_configuration_validation_reports_minus_1092_after_short_spin(self):
        class FakeMic:
            last_ssi_configuration_error = 0

            def __init__(self) -> None:
                self.disabled = False

            def clear_errors(self) -> None:
                pass

            def get_extended_ssi(self) -> bool:
                return True

            def get_ssi_encoder_status(self) -> int:
                return gui.SSI_READY_STATUS

            def get_error_code(self) -> int:
                return -1092

            def enabled(self, status: bool) -> None:
                self.disabled = not status

        can = object()
        mic = FakeMic()
        calls: list[tuple[object, ...]] = []
        original_acquire = gui.acquire_controller
        original_release = gui.release_controller
        original_spin = gui.spin_to_angle_and_verify
        try:
            gui.acquire_controller = (
                lambda node, enable, can_bitrate: calls.append(("acquire", node, enable, can_bitrate)) or (can, mic, True)
            )
            gui.release_controller = lambda _can, owned: calls.append(("release", _can, owned))
            gui.spin_to_angle_and_verify = (
                lambda _mic, angle_deg, rpm, timeout_s: calls.append(("spin", _mic, angle_deg, rpm, timeout_s)) or True
            )

            ok, status = gui.run_configuration_controller_validation_status(
                node=50,
                can_bitrate=250,
            )
        finally:
            gui.acquire_controller = original_acquire
            gui.release_controller = original_release
            gui.spin_to_angle_and_verify = original_spin

        self.assertFalse(ok)
        self.assertEqual(status, "-1092")
        self.assertEqual(
            calls,
            [
                ("acquire", 50, False, 250),
                (
                    "spin",
                    mic,
                    gui.CONFIGURATION_SPIN_CHECK_DEG,
                    gui.CONFIGURATION_SPIN_CHECK_RPM,
                    gui.CONFIGURATION_SPIN_CHECK_TIMEOUT_S,
                ),
                ("release", can, True),
            ],
        )
        self.assertTrue(mic.disabled)

    def test_task_can_start_raises_after_failed_reconnect_and_recovery(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        original_check = gui.check_can_connection
        original_recover = gui.recover_can_interface_after_failure
        original_detach = gui._detach_manual_can_for_power_change
        original_can_ok = gui.STATE.can_connection_ok
        original_can_node = gui.STATE.can_connection_node
        original_can_bitrate = gui.STATE.can_connection_bitrate
        original_manual_mic = gui.STATE.manual_mic
        try:
            gui.STATE.can_connection_ok = False
            gui.STATE.can_connection_node = None
            gui.STATE.can_connection_bitrate = None
            gui.STATE.manual_mic = None
            gui._detach_manual_can_for_power_change = lambda _message: None
            gui.check_can_connection = lambda *args, **kwargs: (False, "Could not add CAN node 50.")
            gui.recover_can_interface_after_failure = lambda **_kwargs: (False, "Recovery skipped.")

            with self.assertRaisesRegex(RuntimeError, "CAN connection failed before TestCalibration"):
                gui.ensure_controller_ready_for_task(context, "TestCalibration")
        finally:
            gui.check_can_connection = original_check
            gui.recover_can_interface_after_failure = original_recover
            gui._detach_manual_can_for_power_change = original_detach
            gui.STATE.can_connection_ok = original_can_ok
            gui.STATE.can_connection_node = original_can_node
            gui.STATE.can_connection_bitrate = original_can_bitrate
            gui.STATE.manual_mic = original_manual_mic

    def test_manual_restart_reconnect_uses_two_value_can_check_result(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_confirm = gui.STATE.request_power_cycle_confirmation
        try:
            gui.STATE.request_power_cycle_confirmation = lambda timeout: calls.append(("confirm", timeout)) or True
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (True, "connected")

            self.assertTrue(gui.wait_for_manual_restart_and_reconnect(context, "Missing."))
        finally:
            gui.check_can_connection = original_check
            gui.STATE.request_power_cycle_confirmation = original_confirm

        check_calls = [call for call in calls if call[0] == "check"]
        self.assertEqual(len(check_calls), 1)
        self.assertEqual(check_calls[0][1][0], 50)
        self.assertEqual(check_calls[0][2]["can_bitrate"], 125)
        self.assertFalse(check_calls[0][2]["create_report"])

    def test_power_supply_route_delegates_to_controller_relay_power(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        calls: list[tuple[object, ...]] = []
        original_context = gui.STATE.current_product_context
        original_power = gui.set_controller_power_relays
        try:
            gui.STATE.current_product_context = context
            gui.set_controller_power_relays = lambda enabled, **kwargs: calls.append((enabled, kwargs)) or (True, "relay on")

            ok, message = gui.run_power_supply_output(node=59, enabled=True, can_bitrate=125)
        finally:
            gui.STATE.current_product_context = original_context
            gui.set_controller_power_relays = original_power

        self.assertTrue(ok)
        self.assertEqual(message, "relay on")
        self.assertEqual(calls, [(True, {"node": 59, "can_bitrate": 125, "reconnect": True, "context": context})])

    def test_manual_controller_power_on_can_reconnect_failure_is_nonfatal(self):
        class FakeRelayArduino:
            def __init__(self) -> None:
                self.mask = 0

            def _set_relays_bits(self, mask: int) -> bool:
                self.mask = mask
                return True

            def get_relays(self) -> int:
                return self.mask

        original_relay = gui.STATE.relay_arduino
        original_can_ok = gui.STATE.can_connection_ok
        original_can_node = gui.STATE.can_connection_node
        original_can_bitrate = gui.STATE.can_connection_bitrate
        original_can_message = gui.STATE.can_connection_message
        original_sleep = gui.time.sleep
        original_reconnect = gui._controller_reconnect_after_relay_power_on
        original_restart_can_service = gui.restart_st_can0_service
        original_cycle_can0 = gui.cycle_can0_link_down_up
        original_native_driver = gui._socketcan_channel_uses_native_driver
        try:
            gui.STATE.relay_arduino = FakeRelayArduino()
            gui.time.sleep = lambda _seconds: None
            gui._controller_reconnect_after_relay_power_on = (
                lambda **_kwargs: (False, 'CAN connection failed for node 50. (Device "can0" does not exist.)')
            )
            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: (False, "can0 is not native SocketCAN.")
            gui.restart_st_can0_service = lambda: (False, "Could not restart st-can0.service.")
            gui.cycle_can0_link_down_up = lambda: (False, "Could not cycle can0 down/up.")

            ok, message = gui.set_controller_power_relays(
                True,
                node=50,
                can_bitrate=125,
                fail_on_reconnect_error=False,
            )

            self.assertTrue(ok)
            self.assertIn("Controller power relays are ON", message)
            self.assertIn("CAN connection failed for node 50", message)
            self.assertFalse(gui.STATE.can_connection_ok)
            self.assertEqual(gui.STATE.can_connection_node, 50)
            self.assertEqual(gui.STATE.can_connection_bitrate, 125)
            self.assertEqual(gui.STATE.can_connection_message, "CAN not connected.")
        finally:
            gui.STATE.relay_arduino = original_relay
            gui.STATE.can_connection_ok = original_can_ok
            gui.STATE.can_connection_node = original_can_node
            gui.STATE.can_connection_bitrate = original_can_bitrate
            gui.STATE.can_connection_message = original_can_message
            gui.time.sleep = original_sleep
            gui._controller_reconnect_after_relay_power_on = original_reconnect
            gui.restart_st_can0_service = original_restart_can_service
            gui.cycle_can0_link_down_up = original_cycle_can0
            gui._socketcan_channel_uses_native_driver = original_native_driver

    def test_manual_controller_power_on_restarts_st_can0_before_reporting_can_failure(self):
        class FakeRelayArduino:
            def __init__(self) -> None:
                self.mask = 0

            def _set_relays_bits(self, mask: int) -> bool:
                self.mask = mask
                return True

            def get_relays(self) -> int:
                return self.mask

        calls: list[tuple[object, ...]] = []
        original_relay = gui.STATE.relay_arduino
        original_sleep = gui.time.sleep
        original_reconnect = gui._controller_reconnect_after_relay_power_on
        original_restart_can_service = gui.restart_st_can0_service
        original_cycle_can0 = gui.cycle_can0_link_down_up
        original_native_driver = gui._socketcan_channel_uses_native_driver
        try:
            gui.STATE.relay_arduino = FakeRelayArduino()
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            def fake_reconnect(**kwargs):
                calls.append(("reconnect", kwargs))
                return (
                    (False, 'CAN connection failed for node 50. (Device "can0" does not exist.)')
                    if len([call for call in calls if call[0] == "reconnect"]) == 1
                    else (True, "CAN connected to node 50.")
                )

            gui._controller_reconnect_after_relay_power_on = fake_reconnect
            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: calls.append(("inspect_native",)) or (False, "can0 is not native SocketCAN.")
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (True, "Restarted st-can0.service.")
            gui.cycle_can0_link_down_up = lambda: calls.append(("cycle_can0",)) or (True, "Cycled can0 down/up.")

            ok, message = gui.set_controller_power_relays(
                True,
                node=50,
                can_bitrate=125,
                fail_on_reconnect_error=False,
            )

            self.assertTrue(ok)
            self.assertIn("Restarted st-can0.service", message)
            self.assertIn("CAN connected to node 50", message)
            self.assertEqual(
                [call[0] for call in calls if call[0] in {"reconnect", "restart_st_can0"}],
                ["reconnect", "restart_st_can0", "reconnect"],
            )
        finally:
            gui.STATE.relay_arduino = original_relay
            gui.time.sleep = original_sleep
            gui._controller_reconnect_after_relay_power_on = original_reconnect
            gui.restart_st_can0_service = original_restart_can_service
            gui.cycle_can0_link_down_up = original_cycle_can0
            gui._socketcan_channel_uses_native_driver = original_native_driver

    def test_gui_can_check_restarts_st_can0_and_retries_explicit_node(self):
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_restart_can_service = gui.restart_st_can0_service
        original_cycle_can0 = gui.cycle_can0_link_down_up
        original_native_driver = gui._socketcan_channel_uses_native_driver
        original_sleep = gui.time.sleep
        try:
            def fake_check(*args, **kwargs):
                calls.append(("check", args, kwargs))
                return (
                    (False, 'CAN connection failed for node 50. (Device "can0" does not exist.)')
                    if len([call for call in calls if call[0] == "check"]) == 1
                    else (True, "CAN connected to node 50.")
                )

            gui.check_can_connection = fake_check
            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: calls.append(("inspect_native",)) or (False, "can0 is not native SocketCAN.")
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (True, "Restarted st-can0.service.")
            gui.cycle_can0_link_down_up = lambda: calls.append(("cycle_can0",)) or (True, "Cycled can0 down/up.")
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            connected, node, bitrate, message, context = gui._check_gui_can_with_st_can0_retry(
                explicit_target=True,
                node=50,
                bitrate=125,
            )
        finally:
            gui.check_can_connection = original_check
            gui.restart_st_can0_service = original_restart_can_service
            gui.cycle_can0_link_down_up = original_cycle_can0
            gui._socketcan_channel_uses_native_driver = original_native_driver
            gui.time.sleep = original_sleep

        self.assertTrue(connected)
        self.assertEqual(node, 50)
        self.assertEqual(bitrate, 125)
        self.assertIsNone(context)
        self.assertIn("Restarted st-can0.service", message)
        self.assertIn("CAN connected to node 50", message)
        self.assertEqual(
            [call[0] for call in calls if call[0] in {"check", "restart_st_can0"}],
            ["check", "restart_st_can0", "check"],
        )

    def test_configure_socketcan_link_up_only_sets_up_when_bitrate_matches(self):
        calls: list[tuple[object, ...]] = []
        original_bitrate = gui._socketcan_configured_bitrate_hz
        original_run_ip_link = gui._run_ip_link_command
        try:
            gui._socketcan_configured_bitrate_hz = lambda *_args, **_kwargs: 125000
            gui._run_ip_link_command = lambda args, **kwargs: calls.append((tuple(args), kwargs)) or (True, "ok")

            ok, message = gui.configure_socketcan_link_up(can_bitrate=125)
        finally:
            gui._socketcan_configured_bitrate_hz = original_bitrate
            gui._run_ip_link_command = original_run_ip_link

        self.assertTrue(ok)
        self.assertIn("Configured can0 up", message)
        self.assertEqual([call[0] for call in calls], [("link", "set", "can0", "up")])

    def test_configure_socketcan_link_up_reconfigures_when_bitrate_differs(self):
        calls: list[tuple[object, ...]] = []
        original_bitrate = gui._socketcan_configured_bitrate_hz
        original_run_ip_link = gui._run_ip_link_command
        try:
            gui._socketcan_configured_bitrate_hz = lambda *_args, **_kwargs: 250000
            gui._run_ip_link_command = lambda args, **kwargs: calls.append((tuple(args), kwargs)) or (True, "ok")

            ok, message = gui.configure_socketcan_link_up(can_bitrate=125)
        finally:
            gui._socketcan_configured_bitrate_hz = original_bitrate
            gui._run_ip_link_command = original_run_ip_link

        self.assertTrue(ok)
        self.assertIn("125000", message)
        self.assertEqual(
            [call[0] for call in calls],
            [
                ("link", "set", "can0", "down"),
                ("link", "set", "can0", "type", "can", "bitrate", "125000"),
                ("link", "set", "can0", "up"),
            ],
        )

    def test_ip_link_recovery_uses_sudo_password_without_prompt(self):
        calls: list[tuple[object, ...]] = []
        original_run = gui.subprocess.run
        original_which = gui.shutil.which
        original_password = gui._sudo_password
        try:
            def fake_which(name):
                return {
                    "ip": "/usr/sbin/ip",
                    "sudo": "/usr/bin/sudo",
                }.get(name)

            def fake_run(command, **kwargs):
                calls.append((tuple(command), kwargs))
                if command[0] == "/usr/sbin/ip":
                    return gui.subprocess.CompletedProcess(
                        command,
                        2,
                        "",
                        "RTNETLINK answers: Operation not permitted",
                    )
                if "-n" in command:
                    return gui.subprocess.CompletedProcess(
                        command,
                        1,
                        "",
                        "sudo: a password is required",
                    )
                return gui.subprocess.CompletedProcess(command, 0, "", "")

            gui.shutil.which = fake_which
            gui.subprocess.run = fake_run
            gui._sudo_password = lambda: "mobotic"

            ok, detail = gui._run_ip_link_command(["link", "set", "can0", "up"])
        finally:
            gui.subprocess.run = original_run
            gui.shutil.which = original_which
            gui._sudo_password = original_password

        self.assertTrue(ok)
        self.assertIn("sudo /usr/sbin/ip link set can0 up", detail)
        self.assertNotIn("mobotic", detail)
        self.assertEqual(calls[2][0], ("/usr/bin/sudo", "-S", "-p", "", "/usr/sbin/ip", "link", "set", "can0", "up"))
        self.assertEqual(calls[2][1]["input"], "mobotic\n")

    def test_st_can0_restart_uses_sudo_password_without_prompt(self):
        calls: list[tuple[object, ...]] = []
        original_run = gui.subprocess.run
        original_which = gui.shutil.which
        original_password = gui._sudo_password
        try:
            def fake_which(name):
                return {
                    "systemctl": "/usr/bin/systemctl",
                    "sudo": "/usr/bin/sudo",
                }.get(name)

            def fake_run(command, **kwargs):
                calls.append((tuple(command), kwargs))
                if command[0] == "/usr/bin/systemctl":
                    return gui.subprocess.CompletedProcess(
                        command,
                        1,
                        "",
                        "Interactive authentication required.",
                    )
                if "-n" in command:
                    return gui.subprocess.CompletedProcess(
                        command,
                        1,
                        "",
                        "sudo: a password is required",
                    )
                return gui.subprocess.CompletedProcess(command, 0, "", "")

            gui.shutil.which = fake_which
            gui.subprocess.run = fake_run
            gui._sudo_password = lambda: "mobotic"

            ok, detail = gui.restart_st_can0_service()
        finally:
            gui.subprocess.run = original_run
            gui.shutil.which = original_which
            gui._sudo_password = original_password

        self.assertTrue(ok)
        self.assertEqual(detail, "Restarted st-can0.service.")
        self.assertEqual(calls[2][0], ("/usr/bin/sudo", "-S", "-p", "", "/usr/bin/systemctl", "restart", "st-can0.service"))
        self.assertEqual(calls[2][1]["input"], "mobotic\n")

    def test_summarized_can_setup_failure_uses_native_socketcan_recovery(self):
        calls: list[tuple[object, ...]] = []
        original_recover_native = gui._socketcan_channel_uses_native_driver
        original_configure_socketcan = gui.configure_socketcan_link_up
        original_restart_can_service = gui.restart_st_can0_service
        original_stop_can_service = gui.stop_st_can0_service
        try:
            def fake_restart():
                calls.append(("restart_st_can0",))
                raise AssertionError("st-can0.service must not be restarted for native SocketCAN setup failures")

            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: calls.append(("inspect_native",)) or (True, "can0 is managed by native SocketCAN driver gs_usb.")
            gui.stop_st_can0_service = lambda: calls.append(("stop_st_can0",)) or (True, "Stopped st-can0.service.")
            gui.configure_socketcan_link_up = lambda **kwargs: calls.append(("configure_socketcan", kwargs)) or (False, "Could not configure can0: sudo password required. Run: sudo ip link set can0 up")
            gui.restart_st_can0_service = fake_restart

            ok, message = gui.recover_can_interface_after_failure(
                first_failure=(
                    "CAN interface setup failed. Product specification was read correctly. "
                    "Product specification Steering Node ID is 50. Run: sudo ip link set can0 up"
                ),
                can_bitrate=125,
            )
        finally:
            gui._socketcan_channel_uses_native_driver = original_recover_native
            gui.configure_socketcan_link_up = original_configure_socketcan
            gui.restart_st_can0_service = original_restart_can_service
            gui.stop_st_can0_service = original_stop_can_service

        self.assertFalse(ok)
        self.assertIn("native SocketCAN driver gs_usb", message)
        self.assertIn("Stopped st-can0.service", message)
        self.assertIn("sudo ip link set can0 up", message)
        self.assertEqual(
            [call[0] for call in calls],
            ["inspect_native", "stop_st_can0", "configure_socketcan"],
        )

    def test_native_socketcan_bitrate_setup_stops_stale_st_can0_service(self):
        calls: list[tuple[object, ...]] = []
        original_recover_native = gui._socketcan_channel_uses_native_driver
        original_configure_socketcan = gui.configure_socketcan_link_up
        original_restart_can_service = gui.restart_st_can0_service
        original_stop_can_service = gui.stop_st_can0_service
        try:
            def fake_restart():
                calls.append(("restart_st_can0",))
                raise AssertionError("st-can0.service must not be restarted for native SocketCAN bitrate setup")

            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: calls.append(("inspect_native",)) or (True, "can0 is managed by native SocketCAN driver gs_usb.")
            gui.stop_st_can0_service = lambda: calls.append(("stop_st_can0",)) or (True, "Stopped st-can0.service.")
            gui.configure_socketcan_link_up = lambda **kwargs: calls.append(("configure_socketcan", kwargs)) or (True, "Configured can0 up at 125000 bitrate.")
            gui.restart_st_can0_service = fake_restart

            ok, message = gui.recover_can_interface_after_failure(
                first_failure=(
                    "CAN connection failed for node 50. "
                    "(CAN interface can0 bitrate is None, expected 125000.)"
                ),
                can_bitrate=125,
            )
        finally:
            gui._socketcan_channel_uses_native_driver = original_recover_native
            gui.configure_socketcan_link_up = original_configure_socketcan
            gui.restart_st_can0_service = original_restart_can_service
            gui.stop_st_can0_service = original_stop_can_service

        self.assertTrue(ok)
        self.assertIn("native SocketCAN driver gs_usb", message)
        self.assertIn("Stopped st-can0.service", message)
        self.assertIn("Configured can0 up at 125000 bitrate", message)
        self.assertEqual(
            [call[0] for call in calls],
            ["inspect_native", "stop_st_can0", "configure_socketcan"],
        )

    def test_gui_can_check_configures_native_socketcan_without_st_can0_restart(self):
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_restart_can_service = gui.restart_st_can0_service
        original_stop_can_service = gui.stop_st_can0_service
        original_native_driver = gui._socketcan_channel_uses_native_driver
        original_configure_socketcan = gui.configure_socketcan_link_up
        original_sleep = gui.time.sleep
        try:
            def fake_check(*args, **kwargs):
                calls.append(("check", args, kwargs))
                return (
                    (False, "CAN connection failed for node 50. (Failed to transmit: Network is down [Error Code 100])")
                    if len([call for call in calls if call[0] == "check"]) == 1
                    else (True, "CAN connected to node 50.")
                )

            def fake_restart():
                calls.append(("restart_st_can0",))
                raise AssertionError("st-can0.service must not be restarted for native SocketCAN")

            def fake_native_driver(*_args, **_kwargs):
                calls.append(("inspect_native",))
                return True, "can0 is managed by native SocketCAN driver gs_usb."

            def fake_configure_socketcan(**kwargs):
                calls.append(("configure_socketcan", kwargs))
                return True, "Configured can0 up at 125000 bitrate."

            gui.check_can_connection = fake_check
            gui.restart_st_can0_service = fake_restart
            gui.stop_st_can0_service = lambda: calls.append(("stop_st_can0",)) or (True, "Stopped st-can0.service.")
            gui._socketcan_channel_uses_native_driver = fake_native_driver
            gui.configure_socketcan_link_up = fake_configure_socketcan
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            connected, node, bitrate, message, context = gui._check_gui_can_with_st_can0_retry(
                explicit_target=True,
                node=50,
                bitrate=125,
            )
        finally:
            gui.check_can_connection = original_check
            gui.restart_st_can0_service = original_restart_can_service
            gui.stop_st_can0_service = original_stop_can_service
            gui._socketcan_channel_uses_native_driver = original_native_driver
            gui.configure_socketcan_link_up = original_configure_socketcan
            gui.time.sleep = original_sleep

        self.assertTrue(connected)
        self.assertEqual(node, 50)
        self.assertEqual(bitrate, 125)
        self.assertIsNone(context)
        self.assertIn("native SocketCAN driver gs_usb", message)
        self.assertIn("Stopped st-can0.service", message)
        self.assertIn("CAN connected to node 50", message)
        self.assertNotIn("Restarted st-can0.service", message)
        self.assertEqual(
            [call[0] for call in calls if call[0] in {"check", "inspect_native", "stop_st_can0", "configure_socketcan", "restart_st_can0"}],
            ["check", "inspect_native", "stop_st_can0", "configure_socketcan", "check"],
        )
        configure_calls = [call for call in calls if call[0] == "configure_socketcan"]
        self.assertEqual(configure_calls[0][1]["can_bitrate"], 125)

    def test_gui_can_check_cycles_can0_down_up_when_service_restart_fails(self):
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_restart_can_service = gui.restart_st_can0_service
        original_cycle_can0 = gui.cycle_can0_link_down_up
        original_native_driver = gui._socketcan_channel_uses_native_driver
        original_sleep = gui.time.sleep
        try:
            def fake_check(*args, **kwargs):
                calls.append(("check", args, kwargs))
                return (
                    (False, 'CAN connection failed for node 50. (bitrate is None)')
                    if len([call for call in calls if call[0] == "check"]) == 1
                    else (True, "CAN connected to node 50.")
                )

            gui.check_can_connection = fake_check
            gui._socketcan_channel_uses_native_driver = lambda *_args, **_kwargs: calls.append(("inspect_native",)) or (False, "can0 is not native SocketCAN.")
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (False, "Restarting st-can0.service timed out.")
            gui.cycle_can0_link_down_up = lambda: calls.append(("cycle_can0",)) or (True, "Cycled can0 down/up.")
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            connected, node, bitrate, message, context = gui._check_gui_can_with_st_can0_retry(
                explicit_target=True,
                node=50,
                bitrate=125,
            )
        finally:
            gui.check_can_connection = original_check
            gui.restart_st_can0_service = original_restart_can_service
            gui.cycle_can0_link_down_up = original_cycle_can0
            gui._socketcan_channel_uses_native_driver = original_native_driver
            gui.time.sleep = original_sleep

        self.assertTrue(connected)
        self.assertEqual(node, 50)
        self.assertEqual(bitrate, 125)
        self.assertIsNone(context)
        self.assertIn("Restarting st-can0.service timed out.", message)
        self.assertIn("Cycled can0 down/up.", message)
        self.assertEqual(
            [call[0] for call in calls if call[0] in {"check", "restart_st_can0", "cycle_can0"}],
            ["check", "restart_st_can0", "cycle_can0", "check"],
        )

    def test_gui_can_check_does_not_restart_service_for_node_timeout(self):
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_restart_can_service = gui.restart_st_can0_service
        original_cycle_can0 = gui.cycle_can0_link_down_up
        original_sleep = gui.time.sleep
        try:
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (
                False,
                "CAN connection failed for node 50. (Could not add CAN node 50.)",
            )
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (True, "Restarted st-can0.service.")
            gui.cycle_can0_link_down_up = lambda: calls.append(("cycle_can0",)) or (True, "Cycled can0 down/up.")
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            connected, node, bitrate, message, context = gui._check_gui_can_with_st_can0_retry(
                explicit_target=True,
                node=50,
                bitrate=125,
            )
        finally:
            gui.check_can_connection = original_check
            gui.restart_st_can0_service = original_restart_can_service
            gui.cycle_can0_link_down_up = original_cycle_can0
            gui.time.sleep = original_sleep

        self.assertFalse(connected)
        self.assertEqual(node, 50)
        self.assertEqual(bitrate, 125)
        self.assertIsNone(context)
        self.assertIn("controller node did not respond", message)
        self.assertEqual([call[0] for call in calls], ["check"])

    def test_operation_relay_mask_uses_controller_power_only(self):
        self.assertEqual(
            gui.operation_relay_mask(),
            gui._relay_mask(1, 2, 3, 4, 7, 8),
        )

    def test_load_config_keeps_controller_power_relay_mask_around_mu_write(self):
        from logic import FlashConfigZero as fz

        calls: list[tuple[object, ...]] = []
        can = object()
        mic = object()
        relay = object()
        original_acquire = gui.acquire_controller
        original_release = gui.release_controller
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_sleep = gui.time.sleep
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        original_reload = gui.importlib.reload
        original_write = fz.write_just_conf
        try:
            gui.acquire_controller = (
                lambda node, can_bitrate: calls.append(("acquire", node, can_bitrate)) or (can, mic, False)
            )
            gui.release_controller = lambda _can, owned: calls.append(("release", _can, owned))
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))
            gui.OPERATION_RELAY_SETTLE_S = 1.25
            gui.importlib.reload = lambda module: module
            fz.write_just_conf = lambda _mu, _handle, _mic, _serial: calls.append(("write", _mic)) or True

            self.assertTrue(gui.run_load_config(node=50, can_bitrate=125))
        finally:
            gui.acquire_controller = original_acquire
            gui.release_controller = original_release
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.time.sleep = original_sleep
            gui.OPERATION_RELAY_SETTLE_S = original_settle
            gui.importlib.reload = original_reload
            fz.write_just_conf = original_write

        self.assertEqual(
            calls,
            [
                ("acquire", 50, 125),
                ("relay", relay, gui.controller_power_relay_mask(), "controller power relay mask"),
                ("sleep", 1.25),
                ("write", mic),
                ("relay", relay, gui.controller_power_relay_mask(), "controller power relay mask restore"),
                ("release", can, False),
            ],
        )

    def test_controller_relay_restart_can_restore_operation_relay_mask(self):
        class FakeRelayArduino:
            def __init__(self) -> None:
                self.masks: list[int] = []

            def _set_relays_bits(self, mask: int) -> bool:
                self.masks.append(int(mask))
                return True

            def get_relays(self) -> int:
                return self.masks[-1] if self.masks else 0

        relay = FakeRelayArduino()
        original_relay = gui.STATE.relay_arduino
        original_sleep = gui.time.sleep
        try:
            gui.STATE.relay_arduino = relay
            gui.time.sleep = lambda _seconds: None

            ok, message = gui.restart_controller_with_relays(
                reconnect=False,
                on_mask=gui.operation_relay_mask(),
            )
        finally:
            gui.STATE.relay_arduino = original_relay
            gui.time.sleep = original_sleep

        self.assertTrue(ok)
        self.assertIn("CAN reconnect deferred", message)
        self.assertEqual(relay.masks, [0, gui.operation_relay_mask()])

    def test_start_task_blocks_steering_without_product(self):
        original_barcode = gui.STATE.current_barcode
        original_steering = gui.STATE.steering_available
        original_running = gui.STATE.running
        original_inflight = gui.STATE.manual_requests_in_flight
        try:
            gui.STATE.current_barcode = ""
            gui.STATE.steering_available = None
            gui.STATE.running = False
            gui.STATE.manual_requests_in_flight = 0

            ok, message = gui.STATE.start_task("load_script_config")
        finally:
            gui.STATE.current_barcode = original_barcode
            gui.STATE.steering_available = original_steering
            gui.STATE.running = original_running
            gui.STATE.manual_requests_in_flight = original_inflight

        self.assertFalse(ok)
        self.assertEqual(message, "Scan a steering product before starting steering tasks.")

    def test_start_task_blocks_steering_when_product_has_no_steering(self):
        original_barcode = gui.STATE.current_barcode
        original_steering = gui.STATE.steering_available
        original_running = gui.STATE.running
        original_inflight = gui.STATE.manual_requests_in_flight
        try:
            gui.STATE.current_barcode = "99038922252125052947221126788"
            gui.STATE.steering_available = False
            gui.STATE.running = False
            gui.STATE.manual_requests_in_flight = 0

            ok, message = gui.STATE.start_task("load_script_config")
        finally:
            gui.STATE.current_barcode = original_barcode
            gui.STATE.steering_available = original_steering
            gui.STATE.running = original_running
            gui.STATE.manual_requests_in_flight = original_inflight

        self.assertFalse(ok)
        self.assertEqual(message, "Steering is not available for this product.")

    def test_gui_task_activates_and_deactivates_operation_relays(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        try:
            relay = object()
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.OPERATION_RELAY_SETTLE_S = 0
            gui.STATE.running = True

            gui.STATE._run_task("traction_calibration", {"product_barcode": "99038922252125052947221126788"})
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.OPERATION_RELAY_SETTLE_S = original_settle

        self.assertEqual(calls[0], ("relay", relay, gui.task_start_relay_mask(), "task relays"))
        self.assertEqual(calls[1][0], "task")
        self.assertEqual(calls[2], ("relay", relay, 0, "task relays off"))

    def test_gui_task_waits_after_operation_relays_before_task_body(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_sleep = gui.time.sleep
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        try:
            relay = object()
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))
            gui.OPERATION_RELAY_SETTLE_S = 1.25
            gui.STATE.running = True

            gui.STATE._run_task("traction_calibration", {"product_barcode": "99038922252125052947221126788"})
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.time.sleep = original_sleep
            gui.OPERATION_RELAY_SETTLE_S = original_settle
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log

        self.assertEqual(calls[0], ("relay", relay, gui.task_start_relay_mask(), "task relays"))
        self.assertEqual(calls[1], ("sleep", 1.25))
        self.assertEqual(calls[2][0], "task")
        self.assertEqual(calls[3], ("relay", relay, 0, "task relays off"))

    def test_gui_task_deactivates_operation_relays_after_task_exception(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        try:
            relay = object()

            def fail_task(_task_id, task_options=None):
                calls.append(("task", _task_id, task_options))
                raise RuntimeError("task failed")

            gui.run_task = fail_task
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.OPERATION_RELAY_SETTLE_S = 0
            gui.STATE.running = True

            gui.STATE._run_task("traction_calibration", {"product_barcode": "99038922252125052947221126788"})
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.OPERATION_RELAY_SETTLE_S = original_settle

        self.assertEqual(calls[0], ("relay", relay, gui.task_start_relay_mask(), "task relays"))
        self.assertEqual(calls[1][0], "task")
        self.assertEqual(calls[2], ("relay", relay, 0, "task relays off"))

    def test_gui_task_activation_failure_skips_task_body(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        try:
            relay = object()
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui.OPERATION_RELAY_SETTLE_S = 0

            def fail_activation(arduino, mask, label, **kwargs):
                calls.append(("relay", arduino, mask, label))
                if mask == gui.task_start_relay_mask():
                    raise RuntimeError("relay unavailable")

            gui._confirmed_set_relays = fail_activation
            gui.STATE.running = True

            gui.STATE._run_task("traction_calibration", {"product_barcode": "99038922252125052947221126788"})
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.OPERATION_RELAY_SETTLE_S = original_settle

        self.assertEqual(
            calls,
            [
                ("relay", relay, gui.task_start_relay_mask(), "task relays"),
                ("relay", relay, 0, "task relays off after activation failure"),
            ],
        )

    def test_confirmed_set_relays_accepts_readback_after_lost_set_echo(self):
        class FakeRelayArduino:
            def __init__(self):
                self.mask = 0
                self.set_calls = 0

            def _set_relays_bits(self, mask: int) -> bool:
                self.set_calls += 1
                self.mask = mask
                return False

            def get_relays(self) -> int:
                return self.mask

        relay = FakeRelayArduino()

        gui._confirmed_set_relays(relay, gui.operation_relay_mask(), "operation relays")

        self.assertEqual(relay.mask, gui.operation_relay_mask())
        self.assertEqual(relay.set_calls, 1)

    def test_manual_relay_mode_waits_instead_of_setting_relays(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_set_relays = gui._confirmed_set_relays
        original_wait = gui.wait_for_manual_operation_relay_step
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_relay_mode = gui.STATE.relay_mode
        try:
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._confirmed_set_relays = lambda *args, **kwargs: calls.append(("relay", args, kwargs))
            gui.wait_for_manual_operation_relay_step = lambda action, label: calls.append(("manual", action, label))
            gui.STATE.relay_mode = "manual"
            gui.STATE.running = True

            gui.STATE._run_task("traction_calibration", {"product_barcode": "99038922252125052947221126788"})
        finally:
            gui.run_task = original_run_task
            gui._confirmed_set_relays = original_set_relays
            gui.wait_for_manual_operation_relay_step = original_wait
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.STATE.relay_mode = original_relay_mode

        self.assertEqual(
            calls,
            [
                ("manual", "activate", "Traction Calibration"),
                ("task", "traction_calibration", {"product_barcode": "99038922252125052947221126788"}),
                ("manual", "deactivate", "Traction Calibration"),
            ],
        )

    def test_eol_does_not_use_gui_task_operation_relays(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_wait = gui.wait_for_manual_operation_relay_step
        original_reconnect = gui.reconnect_gui_can
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_relay_mode = gui.STATE.relay_mode
        original_settle = gui.OPERATION_RELAY_SETTLE_S
        try:
            relay = object()
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: relay
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.wait_for_manual_operation_relay_step = lambda action, label: calls.append(("manual", action, label))
            gui.reconnect_gui_can = lambda node, bitrate=gui.DEFAULT_CAN_BITRATE: (True, "reconnected")
            gui.OPERATION_RELAY_SETTLE_S = 0
            gui.STATE.relay_mode = "manual"
            gui.STATE.running = True

            gui.STATE._run_task("run_eol", {"product_barcode": "SO-1000", "motor_barcode": "0"})
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.wait_for_manual_operation_relay_step = original_wait
            gui.reconnect_gui_can = original_reconnect
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.STATE.relay_mode = original_relay_mode
            gui.OPERATION_RELAY_SETTLE_S = original_settle

        self.assertEqual(calls, [("task", "run_eol", {"product_barcode": "SO-1000", "motor_barcode": "0"})])
        self.assertFalse(any(call[0] == "relay" for call in calls))
        self.assertFalse(any(call[0] == "manual" for call in calls))

    def test_show_current_zero_does_not_use_task_operation_relays(self):
        calls: list[tuple[object, ...]] = []
        original_run_task = gui.run_task
        original_get_relay = gui._get_or_connect_relay_arduino
        original_set_relays = gui._confirmed_set_relays
        original_wait = gui.wait_for_manual_operation_relay_step
        original_reconnect = gui.reconnect_gui_can
        original_running = gui.STATE.running
        original_status = gui.STATE.status
        original_log = gui.STATE.log
        original_relay_mode = gui.STATE.relay_mode
        try:
            gui.run_task = lambda task_id, task_options=None: calls.append(("task", task_id, task_options)) or True
            gui._get_or_connect_relay_arduino = lambda timeout_s=8.0: calls.append(("connect",)) or object()
            gui._confirmed_set_relays = lambda arduino, mask, label, **kwargs: calls.append(("relay", arduino, mask, label))
            gui.wait_for_manual_operation_relay_step = lambda action, label: calls.append(("manual", action, label))
            gui.reconnect_gui_can = lambda node, bitrate=gui.DEFAULT_CAN_BITRATE: (True, "reconnected")
            gui.STATE.relay_mode = "automatic"
            gui.STATE.running = True

            gui.STATE._run_task("show_current_zero")
        finally:
            gui.run_task = original_run_task
            gui._get_or_connect_relay_arduino = original_get_relay
            gui._confirmed_set_relays = original_set_relays
            gui.wait_for_manual_operation_relay_step = original_wait
            gui.reconnect_gui_can = original_reconnect
            gui.STATE.running = original_running
            gui.STATE.status = original_status
            gui.STATE.log = original_log
            gui.STATE.relay_mode = original_relay_mode

        self.assertEqual(calls, [("task", "show_current_zero", None)])


if __name__ == "__main__":
    unittest.main()
