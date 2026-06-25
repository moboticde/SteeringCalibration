from pathlib import Path

import pandas as pd
import pytest

from managers.test_manager import TestRunner


class DummyConfig:
    def __init__(self, base_path: Path):
        self.BASE_PATH = str(base_path)


def write_conf_status(base_path: Path, rows: list[dict[str, object]]) -> Path:
    path = base_path / "04_Results" / "SN123_status.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        rows,
        columns=["Serial number", "Configuration", "Write Zero", "Calibration"],
    ).to_excel(path, sheet_name="conf", index=False)
    return path


def test_verify_configuration_processes_done_accepts_complete_row(tmp_path):
    write_conf_status(
        tmp_path,
        [
            {
                "Serial number": "SN122",
                "Configuration": "OK",
                "Write Zero": "-",
                "Calibration": "-",
            },
            {
                "Serial number": "SN123",
                "Configuration": "OK",
                "Write Zero": "OK",
                "Calibration": "OK",
            }
        ],
    )
    runner = TestRunner(
        arduino=None,
        config=DummyConfig(tmp_path),
        unit_serial_number="SN123",
    )

    assert runner.verify_configuration_processes_done() is True


def test_verify_configuration_processes_done_rejects_incomplete_latest_row(tmp_path):
    write_conf_status(
        tmp_path,
        [
            {
                "Serial number": "SN123",
                "Configuration": "OK",
                "Write Zero": "OK",
                "Calibration": "OK",
            },
            {
                "Serial number": "SN124",
                "Configuration": "OK",
                "Write Zero": "OK",
                "Calibration": "-",
            },
        ],
    )
    runner = TestRunner(
        arduino=None,
        config=DummyConfig(tmp_path),
        unit_serial_number="SN123",
    )

    with pytest.raises(RuntimeError, match="Configuration process is not complete"):
        runner.verify_configuration_processes_done()


@pytest.mark.parametrize(
    ("configuration", "write_zero", "calibration"),
    [
        ("OK", "OK", "-"),
        ("OK", "OK", "not OK"),
        ("OK", "-", "-"),
        ("OK", "not OK", "not OK"),
        ("-", "OK", "-"),
        ("not OK", "OK", "not OK"),
    ],
)
def test_verify_configuration_processes_done_rejects_latest_incomplete_combinations(
    tmp_path,
    configuration,
    write_zero,
    calibration,
):
    write_conf_status(
        tmp_path,
        [
            {
                "Serial number": "SN123",
                "Configuration": configuration,
                "Write Zero": write_zero,
                "Calibration": calibration,
            }
        ],
    )
    runner = TestRunner(
        arduino=None,
        config=DummyConfig(tmp_path),
        unit_serial_number="SN123",
    )

    with pytest.raises(RuntimeError, match="Configuration process is not complete"):
        runner.verify_configuration_processes_done()
