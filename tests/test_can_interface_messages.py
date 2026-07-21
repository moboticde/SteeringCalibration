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

    def test_configuration_preflight_accepts_standard_or_product_node(self):
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
        original_restart = gui.restart_controller_with_relays
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (True, "node 59 connected")
            gui.restart_controller_with_relays = lambda **kwargs: calls.append(("restart", kwargs)) or (False, "should not restart")
            gui.wait_for_manual_restart_and_reconnect = lambda *_args, **_kwargs: calls.append(("wait",)) or False

            gui.ensure_controller_ready_for_configuration(context)
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

        self.assertEqual(calls[0][0], "check")
        self.assertEqual(calls[0][1][0], 59)
        self.assertFalse(any(call[0] == "restart" for call in calls))
        self.assertFalse(any(call[0] == "wait" for call in calls))

    def test_configuration_preflight_tries_product_node_after_standard_node(self):
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
        original_restart = gui.restart_controller_with_relays
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            def fake_check(*args, **kwargs):
                calls.append(("check", args, kwargs))
                return (args[0] == 50, "connected" if args[0] == 50 else "missing")

            gui.check_can_connection = fake_check
            gui.restart_controller_with_relays = lambda **kwargs: calls.append(("restart", kwargs)) or (False, "should not restart")
            gui.wait_for_manual_restart_and_reconnect = lambda *_args, **_kwargs: calls.append(("wait",)) or False

            gui.ensure_controller_ready_for_configuration(context)
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

        check_calls = [call for call in calls if call[0] == "check"]
        self.assertEqual([call[1][0] for call in check_calls], [59, 50])
        self.assertEqual(check_calls[1][2]["can_bitrate"], 250)
        self.assertFalse(any(call[0] == "restart" for call in calls))

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
        original_load_config = gui.run_load_config
        original_check = gui.run_ssi_configuration_check_status
        try:
            gui.load_steering_script_with_node_fallback = lambda _context: calls.append(("script", _context)) or {"script_path": "SteeringScript.py"}
            gui.run_load_config = lambda *, node, can_bitrate: calls.append(("write_just_conf", node, can_bitrate)) or True
            gui.run_ssi_configuration_check_status = lambda *, node, can_bitrate: calls.append(("ssi_check", node, can_bitrate)) or (True, "No error")

            result = gui.run_load_script_config_details(context)
        finally:
            gui.load_steering_script_with_node_fallback = original_load_script
            gui.run_load_config = original_load_config
            gui.run_ssi_configuration_check_status = original_check

        self.assertTrue(result["ok"])
        self.assertEqual(
            calls,
            [
                ("script", context),
                ("write_just_conf", 50, 250),
                ("ssi_check", 50, 250),
            ],
        )

    def test_preflight_accepts_connected_product_node(self):
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
        original_restart = gui.restart_controller_with_relays_for_task
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (True, "connected")
            gui.restart_controller_with_relays_for_task = lambda *_args, **_kwargs: calls.append(("restart",)) or False
            gui.wait_for_manual_restart_and_reconnect = lambda *_args, **_kwargs: calls.append(("wait",)) or False

            gui.ensure_controller_ready_for_task(context, "Calibration")
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays_for_task = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

        self.assertEqual(calls[0][0], "check")
        self.assertFalse(any(call[0] == "wait" for call in calls))

    def test_preflight_falls_back_to_manual_restart_when_relay_restart_fails(self):
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
        original_restart = gui.restart_controller_with_relays_for_task
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (False, "missing")
            gui.restart_controller_with_relays_for_task = lambda _context, reason: calls.append(("restart", reason)) or False
            gui.wait_for_manual_restart_and_reconnect = lambda _context, reason: calls.append(("wait", reason)) or True

            gui.ensure_controller_ready_for_task(context, "Write Zero")
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays_for_task = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

        self.assertIn(("restart", "Controller is not reachable before Write Zero."), calls)
        self.assertIn(("wait", "Controller is not reachable before Write Zero."), calls)

    def test_preflight_uses_relay_restart_before_manual_confirmation(self):
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
        original_restart = gui.restart_controller_with_relays_for_task
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            gui.check_can_connection = lambda *args, **kwargs: calls.append(("check", args, kwargs)) or (False, "missing")
            gui.restart_controller_with_relays_for_task = lambda _context, reason: calls.append(("restart", reason)) or True
            gui.wait_for_manual_restart_and_reconnect = lambda *_args, **_kwargs: calls.append(("wait",)) or False

            gui.ensure_controller_ready_for_task(context, "Configuration")
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays_for_task = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

        self.assertIn(("restart", "Controller is not reachable before Configuration."), calls)
        self.assertFalse(any(call[0] == "wait" for call in calls))


    def test_preflight_raises_after_failed_manual_restart(self):
        context = gui.ProductContext(
            qr_code="S-1000-200",
            product_dir=Path("/tmp/S-1000-200-01"),
            can_bitrate=125,
            steering_node_id=50,
            zero_angle=270.0,
            script_path=Path("/tmp/S-1000-200-01/01_SwConfiguration/SteeringScript.py"),
        )
        original_check = gui.check_can_connection
        original_restart = gui.restart_controller_with_relays_for_task
        original_wait = gui.wait_for_manual_restart_and_reconnect
        try:
            gui.check_can_connection = lambda *args, **kwargs: (False, "missing")
            gui.restart_controller_with_relays_for_task = lambda *_args, **_kwargs: False
            gui.wait_for_manual_restart_and_reconnect = lambda *_args, **_kwargs: False

            with self.assertRaisesRegex(RuntimeError, "before TestCalibration"):
                gui.ensure_controller_ready_for_task(context, "TestCalibration")
        finally:
            gui.check_can_connection = original_check
            gui.restart_controller_with_relays_for_task = original_restart
            gui.wait_for_manual_restart_and_reconnect = original_wait

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
        try:
            gui.STATE.relay_arduino = FakeRelayArduino()
            gui.time.sleep = lambda _seconds: None
            gui._controller_reconnect_after_relay_power_on = (
                lambda **_kwargs: (False, 'CAN connection failed for node 50. (Device "can0" does not exist.)')
            )
            gui.restart_st_can0_service = lambda: (False, "Could not restart st-can0.service.")

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
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (True, "Restarted st-can0.service.")

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

    def test_gui_can_check_restarts_st_can0_and_retries_explicit_node(self):
        calls: list[tuple[object, ...]] = []
        original_check = gui.check_can_connection
        original_restart_can_service = gui.restart_st_can0_service
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
            gui.restart_st_can0_service = lambda: calls.append(("restart_st_can0",)) or (True, "Restarted st-can0.service.")
            gui.time.sleep = lambda seconds: calls.append(("sleep", seconds))

            connected, node, bitrate, message, context = gui._check_gui_can_with_st_can0_retry(
                explicit_target=True,
                node=50,
                bitrate=125,
            )
        finally:
            gui.check_can_connection = original_check
            gui.restart_st_can0_service = original_restart_can_service
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

    def test_operation_relay_mask_uses_controller_power_relays(self):
        self.assertEqual(
            gui.operation_relay_mask(),
            gui._relay_mask(1, 2, 3, 4, 7, 8),
        )



if __name__ == "__main__":
    unittest.main()
