from __future__ import annotations

import types
import unittest

from drivers.driver_can import DriverCan


class DriverCanSocketcanTests(unittest.TestCase):
    def test_matching_bitrate_but_down_link_fails_before_canopen_connect(self):
        driver = DriverCan.__new__(DriverCan)
        driver.channel = "can0"
        driver.can_bitrate = 125000

        calls: list[tuple[str, ...]] = []

        def fake_run_ip(*args):
            calls.append(args)
            if args == ("-details", "link", "show", "can0"):
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "7: can0: <NOARP,ECHO> mtu 16 qdisc pfifo_fast "
                        "state DOWN mode DEFAULT group default qlen 10\n"
                        "    link/can\n"
                        "    can state STOPPED restart-ms 0\n"
                        "      bitrate 125000 sample-point 0.875\n"
                    ),
                    stderr="",
                )
            if args == ("link", "set", "can0", "up"):
                return types.SimpleNamespace(
                    returncode=2,
                    stdout="",
                    stderr="RTNETLINK answers: Operation not permitted\n",
                )
            raise AssertionError(f"Unexpected ip call: {args!r}")

        driver._run_ip = fake_run_ip

        with self.assertRaisesRegex(RuntimeError, "link is down"):
            driver.ensure_socketcan_bitrate()

        self.assertEqual(
            calls,
            [
                ("-details", "link", "show", "can0"),
                ("link", "set", "can0", "up"),
            ],
        )

    def test_matching_bitrate_and_up_link_returns_without_reconfiguring(self):
        driver = DriverCan.__new__(DriverCan)
        driver.channel = "can0"
        driver.can_bitrate = 125000

        calls: list[tuple[str, ...]] = []

        def fake_run_ip(*args):
            calls.append(args)
            return types.SimpleNamespace(
                returncode=0,
                stdout=(
                    "7: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast "
                    "state UP mode DEFAULT group default qlen 10\n"
                    "    link/can\n"
                    "    can state ERROR-ACTIVE restart-ms 0\n"
                    "      bitrate 125000 sample-point 0.875\n"
                ),
                stderr="",
            )

        driver._run_ip = fake_run_ip

        driver.ensure_socketcan_bitrate()

        self.assertEqual(calls, [("-details", "link", "show", "can0")])


if __name__ == "__main__":
    unittest.main()
