from __future__ import annotations

import unittest

from drivers import driver_miControlF35 as mic_driver


class _FakeSdo:
    def __init__(self, steering_positions: list[int]) -> None:
        self.steering_positions = list(steering_positions)
        self.downloads: list[tuple[int, int, bytes]] = []

    def download(self, index: int, subindex: int, data: bytes) -> None:
        self.downloads.append((index, subindex, bytes(data)))

    def upload(self, index: int, subindex: int) -> bytes:
        if (index, subindex) == (0x3762, 0):
            if self.steering_positions:
                position = self.steering_positions.pop(0)
            else:
                position = 0
            return int(position).to_bytes(4, byteorder="little", signed=True)
        if (index, subindex) == (0x397A, 0x02):
            return int(0).to_bytes(4, byteorder="little", signed=True)
        return int(0).to_bytes(4, byteorder="little", signed=False)


class _FakeNode:
    def __init__(self, steering_positions: list[int]) -> None:
        self.sdo = _FakeSdo(steering_positions)


class MiControlZeroSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_sleep = mic_driver.time.sleep
        mic_driver.time.sleep = lambda _seconds: None

    def tearDown(self) -> None:
        mic_driver.time.sleep = self.original_sleep

    def test_save_ssi_absolute_zero_waits_until_zero_readback_before_saving(self):
        mic = mic_driver.MicontrolF35_CAN.__new__(mic_driver.MicontrolF35_CAN)
        mic.node_id = 50
        mic.added_node = _FakeNode([188, 97, 50, 25, 12, 6, 3, 3])
        mic.store_parameters = lambda: True

        self.assertTrue(mic.save_ssi_absolute_zero())

        downloads = mic.added_node.sdo.downloads
        zero_writes = [
            item
            for item in downloads
            if item == (0x3762, 0, int(0).to_bytes(4, "little", signed=True))
        ]
        saves = [
            item
            for item in downloads
            if item
            == (
                0x3970,
                0x08,
                mic_driver.CANOPEN_SAVE_SIGNATURE.to_bytes(
                    4,
                    byteorder="little",
                    signed=False,
                ),
            )
        ]
        self.assertGreaterEqual(len(zero_writes), 1)
        self.assertEqual(len(saves), 1)
        self.assertLess(downloads.index(zero_writes[0]), downloads.index(saves[0]))

    def test_save_ssi_absolute_zero_refuses_to_save_without_zero_readback(self):
        original_timeout = mic_driver.SSI_ZERO_WRITE_SETTLE_TIMEOUT_S
        original_attempts = mic_driver.SSI_ZERO_WRITE_ATTEMPTS
        try:
            mic_driver.SSI_ZERO_WRITE_SETTLE_TIMEOUT_S = 0.0
            mic_driver.SSI_ZERO_WRITE_ATTEMPTS = 2
            mic = mic_driver.MicontrolF35_CAN.__new__(mic_driver.MicontrolF35_CAN)
            mic.node_id = 50
            mic.added_node = _FakeNode([50, 50, 50, 50])
            mic.store_parameters = lambda: True

            self.assertFalse(mic.save_ssi_absolute_zero())

            saves = [
                item
                for item in mic.added_node.sdo.downloads
                if item[0:2] == (0x3970, 0x08)
            ]
            self.assertEqual(saves, [])
        finally:
            mic_driver.SSI_ZERO_WRITE_SETTLE_TIMEOUT_S = original_timeout
            mic_driver.SSI_ZERO_WRITE_ATTEMPTS = original_attempts


if __name__ == "__main__":
    unittest.main()
