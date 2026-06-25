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


if __name__ == "__main__":
    unittest.main()
