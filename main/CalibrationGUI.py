import contextlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from traceback import format_exc
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MANUFACTURING_ROOT = Path("/home/mobotic/Manufacturing")
EOL_CASE_ROOT = Path("/home/mobotic/Internal Projects/EOL-case/02_EOL_files")
EOL_CASE_MAIN_PATH = EOL_CASE_ROOT / "main" / "mobotic_EOL.py"
TRACTION_CALIBRATION_ROOT = Path("/home/mobotic/Internal Projects/TrCalibration-Linux")
TRACTION_CALIBRATION_WORKBOOK = MANUFACTURING_ROOT / "Calibration.xlsx"
EOL_CASE_IMPORT_PREFIXES = (
    "calibration",
    "drivers",
    "flash_config",
    "io_helpers",
    "logic",
    "managers",
    "processing",
    "utils",
)

from utils.interrupt_guard import install_deferred_keyboard_interrupt


BASE_DIR = PROJECT_ROOT
LOGO_PATH = BASE_DIR / "resources" / "mobotic-logo.png"
SERIAL_LAST4 = ""
DEFAULT_CAN_BITRATE = 125
STANDARD_NODE_ID = 59
DEFAULT_NODE_ID = STANDARD_NODE_ID
SCAN_OPTION_QR_CAMERA = "qr_camera"
SCAN_OPTION_QR_SCANNER = "qr_scanner"
SCAN_OPTION_BARCODE_SCANNER = "barcode_scanner"
SCAN_OPTION_MANUAL = "manual"
SCAN_OPTIONS = {
    SCAN_OPTION_QR_CAMERA,
    SCAN_OPTION_QR_SCANNER,
    SCAN_OPTION_BARCODE_SCANNER,
    SCAN_OPTION_MANUAL,
}
ZERO_ANGLE_DEG = 270.0
ZERO_VISUAL_TOLERANCE_DEG = 1.0
ANGLE_SETTLE_S = 2.0
ANGLE_SAMPLES = 20
ANGLE_TIMEOUT_S = 20.0
ANGLE_READ_ATTEMPTS = 2
SPIN_CHECK_DEG = 90.0
SPIN_CHECK_RPM = 200
SPIN_CHECK_TIMEOUT_S = 3.0
SPIN_FAILURE_ERROR = -1092
MANUAL_SPIN_DEFAULT_RPM = 1000
MANUAL_SPIN_STEP_RPM = 200
MANUAL_SPIN_MIN_RPM = 200
MANUAL_SPIN_MAX_RPM = 5000
ENCODER_COUNTS_PER_REV = 4096.0
ZERO_MOVE_RPM = 1000
ZERO_MOVE_SETTLE_S = 2.0
ZERO_MOVE_TIMEOUT_S = 25.0
ZERO_POSITION_TOLERANCE_COUNTS = 3
POWER_CYCLE_CONFIRM_TIMEOUT_S = 600.0
CONTROLLER_ENCODER_DIGITAL_OUTPUT = False
SSI_READY_STATUS = 9
RELAY_STO_A = 1
RELAY_STO_B = 2
RELAY_BRAKE = 3
RELAY_24V = 4
RELAY_RELE_PLUS = 7
RELAY_RELE_MINUS = 8
CONTROLLER_POWER_RELAYS = (
    RELAY_STO_A,
    RELAY_STO_B,
    RELAY_BRAKE,
    RELAY_24V,
    RELAY_RELE_PLUS,
    RELAY_RELE_MINUS,
)
CONTROLLER_POWER_CYCLE_OFF_S = 3.0
CONTROLLER_POWER_ON_SETTLE_S = 3.0
ST_CAN_SERVICE_NAME = "st-can0.service"
ST_CAN_SERVICE_RESTART_TIMEOUT_S = 10.0
ST_CAN_SERVICE_RESTART_SETTLE_S = 1.0


TASKS = {
    "run_all": "Run all program",
    "run_eol": "Run EOL",
    "traction_calibration": "Traction Calibration",
    "load_script_config": "Configuration",
    "load_script": "Load Script",
    "load_config": "Load Config",
    "start_calibration": "Calibration",
    "test_calibration": "TestCalibration",
    "show_current_zero": "Show Current Zero",
    "start_zeroing": "Write Zero",
}

TASKS_REQUIRING_TESTER_NAME = {"run_all", "run_eol"}


LEGACY_RUN_ALL_REPORT_COLUMNS = (
    "Serial number",
    "Configuration",
    "Write Zero",
    "Calibration",
)
RUN_ALL_REPORT_COLUMNS = (
    "Date",
    *LEGACY_RUN_ALL_REPORT_COLUMNS,
)
EOL_SEQUENCE_STEPS = (
    ("Configuration",),
    ("Write Zero", "Zeroing"),
    ("Calibration",),
)


def safe_filename_token(value: object, fallback: str = "run_all") -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    token = token.strip("._")
    return token[:80] or fallback


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - 64)
    return index


def _xlsx_cell(row_idx: int, col_idx: int, value: object) -> str:
    cell_ref = f"{_xlsx_column_name(col_idx)}{row_idx}"
    text = "" if value is None else str(value)
    return (
        f'<c r="{cell_ref}" t="inlineStr">'
        f"<is><t>{escape(text)}</t></is>"
        f"</c>"
    )


def read_conf_xlsx_rows(path: Path) -> list[list[str]]:
    if not path.is_file():
        return []
    try:
        with zipfile.ZipFile(path) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml")
    except zipfile.BadZipFile:
        return []
    except Exception as exc:
        print(f"[WARN] Could not read existing result workbook {path}: {exc}")
        return []

    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        root = ET.fromstring(sheet_xml)
    except ET.ParseError as exc:
        print(f"[WARN] Could not parse existing result workbook {path}: {exc}")
        return []

    parsed_rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values_by_col: dict[int, str] = {}
        for cell in row.findall("x:c", ns):
            cell_ref = cell.attrib.get("r", "")
            col_idx = _xlsx_column_index(cell_ref)
            if col_idx <= 0:
                continue
            text = "".join(
                node.text or ""
                for node in cell.findall(".//x:is/x:t", ns)
            )
            values_by_col[col_idx] = text
        if not values_by_col:
            parsed_rows.append([])
            continue
        max_col = max(values_by_col)
        parsed_rows.append([values_by_col.get(col_idx, "") for col_idx in range(1, max_col + 1)])
    return parsed_rows


def write_conf_xlsx_rows(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    sheet_rows = []
    for row_idx, row in enumerate(rows, 1):
        cells = "".join(
            _xlsx_cell(row_idx, col_idx, value)
            for col_idx, value in enumerate(row, 1)
        )
        sheet_rows.append(f'<row r="{row_idx}">{cells}</row>')

    col_count = max((len(row) for row in rows), default=2)
    col_widths = []
    for col_idx in range(1, col_count + 1):
        width = 24 if col_idx <= 4 else 32
        if col_idx in (12, 15):
            width = 80
        col_widths.append(
            f'<col min="{col_idx}" max="{col_idx}" width="{width}" customWidth="1"/>'
        )

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<cols>{''.join(col_widths)}</cols>"
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="conf" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _row_values_by_header(header: list[str], row: list[object]) -> dict[str, object]:
    return {
        str(column): row[idx] if idx < len(row) else ""
        for idx, column in enumerate(header)
    }


def normalize_conf_report_rows(rows: list[list[str]]) -> list[list[object]]:
    header = list(RUN_ALL_REPORT_COLUMNS)
    if not rows:
        return [header]

    existing_header = [str(value) for value in rows[0]]
    if existing_header == header:
        return rows

    if existing_header == list(LEGACY_RUN_ALL_REPORT_COLUMNS):
        normalized: list[list[object]] = [header]
        for row in rows[1:]:
            values = _row_values_by_header(existing_header, row)
            normalized.append(["", *[values.get(column, "") for column in LEGACY_RUN_ALL_REPORT_COLUMNS]])
        return normalized

    print(
        "[WARN] Existing result workbook has unexpected columns; "
        "rewriting report table."
    )
    return [header]


def _conf_status_ok(value: object) -> bool:
    return str(value or "").strip().lower() == "ok"


def product_unit_prefix(value: object) -> str:
    match = re.match(r"\s*([A-Za-z]+)", str(value or ""))
    return match.group(1).upper() if match else ""


def is_so_unit(value: object) -> bool:
    return product_unit_prefix(value) == "SO"


def status_workbook_path_for_qr(product_dir: Path, qr_code: object) -> Path:
    return product_dir / "04_Results" / f"{safe_filename_token(qr_code, 'barcode')}_status.xlsx"


def done_workbook_path_for_qr(product_dir: Path, qr_code: object) -> Path:
    return product_dir / "04_Results" / f"{safe_filename_token(qr_code, 'barcode')}_done.xlsx"


def eol_sequence_status_from_rows(rows: list[list[object]]) -> tuple[bool, str]:
    if not rows:
        return False, "No status workbook rows found."

    header = [str(value) for value in rows[0]]
    missing = [
        labels[0]
        for labels in EOL_SEQUENCE_STEPS
        if not any(label in header for label in labels)
    ]
    if missing:
        return False, f"Status workbook is missing columns: {', '.join(missing)}."

    completed_step = 0
    for row in rows[1:]:
        values = _row_values_by_header(header, row)
        if completed_step == 0 and any(_conf_status_ok(values.get(label)) for label in EOL_SEQUENCE_STEPS[0]):
            completed_step = 1
        if completed_step == 1 and any(_conf_status_ok(values.get(label)) for label in EOL_SEQUENCE_STEPS[1]):
            completed_step = 2
        if completed_step == 2 and any(_conf_status_ok(values.get(label)) for label in EOL_SEQUENCE_STEPS[2]):
            completed_step = 3
            return True, "EOL enabled: Configuration, Zeroing, and Calibration are OK in sequence."

    labels = ("Configuration", "Zeroing", "Calibration")
    next_label = labels[min(completed_step, len(labels) - 1)]
    return False, f"EOL disabled until {next_label} is OK in sequence."


def eol_sequence_status_for_product(product_dir: Path | None, qr_code: object) -> tuple[bool, str, str]:
    if product_dir is None or not str(qr_code or "").strip():
        return False, "Scan product first.", ""

    done_path = done_workbook_path_for_qr(product_dir, qr_code)
    if done_path.is_file():
        return True, f"EOL already done: {done_path.name}", str(done_path)

    path = status_workbook_path_for_qr(product_dir, qr_code)
    if not path.is_file():
        return False, f"EOL disabled: status workbook not found: {path.name}", str(path)

    rows = normalize_conf_report_rows(read_conf_xlsx_rows(path))
    ok, message = eol_sequence_status_from_rows(rows)
    return ok, message, str(path)


def eol_done_report_for_product(product_dir: Path | None, qr_code: object) -> Path | None:
    if product_dir is None or not str(qr_code or "").strip():
        return None
    path = done_workbook_path_for_qr(product_dir, qr_code)
    return path if path.is_file() else None


def _workflow_step_state(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "-":
        return "idle"
    return "pass" if _conf_status_ok(text) else "fail"


def conf_workflow_status_from_rows(rows: list[list[object]]) -> dict[str, dict[str, str]]:
    if not rows:
        return {}
    header = [str(value) for value in rows[0]]
    steps = {
        "load_script_config": ("Configuration",),
        "start_zeroing": ("Write Zero", "Zeroing"),
        "start_calibration": ("Calibration",),
    }
    status: dict[str, dict[str, str]] = {}
    for step, labels in steps.items():
        latest_value = ""
        latest_date = ""
        for row in rows[1:]:
            values = _row_values_by_header(header, row)
            for label in labels:
                value = values.get(label, "")
                clean_value = str(value or "").strip()
                if clean_value and clean_value != "-":
                    latest_value = str(value)
                    latest_date = str(values.get("Date", "") or "")
        status[step] = {
            "state": _workflow_step_state(latest_value),
            "value": latest_value or "-",
            "time": latest_date or "-",
        }
    return status


def conf_workflow_status_for_product(
    product_dir: Path | None,
    qr_code: object,
) -> tuple[dict[str, dict[str, str]], str]:
    if product_dir is None or not str(qr_code or "").strip():
        return {}, ""
    path = status_workbook_path_for_qr(product_dir, qr_code)
    if not path.is_file():
        return {}, str(path)
    rows = normalize_conf_report_rows(read_conf_xlsx_rows(path))
    return conf_workflow_status_from_rows(rows), str(path)


DD_CALIBRATION_BARCODE_MARKERS = (
    "1126788",
    "1058534",
)
TRACTION_CALIBRATION_COLUMNS = (
    "Date",
    "Motor Number",
    "Program",
    "Calibration status",
)
CALIBRATION_PARAM_RE = re.compile(
    r"SinOff:\s*(-?\d+)\s*\|\s*"
    r"CosOff:\s*(-?\d+)\s*\|\s*"
    r"GainC:\s*(-?\d+)\s*\|\s*"
    r"Harm4:\s*(-?\d+)\s*\|\s*"
    r"RPM:\s*(-?\d+)",
    re.I,
)


def choose_traction_calibration_program(barcode: object) -> str:
    text = str(barcode or "").upper()
    if any(marker in text for marker in DD_CALIBRATION_BARCODE_MARKERS):
        return "DD"
    return "ST"


def choose_traction_calibration_script(barcode: object) -> Path:
    program = choose_traction_calibration_program(barcode)
    script_name = "DD_Calibration.py" if program == "DD" else "ST_Calibration.py"
    return TRACTION_CALIBRATION_ROOT / script_name


def parse_attempt_9_calibration_zero(output: str) -> tuple[bool, dict[str, int] | None]:
    lines = str(output or "").splitlines()
    attempt_9_seen = False
    attempt_9_params: dict[str, int] | None = None
    for line in lines:
        if re.search(r"Running\s+Calibration\s+Attempt\s+9\b", line, re.I):
            attempt_9_seen = True
            attempt_9_params = None
            continue
        if not attempt_9_seen:
            continue
        match = CALIBRATION_PARAM_RE.search(line)
        if match:
            attempt_9_params = {
                "SinOff": int(match.group(1)),
                "CosOff": int(match.group(2)),
                "GainC": int(match.group(3)),
                "Harm4": int(match.group(4)),
                "RPM": int(match.group(5)),
            }
        elif re.search(r"Running\s+Calibration\s+Attempt\s+\d+\b", line, re.I):
            attempt_9_seen = False

    if attempt_9_params is None:
        return False, None
    return all(attempt_9_params[key] == 0 for key in ("SinOff", "CosOff", "GainC", "Harm4")), attempt_9_params


def append_traction_calibration_log(
    *,
    workbook_path: Path,
    calibration_date: str,
    barcode: str,
    program: str,
    status: str,
) -> None:
    rows = read_conf_xlsx_rows(workbook_path)
    header = list(TRACTION_CALIBRATION_COLUMNS)
    if not rows or rows[0] != header:
        rows = [header]
    rows.append([calibration_date, barcode, program, status])
    write_conf_xlsx_rows(workbook_path, rows)


def run_traction_calibration(motor_barcode: object) -> bool:
    barcode = str(motor_barcode or "").strip()
    if not barcode:
        raise RuntimeError("Motor barcode is required for traction calibration.")

    script_path = choose_traction_calibration_script(barcode)
    program = choose_traction_calibration_program(barcode)
    if not script_path.is_file():
        raise FileNotFoundError(f"Traction calibration script not found: {script_path}")

    print(f"[INFO] Running traction calibration program: {program} ({script_path.name})")
    print(f"[INFO] Motor barcode: {barcode}")
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(TRACTION_CALIBRATION_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n")

    attempt_zero, attempt_params = parse_attempt_9_calibration_zero(
        f"{completed.stdout}\n{completed.stderr}"
    )
    status = "PASS" if completed.returncode == 0 and attempt_zero else "FAIL"
    append_traction_calibration_log(
        workbook_path=TRACTION_CALIBRATION_WORKBOOK,
        calibration_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        barcode=barcode,
        program=program,
        status=status,
    )
    params_text = f" Attempt 9 params: {attempt_params}." if attempt_params else " Attempt 9 params missing."
    print(
        f"[INFO] Traction calibration status: {status}. "
        f"Exit code: {completed.returncode}.{params_text}"
    )
    return status == "PASS"


class RunAllReport:
    def __init__(self, product_dir: Path, qr_code: object, node: int, desired_angle: float):
        timestamp = datetime.now()
        self.qr_code = str(qr_code or "")
        self.product_dir = product_dir
        result_dir = product_dir / "04_Results"
        filename = f"{safe_filename_token(qr_code, 'barcode')}_status.xlsx"
        self.path = result_dir / filename
        rows = normalize_conf_report_rows(read_conf_xlsx_rows(self.path))
        header = list(RUN_ALL_REPORT_COLUMNS)
        self.rows = rows
        self.values = {
            "Date": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "Serial number": "-",
            "Configuration": "-",
            "Write Zero": "-",
            "Calibration": "-",
        }
        self.row_idx = len(self.rows)
        self.rows.append(self._values_to_row())
        self.save()

    def update(self, **values: object) -> None:
        changed = False
        for key, value in values.items():
            if key not in RUN_ALL_REPORT_COLUMNS:
                continue
            text_value = "" if value is None else str(value)
            if str(self.values.get(key, "")) != text_value:
                self.values[key] = text_value
                changed = True
        if changed:
            self.rows[self.row_idx] = self._values_to_row()
            self.save()

    def _values_to_row(self) -> list[str]:
        return [str(self.values.get(column, "")) for column in RUN_ALL_REPORT_COLUMNS]

    def save(self) -> None:
        write_conf_xlsx_rows(self.path, self.rows)


@dataclass(frozen=True)
class ProductContext:
    qr_code: str
    product_dir: Path
    can_bitrate: int
    steering_node_id: int
    zero_angle: float
    script_path: Path

    def script_info(self) -> dict[str, object]:
        return {
            "qr_code": self.qr_code,
            "product_dir": str(self.product_dir),
            "script_path": str(self.script_path),
        }


@dataclass(frozen=True)
class ProductSpecCache:
    qr_code: str
    product_dir: Path
    spec_path: Path
    params: dict[str, object]
    context: ProductContext | None
    steering_available: bool
    message: str


def _xlsx_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext())


def read_product_spec_parameters(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"Product specification not found: {path}")

    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    params: dict[str, object] = {}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [_xlsx_text(si) for si in root.findall("x:si", ns)]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        for sheet in workbook.findall("x:sheets/x:sheet", ns):
            rel_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if not rel_id or rel_id not in targets:
                continue
            target = targets[rel_id].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(archive.read(target))
            for row in root.findall(".//x:sheetData/x:row", ns):
                values: list[object] = []
                for cell in row.findall("x:c", ns):
                    value = cell.find("x:v", ns)
                    inline = cell.find("x:is", ns)
                    if cell.attrib.get("t") == "s" and value is not None:
                        values.append(shared[int(value.text or "0")])
                    elif cell.attrib.get("t") == "inlineStr":
                        values.append(_xlsx_text(inline))
                    elif value is not None:
                        values.append(value.text or "")
                    else:
                        values.append("")
                if len(values) >= 2 and str(values[0]).strip():
                    params[str(values[0]).strip()] = values[1]
    return params


def _require_int_param(params: dict[str, object], key: str, minimum: int, maximum: int) -> int:
    raw = params.get(key)
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"Missing required product specification value: {key}")
    try:
        value = int(float(str(raw).strip()))
    except ValueError as exc:
        raise ValueError(f"Invalid product specification value for {key}: {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise ValueError(
            f"Product specification value {key} must be between {minimum} and {maximum}: {value}"
        )
    return value


def _require_float_param(params: dict[str, object], key: str) -> float:
    raw = params.get(key)
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"Missing required product specification value: {key}")
    try:
        return float(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid product specification value for {key}: {raw!r}") from exc


def find_product_spec_path(product_dir: Path) -> Path:
    direct = product_dir / "ProductSpecifications_V2.xlsx"
    if direct.is_file():
        return direct

    child_matches = sorted(product_dir.glob("*/ProductSpecifications_V2.xlsx"))
    if child_matches:
        return child_matches[0]

    nested_matches = sorted(product_dir.rglob("ProductSpecifications_V2.xlsx"))
    if nested_matches:
        return nested_matches[0]

    raise FileNotFoundError(
        f"Product specification not found under product folder: {product_dir}"
    )


def _normalized_product_key(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()


def resolve_product_family_dir(
    qr_code: object,
    product_dir_raw: Path | str,
    product_base: Path | str | None,
) -> Path:
    product_dir = Path(product_dir_raw).expanduser().resolve()
    if product_base is None:
        return product_dir

    base_dir = Path(product_base).expanduser().resolve()
    try:
        relative_parts = product_dir.relative_to(base_dir).parts
    except ValueError:
        return product_dir

    if not relative_parts:
        return product_dir

    family_dir = base_dir / relative_parts[0]
    qr_key = _normalized_product_key(qr_code)
    family_key = _normalized_product_key(family_dir.name)
    if family_key and qr_key.startswith(family_key):
        return family_dir
    return product_dir


def configured_product_base_path(config_data: dict[str, object] | None) -> Path | None:
    if not isinstance(config_data, dict):
        return None
    paths = config_data.get("paths", {})
    if not isinstance(paths, dict):
        return None
    product_base = paths.get("product_base")
    if not product_base:
        return None
    return Path(str(product_base))


def product_family_name_from_qr(qr_code: object) -> str:
    parts = str(qr_code or "").strip().split("-")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return "-".join(parts[:2])
    return str(qr_code or "").strip()


def product_search_roots(config_data: dict[str, object] | None) -> list[Path]:
    roots: list[Path] = []
    configured_root = configured_product_base_path(config_data)
    if configured_root is not None:
        roots.append(configured_root)
        roots.append(configured_root / "01_Products")
    roots.append(MANUFACTURING_ROOT / "01_Products")
    roots.append(MANUFACTURING_ROOT)

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = os.fspath(root.expanduser())
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def find_product_family_folder_from_roots(
    qr_code: object,
    config_data: dict[str, object] | None,
) -> Path | None:
    qr_key = _normalized_product_key(qr_code)
    family_name = product_family_name_from_qr(qr_code)
    family_key = _normalized_product_key(family_name)
    for root in product_search_roots(config_data):
        root = root.expanduser()
        if not root.is_dir():
            continue

        direct_candidates = [root / family_name] if family_name else []
        try:
            direct_candidates.extend(
                child for child in root.iterdir() if child.is_dir()
            )
        except OSError:
            continue

        matches = []
        for candidate in direct_candidates:
            if not candidate.is_dir():
                continue
            candidate_key = _normalized_product_key(candidate.name)
            if candidate_key and (
                qr_key.startswith(candidate_key)
                or (family_key and candidate_key == family_key)
            ):
                matches.append(candidate)
        if matches:
            return max(matches, key=lambda path: len(path.name)).resolve()
    return None


def _product_value_present(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in {"nan", "none", "null", "-"}


def has_steering_information(params: dict[str, object]) -> bool:
    if not _product_value_present(params.get("Steering Controller Type")):
        return False
    try:
        _require_int_param(params, "Steering Node ID", 1, 127)
    except Exception:
        return False
    return True


def resolve_product_scan_text(scan_text: object) -> ProductSpecCache:
    from io_helpers import find_product_folder

    qr_code = str(scan_text or "").strip()
    if not qr_code:
        raise RuntimeError("Product code is empty.")

    old_cwd = os.getcwd()
    try:
        product_dir_raw = find_product_folder.find_config(qr_code)
    finally:
        try:
            os.chdir(old_cwd)
        except Exception:
            pass
    product_base = configured_product_base_path(getattr(find_product_folder, "config", None))
    if not product_dir_raw:
        product_dir = find_product_family_folder_from_roots(
            qr_code,
            getattr(find_product_folder, "config", None),
        )
        if product_dir is None:
            raise RuntimeError(f"No product folder found for QR code: {qr_code}")
    else:
        product_dir = resolve_product_family_dir(
            qr_code,
            Path(product_dir_raw),
            product_base,
        )
    spec_path = find_product_spec_path(product_dir)
    params = read_product_spec_parameters(spec_path)

    if not has_steering_information(params):
        message = (
            f"{qr_code}: product specification has no steering information. "
            "Steering tab disabled."
        )
        print(f"[INFO] {message}")
        return ProductSpecCache(
            qr_code=str(qr_code),
            product_dir=product_dir,
            spec_path=spec_path,
            params=params,
            context=None,
            steering_available=False,
            message=message,
        )

    can_bitrate = _require_int_param(params, "CAN Baudrate", 1, 1000)
    steering_node_id = _require_int_param(params, "Steering Node ID", 1, 127)
    zero_angle = _require_float_param(params, "Zero angle")
    script_path = product_dir / "01_SwConfiguration" / "SteeringScript.py"
    if not script_path.is_file():
        raise FileNotFoundError(f"SteeringScript.py not found: {script_path}")

    context = ProductContext(
        qr_code=str(qr_code),
        product_dir=product_dir,
        can_bitrate=can_bitrate,
        steering_node_id=steering_node_id,
        zero_angle=zero_angle,
        script_path=script_path,
    )
    print(
        "[INFO] Product context -> "
        f"qr={context.qr_code} product_dir={context.product_dir} "
        f"bitrate={context.can_bitrate} node={context.steering_node_id} "
        f"zero_angle={context.zero_angle:.2f}"
    )
    return ProductSpecCache(
        qr_code=str(qr_code),
        product_dir=product_dir,
        spec_path=spec_path,
        params=params,
        context=context,
        steering_available=True,
        message=f"{context.qr_code}: steering product specification loaded.",
    )


def scan_product_context() -> ProductSpecCache:
    from drivers.driver_QRreader import run_qr_reader

    print("[INFO] Scanning product QR code.")
    qr_code = run_qr_reader(show=True, once=True, return_first=True)
    if not qr_code:
        raise RuntimeError("QR code could not be read from camera.")
    return resolve_product_scan_text(qr_code)


def get_cached_or_scan_product_context() -> ProductContext:
    cached = STATE.get_cached_product_context()
    if cached is not None:
        return cached
    with STATE.lock:
        if STATE.product_scan_completed and STATE.steering_available is False:
            raise RuntimeError(STATE.product_scan_message)
        if STATE.product_scan_running:
            raise RuntimeError("Product QR/specification scan is still running.")

    result = scan_product_context()
    STATE.set_product_scan_result(result)
    if result.context is None:
        raise RuntimeError(result.message)
    return result.context


def resolve_product_context() -> ProductContext:
    return get_cached_or_scan_product_context()


HTML_TEMPLATE_PATH = Path(__file__).with_name("CalibrationGUI.html")


def load_html_template() -> str:
    return HTML_TEMPLATE_PATH.read_text(encoding="utf-8")


HTML = load_html_template()


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.log = ""
        self.status = "Switch On Power Supply"
        self.quality = "Calibration quality: no result yet."
        self.quality_ok: bool | None = None
        self._quality_fields: dict[str, str] = {}
        self.status_lines: list[str] = ["Switch On Power Supply"]
        self.activity_label = "Switch On Power Supply"
        self.activity_step = "Power and CAN are required before steering tasks."
        self.activity_state = "idle"
        self.has_error = False
        self.running = False
        self.worker: threading.Thread | None = None
        self.awaiting_power_cycle = False
        self.latest_manual_seq = 0
        self.manual_requests_in_flight = 0
        self.can_check_running = False
        self.can_connection_ok: bool | None = None
        self.can_connection_node: int | None = None
        self.can_connection_bitrate: int = DEFAULT_CAN_BITRATE
        self.can_connection_message = "Switch On Power Supply"
        self.manual_can = None
        self.manual_mic = None
        self.relay_arduino = None
        self.relay_connecting = False
        self.relay_connection_ok: bool | None = None
        self.relay_connection_message = "Relay Arduino not connected yet."
        self.controller_enabled = False
        self.controller_error_code: int | None = None
        self.controller_error_active = False
        self.current_barcode = ""
        self.current_product_dir: Path | None = None
        self.current_product_context: ProductContext | None = None
        self.current_product_params: dict[str, object] = {}
        self.current_product_spec_path: Path | None = None
        self.product_scan_running = False
        self.product_scan_completed = False
        self.awaiting_product_scan = False
        self.scan_option = SCAN_OPTION_QR_CAMERA
        self.product_scan_message = "Product QR not scanned yet."
        self.product_scan_error = ""
        self.steering_available: bool | None = None
        self.current_report: RunAllReport | None = None
        self._power_cycle_event = threading.Event()

    def append_log(self, text: str) -> None:
        if not text:
            return
        with self.lock:
            self.log += text

    def reset_quality(self) -> None:
        with self.lock:
            self.quality = "Calibration quality: running..."
            self.quality_ok = None
            self._quality_fields = {}

    def append_status(
        self,
        text: str,
        is_error: bool = False,
        *,
        mark_error: bool = True,
    ) -> None:
        clean = text.strip()
        if not clean:
            return
        with self.lock:
            self.activity_step = clean
            self.activity_state = "fail" if is_error else ("running" if self.running else "idle")
            self.status_lines = [clean]
            if is_error and mark_error:
                self.has_error = True

    def set_activity(
        self,
        label: str | None = None,
        step: str | None = None,
        state: str = "running",
        *,
        mark_error: bool = True,
    ) -> None:
        with self.lock:
            if label:
                self.activity_label = label
                self.status = label
            if step:
                self.activity_step = step
                self.status_lines = [step]
            self.activity_state = state
            if state == "fail" and mark_error:
                self.has_error = True
            elif state in {"idle", "done"} and not self.controller_error_active:
                self.has_error = False

    def finish_activity(self, label: str, step: str, ok: bool) -> None:
        self.set_activity(label, step, "done" if ok else "fail")

    def clear_log(self) -> None:
        with self.lock:
            self.log = ""
            self.status_lines = ["Ready."]
            self.activity_label = "Ready"
            self.activity_step = "Choose one operation."
            self.activity_state = "idle"
            self.has_error = False
            self.controller_error_active = False

    def observe_log_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return

        status_message, is_error = self._status_message_from_log_line(stripped)
        if status_message:
            self.append_status(status_message, is_error=is_error, mark_error=False)
        self._observe_quality_line(stripped)

    def _status_message_from_log_line(self, stripped: str) -> tuple[str | None, bool]:
        if stripped.startswith("==="):
            return None, False

        result_match = re.match(r"\[RESULT\]\s+(.+?)\s+ok=(True|False)(?:\s+error=(.*))?$", stripped)
        if result_match:
            name = self._humanize_result_name(result_match.group(1))
            ok = result_match.group(2) == "True"
            error = (result_match.group(3) or "").strip()
            if ok:
                return f"{name} passed.", False
            if error:
                return f"{name} failed: {error}", True
            return f"{name} failed.", True

        prefixed_match = re.match(r"\[(INFO|WARN|ERROR|STATUS|RESULT)\]\s*(.*)", stripped)
        if prefixed_match:
            level, message = prefixed_match.groups()
            message = message.strip()
            if not message:
                return None, False
            if level == "ERROR":
                return f"Issue: {message}", True
            if level == "STATUS":
                return message, False
            return None, False

        if "completed" in stripped.lower():
            return stripped, False

        return None, False

    def _humanize_result_name(self, raw_name: str) -> str:
        abbreviations = {"can": "CAN", "ssi": "SSI", "mu": "MU", "mpu": "MPU"}
        words = raw_name.replace("_", " ").strip().split()
        human_words = [
            abbreviations.get(word.lower(), word.lower())
            for word in words
        ]
        if human_words and human_words[0] not in abbreviations.values():
            human_words[0] = human_words[0].capitalize()
        return " ".join(human_words) or "Operation"

    def _update_controller_error_state_locked(self, error_code: int | None) -> None:
        self.controller_error_code = error_code
        try:
            self.controller_error_active = int(error_code) != 0
        except (TypeError, ValueError):
            self.controller_error_active = error_code not in (None, "", 0)

    def _observe_quality_line(self, stripped: str) -> None:
        match = re.search(r"quality_status=(PASS|FAIL)", stripped)
        if match:
            self._update_quality_field("status", match.group(1))
            return

        match = re.search(
            r"max_abs_analog_residual=([+-]?\d+(?:\.\d+)?) LSB .*final cap ([+-]?\d+(?:\.\d+)?)",
            stripped,
        )
        if match:
            self._update_quality_field(
                "residual",
                f"{float(match.group(1)):.4f} LSB / cap {float(match.group(2)):.4f}",
            )
            return

        match = re.search(
            r"nonius_phase_margin=([+-]?\d+(?:\.\d+)?)% .*max ([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_margin",
                f"{float(match.group(1)):.2f}% / max {float(match.group(2)):.2f}%",
            )
            return

        match = re.search(
            r"upper_phase_clearance=([+-]?\d+(?:\.\d+)?)% lower_phase_clearance=([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_clearance",
                f"upper {float(match.group(1)):.2f}%, lower {float(match.group(2)):.2f}%",
            )
            return

        match = re.search(
            r"upper_phase_margin=([+-]?\d+(?:\.\d+)?)% lower_phase_margin=([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_clearance",
                f"upper {float(match.group(1)):.2f}%, lower {float(match.group(2)):.2f}%",
            )
            return

        if "quality_gate_reason=" in stripped:
            self._update_quality_field("reason", stripped.split("quality_gate_reason=", 1)[1])
            return

        match = re.search(r"\[RESULT\] (?:full calibration|test calibration) ok=(True|False)", stripped)
        if match:
            self._update_quality_field(
                "overall",
                "PASS" if match.group(1) == "True" else "FAIL",
            )

    def _update_quality_field(self, key: str, value: str) -> None:
        with self.lock:
            self._quality_fields[key] = value
            status = self._quality_fields.get("overall") or self._quality_fields.get("status")
            if status == "PASS":
                self.quality_ok = True
            elif status == "FAIL":
                self.quality_ok = False

            parts = []
            if status:
                parts.append(f"Calibration quality: {status}")
            else:
                parts.append("Calibration quality: running...")
            if "residual" in self._quality_fields:
                parts.append(f"Residual: {self._quality_fields['residual']}")
            if "phase_margin" in self._quality_fields:
                parts.append(f"Phase margin: {self._quality_fields['phase_margin']}")
            if "phase_clearance" in self._quality_fields:
                parts.append(f"Phase clearance: {self._quality_fields['phase_clearance']}")
            if "reason" in self._quality_fields:
                parts.append(f"Reason: {self._quality_fields['reason']}")
            self.quality = "\n".join(parts)

    def mark_quality_failed_if_pending(self, reason: str) -> None:
        with self.lock:
            if self.quality_ok is None and self.quality == "Calibration quality: running...":
                self.quality_ok = False
                self.quality = f"Calibration quality: FAIL\nReason: {reason}"

    def snapshot(self) -> dict[str, object]:
        self.refresh_controller_error_code()
        controller_power_on = controller_power_relays_are_on()
        with self.lock:
            product_dir = self.current_product_dir
            product_qr_code = self.current_barcode
        unit_is_so = is_so_unit(product_qr_code)
        traction_available = bool(product_qr_code) and not unit_is_so
        conf_workflow_status, conf_status_path = conf_workflow_status_for_product(
            product_dir,
            product_qr_code,
        )
        eol_done_report_path = eol_done_report_for_product(product_dir, product_qr_code)
        if unit_is_so:
            eol_available, eol_status_message, eol_status_path = eol_sequence_status_for_product(
                product_dir,
                product_qr_code,
            )
        else:
            eol_available = False
            eol_status_message = (
                "EOL disabled for non-SO units."
                if product_qr_code
                else "Scan product first."
            )
            eol_status_path = ""
        with self.lock:
            return {
                "log": self.log,
                "status": self.status,
                "quality": self.quality,
                "quality_ok": self.quality_ok,
                "status_feed": "\n".join(self.status_lines),
                "activity": {
                    "label": self.activity_label,
                    "step": self.activity_step,
                    "state": self.activity_state,
                },
                "has_error": self.has_error or self.controller_error_active,
                "running": self.running,
                "awaiting_power_cycle": self.awaiting_power_cycle,
                "can_check_running": self.can_check_running,
                "can_connection_ok": self.can_connection_ok,
                "can_connection_node": self.can_connection_node,
                "can_connection_bitrate": self.can_connection_bitrate,
                "can_connection_message": self.can_connection_message,
                "controller_enabled": self.controller_enabled,
                "controller_error_code": self.controller_error_code,
                "relay_connecting": self.relay_connecting,
                "relay_connection_ok": self.relay_connection_ok,
                "relay_connection_message": self.relay_connection_message,
                "controller_power_relays_on": controller_power_on,
                "product_scan_running": self.product_scan_running,
                "product_scan_completed": self.product_scan_completed,
                "awaiting_product_scan": self.awaiting_product_scan,
                "scan_option": self.scan_option,
                "product_scan_message": self.product_scan_message,
                "product_scan_error": self.product_scan_error,
                "product_qr_code": self.current_barcode,
                "product_unit": product_unit_prefix(self.current_barcode),
                "product_spec_path": (
                    str(self.current_product_spec_path)
                    if self.current_product_spec_path is not None
                    else ""
                ),
                "steering_available": self.steering_available,
                "traction_available": traction_available,
                "eol_available": eol_available,
                "eol_status_message": eol_status_message,
                "eol_status_path": eol_status_path or conf_status_path,
                "eol_done": eol_done_report_path is not None,
                "eol_report_name": eol_done_report_path.name if eol_done_report_path else "",
                "eol_report_path": str(eol_done_report_path) if eol_done_report_path else "",
                "eol_report_url": "/eol-report" if eol_done_report_path else "",
                "conf_workflow_status": conf_workflow_status,
                "conf_status_path": conf_status_path,
            }

    def refresh_controller_error_code(self) -> None:
        with self.lock:
            mic = self.manual_mic
            should_read = (
                self.can_connection_ok is True
                and mic is not None
                and not self.running
                and self.manual_requests_in_flight == 0
                and not self.can_check_running
            )
            if not should_read:
                if self.can_connection_ok is not True:
                    self._update_controller_error_state_locked(None)
                return

        try:
            error_code = mic.get_error_code()
        except Exception:
            error_code = None

        with self.lock:
            if self.manual_mic is mic and self.can_connection_ok is True:
                self._update_controller_error_state_locked(error_code)

    def request_power_cycle_confirmation(self, timeout_s: float) -> bool:
        self._power_cycle_event.clear()
        with self.lock:
            self.awaiting_power_cycle = True
            self.status = "Waiting for power-cycle confirmation."
            self.activity_label = "Waiting for power cycle"
            self.activity_step = "Press Continue after power is back on."
            self.activity_state = "running"
            self.status_lines = [self.activity_step]
        confirmed = self._power_cycle_event.wait(timeout_s)
        with self.lock:
            self.awaiting_power_cycle = False
        return confirmed

    def confirm_power_cycle(self) -> bool:
        with self.lock:
            if not self.awaiting_power_cycle:
                return False
        self.append_status("Power cycle confirmed. Continuing verification.")
        self._power_cycle_event.set()
        return True

    def start_task(
        self,
        task_id: str,
        task_options: dict[str, object] | None = None,
    ) -> tuple[bool, str]:
        if task_id not in TASKS:
            return False, f"Unknown task: {task_id}"

        task_options = task_options or {}
        if task_id in TASKS_REQUIRING_TESTER_NAME:
            tester_name = str(task_options.get("tester_name", "")).strip()
            if not tester_name:
                return False, "Tester name is required for EOL."
            task_options["tester_name"] = tester_name

        with self.lock:
            product_dir = self.current_product_dir
            product_qr_code = self.current_barcode
        if task_id == "traction_calibration" and is_so_unit(product_qr_code):
            return False, "Traction calibration is disabled for SO units."
        if task_id == "run_eol":
            if not is_so_unit(product_qr_code):
                return False, "EOL is enabled only for SO units after steering preparation."
            eol_ok, eol_message, _eol_path = eol_sequence_status_for_product(
                product_dir,
                product_qr_code,
            )
            if not eol_ok:
                return False, eol_message

        can_to_close = None
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            self.running = True
            self.status = f"Running: {TASKS[task_id]}"
            self.activity_label = TASKS[task_id]
            self.activity_step = "Starting..."
            self.activity_state = "running"
            self.log += f"\n=== {TASKS[task_id]} started ===\n"
            self.status_lines = [self.activity_step]
            self.has_error = False
            self.awaiting_power_cycle = False
            self._power_cycle_event.clear()
            can_to_close = self._detach_manual_controller_locked(
                message=f"Running: {TASKS[task_id]}"
            )
        if can_to_close is not None:
            try:
                can_to_close.close_can()
            except Exception:
                pass
        if task_id in {"start_calibration", "test_calibration", "run_all"}:
            self.reset_quality()

        self.worker = threading.Thread(
            target=self._run_task,
            args=(task_id, task_options),
            daemon=True,
        )
        self.worker.start()
        return True, ""

    def begin_manual_command(self, seq: int, node: int, bitrate: int, rpm: int) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            ready, message = self._can_ready_for_node_locked(node, bitrate)
            if not ready and rpm != 0:
                return False, message
            if seq < self.latest_manual_seq:
                return False, ""
            self.latest_manual_seq = seq
            self.manual_requests_in_flight += 1
            return True, ""

    def is_latest_manual_command(self, seq: int) -> bool:
        with self.lock:
            return seq == self.latest_manual_seq

    def finish_manual_command(self) -> None:
        with self.lock:
            self.manual_requests_in_flight = max(0, self.manual_requests_in_flight - 1)

    def begin_can_check(self, node: int, bitrate: int = DEFAULT_CAN_BITRATE) -> tuple[bool, str]:
        can_to_close = None
        with self.lock:
            if self.running or self.manual_requests_in_flight > 0:
                return False, "Cannot check CAN while another operation is running."
            can_to_close = self._detach_manual_controller_locked(
                message=f"Checking CAN node {node}..."
            )
            self.can_check_running = True
            self.can_connection_ok = None
            self.can_connection_node = node
            self.can_connection_bitrate = bitrate
            self.can_connection_message = f"Checking CAN node {node}..."
            self.activity_label = "CAN check"
            self.activity_step = f"Checking CAN node {node}..."
            self.activity_state = "running"
            self.status_lines = [self.activity_step]
            self.has_error = False
        if can_to_close is not None:
            try:
                can_to_close.close_can()
            except Exception:
                pass
        return True, ""

    def finish_can_check(
        self,
        node: int,
        bitrate: int,
        ok: bool,
        message: str,
        report: RunAllReport | None = None,
        context: ProductContext | None = None,
        mark_error: bool = True,
    ) -> None:
        with self.lock:
            self.can_check_running = False
            self.can_connection_ok = ok
            self.can_connection_node = node
            self.can_connection_bitrate = bitrate
            self.can_connection_message = message
            if report is not None:
                self.current_report = report
                self.current_barcode = report.qr_code
                self.current_product_dir = report.product_dir
            if context is not None:
                self.current_product_context = context
                self.current_barcode = context.qr_code
                self.current_product_dir = context.product_dir
                self.steering_available = True
            if not ok:
                self.controller_enabled = False
            if not ok and mark_error:
                self.has_error = True
            if ok:
                self.has_error = False
            self.activity_label = "CAN check"
            self.activity_step = message
            self.activity_state = "done" if ok else ("fail" if mark_error else "idle")
            self.status_lines = [self.activity_step]

    def set_manual_controller(
        self,
        node: int,
        bitrate: int,
        can,
        mic,
        enabled: bool = False,
        message: str | None = None,
        context: ProductContext | None = None,
    ) -> None:
        with self.lock:
            self.manual_can = can
            self.manual_mic = mic
            self.controller_enabled = enabled
            self.can_connection_ok = True
            self.can_connection_node = node
            self.can_connection_bitrate = bitrate
            self.can_connection_message = message or f"CAN connected to node {node}."
            if context is not None:
                self.current_product_context = context
                self.current_barcode = context.qr_code
                self.current_product_dir = context.product_dir
                self.steering_available = True

    def get_manual_controller(self, node: int, bitrate: int = DEFAULT_CAN_BITRATE):
        with self.lock:
            if (
                self.can_connection_ok is True
                and self.can_connection_node == node
                and self.can_connection_bitrate == bitrate
                and self.manual_mic is not None
            ):
                return self.manual_can, self.manual_mic
        return None, None

    def active_can_target(self) -> tuple[int, int]:
        with self.lock:
            if self.can_connection_ok is True and self.can_connection_node is not None:
                return self.can_connection_node, self.can_connection_bitrate
            if self.current_product_context is not None:
                return (
                    self.current_product_context.steering_node_id,
                    self.current_product_context.can_bitrate,
                )
            return DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE

    def _detach_manual_controller_locked(self, message: str | None = None):
        can = self.manual_can
        self.manual_can = None
        self.manual_mic = None
        self.controller_enabled = False
        self.controller_error_code = None
        self.controller_error_active = False
        self.can_connection_ok = False
        if message is not None:
            self.can_connection_message = message
        return can

    def get_current_report(self) -> RunAllReport | None:
        with self.lock:
            return self.current_report

    def set_current_report(self, report: RunAllReport) -> None:
        with self.lock:
            self.current_report = report
            self.current_barcode = report.qr_code
            self.current_product_dir = report.product_dir

    def set_product_context(self, context: ProductContext) -> None:
        with self.lock:
            self.current_product_context = context
            self.current_barcode = context.qr_code
            self.current_product_dir = context.product_dir
            self.steering_available = True

    def get_cached_product_context(self) -> ProductContext | None:
        with self.lock:
            return self.current_product_context

    def begin_product_scan(self) -> bool:
        with self.lock:
            if self.product_scan_running or self.product_scan_completed:
                return False
            self.product_scan_running = True
            self.awaiting_product_scan = False
            self.product_scan_error = ""
            self.product_scan_message = "Scanning product QR code..."
            self.activity_label = "Product scan"
            self.activity_step = "Scanning product QR code..."
            self.activity_state = "running"
            self.status_lines = [self.activity_step]
            return True

    def set_product_scan_result(self, result: ProductSpecCache) -> None:
        with self.lock:
            self.product_scan_running = False
            self.product_scan_completed = True
            self.awaiting_product_scan = False
            self.product_scan_error = ""
            self.product_scan_message = result.message
            self.steering_available = result.steering_available
            self.current_barcode = result.qr_code
            self.current_product_dir = result.product_dir
            self.current_product_params = dict(result.params)
            self.current_product_spec_path = result.spec_path
            self.current_product_context = result.context
            self.activity_label = "Product scan"
            self.activity_step = result.message
            self.activity_state = "done"
            self.status_lines = [self.activity_step]

    def set_product_scan_failed(self, message: str) -> None:
        with self.lock:
            self.product_scan_running = False
            self.product_scan_completed = False
            self.awaiting_product_scan = False
            self.product_scan_error = message
            self.product_scan_message = message
            self.steering_available = None
            self.has_error = True
            self.activity_label = "Product scan"
            self.activity_step = message
            self.activity_state = "fail"
            self.status_lines = [self.activity_step]

    def request_product_scan_input(self) -> None:
        with self.lock:
            if self.product_scan_completed or self.product_scan_running:
                return
            self.awaiting_product_scan = True
            self.product_scan_error = ""
            self.product_scan_message = "Scan product code."
            self.activity_label = "Product scan"
            self.activity_step = "Scan product code."
            self.activity_state = "idle"
            self.status_lines = [self.activity_step]

    def set_scan_option(self, scan_option: str) -> None:
        if scan_option not in SCAN_OPTIONS:
            raise ValueError(f"Unknown scan option: {scan_option}")
        should_start_camera_scan = False
        with self.lock:
            option_changed = self.scan_option != scan_option
            self.scan_option = scan_option
            if option_changed and not self.product_scan_running:
                self.product_scan_completed = False
                self.awaiting_product_scan = False
                self.product_scan_error = ""
                self.product_scan_message = "Scan option changed. Scan product code."
                self.steering_available = None
                self.current_product_context = None
                self.current_product_params = {}
                self.current_product_spec_path = None
                self.current_product_dir = None
                self.current_barcode = ""
                self.current_report = None
                self.activity_label = "Product scan"
                self.activity_step = "Scan option changed. Scan product code."
                self.activity_state = "idle"
                self.status_lines = [self.activity_step]
            if (
                scan_option == SCAN_OPTION_QR_CAMERA
                and self.relay_connection_ok is True
                and not self.product_scan_completed
                and not self.product_scan_running
            ):
                self.awaiting_product_scan = False
                should_start_camera_scan = True
            elif (
                scan_option != SCAN_OPTION_QR_CAMERA
                and self.relay_connection_ok is True
                and not self.product_scan_completed
                and not self.product_scan_running
            ):
                self.awaiting_product_scan = True
                self.product_scan_message = "Scan product code."
        if should_start_camera_scan:
            threading.Thread(target=run_product_scan_and_can_check, args=(None,), daemon=True).start()

    def close_manual_controller(self) -> None:
        with self.lock:
            can = self._detach_manual_controller_locked(message="CAN disconnected.")
        if can is not None:
            try:
                can.close_can()
            except Exception:
                pass

    def disconnect_can(self) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Cannot disconnect CAN while another operation is running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            node = self.can_connection_node
            can = self._detach_manual_controller_locked(
                message=f"CAN disconnected from node {node}." if node is not None else "CAN disconnected."
            )
            message = self.can_connection_message
        if can is not None:
            try:
                can.close_can()
            except Exception:
                pass
        return True, message

    def mark_can_not_connected(
        self,
        *,
        node: int | None = None,
        bitrate: int | None = None,
        message: str = "CAN not connected.",
    ) -> None:
        with self.lock:
            self.can_check_running = False
            self.can_connection_ok = False
            if node is not None:
                self.can_connection_node = node
            if bitrate is not None:
                self.can_connection_bitrate = bitrate
            self.can_connection_message = message
            self.controller_enabled = False

    def begin_relay_command(self, action_label: str) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Cannot change relays while another operation is running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            self.running = True
            self.status = action_label
            self.activity_label = action_label
            self.activity_step = "Starting relay command..."
            self.activity_state = "running"
            self.log += f"\n=== {action_label} started ===\n"
            self.status_lines = [self.activity_step]
            self.has_error = False
            return True, ""

    def finish_relay_command(self, action_label: str, ok: bool, message: str) -> None:
        with self.lock:
            self.running = False
            self.status = "Ready." if ok else f"{action_label} failed."
            self.has_error = not ok
            self.activity_label = action_label
            self.activity_step = message or ("Relay command complete." if ok else "Relay command failed.")
            self.activity_state = "done" if ok else "fail"
            self.status_lines = [self.activity_step]
        self.append_log(
            f"\n=== {action_label} finished ===\n"
            if ok
            else f"\n=== {action_label} failed ===\n"
        )

    def connect_relay_arduino(self) -> None:
        with self.lock:
            if self.relay_arduino is not None or self.relay_connecting:
                return
            self.relay_connecting = True
            self.relay_connection_ok = None
            self.relay_connection_message = "Connecting to relay Arduino..."
            self.activity_label = "Hardware"
            self.activity_step = "Connecting to relay Arduino..."
            self.activity_state = "running"
            self.status_lines = [self.activity_step]

        try:
            from drivers.driver_arduino import DriverArduino

            arduino = DriverArduino()
            protocol = getattr(arduino, "_protocol", None)
            device = getattr(arduino, "device_path", None)
            details = []
            if device:
                details.append(str(device))
            if protocol:
                details.append(f"{protocol} protocol")
            suffix = f" ({', '.join(details)})" if details else ""
            message = f"Relay Arduino connected{suffix}."
            with self.lock:
                self.relay_arduino = arduino
                self.relay_connecting = False
                self.relay_connection_ok = True
                self.relay_connection_message = message
                self.activity_label = "Hardware"
                self.activity_step = message
                self.activity_state = "done"
                self.status_lines = [self.activity_step]
            threading.Thread(target=startup_product_scan_and_can_check, daemon=True).start()
        except Exception as exc:
            message = f"Relay Arduino connection failed: {exc}"
            with self.lock:
                self.relay_arduino = None
                self.relay_connecting = False
                self.relay_connection_ok = False
                self.relay_connection_message = message
                self.has_error = True
                self.log += format_exc()
                self.activity_label = "Hardware"
                self.activity_step = message
                self.activity_state = "fail"
                self.status_lines = [self.activity_step]
            print(f"[ERROR] {message}")

    def get_relay_arduino(self):
        with self.lock:
            if self.relay_arduino is None:
                raise RuntimeError(self.relay_connection_message or "Relay Arduino is not connected.")
            return self.relay_arduino

    def close_relay_arduino(self) -> None:
        with self.lock:
            arduino = self.relay_arduino
            self.relay_arduino = None
            self.relay_connecting = False
            self.relay_connection_ok = False
            self.relay_connection_message = "Relay Arduino disconnected."
        if arduino is not None:
            try:
                arduino.close_arduino()
            except Exception:
                pass

    def begin_power_supply_output(self, node: int, enabled: bool) -> tuple[bool, str, object | None]:
        label = "ON" if enabled else "OFF"
        with self.lock:
            if self.running:
                return False, "Cannot control power supply while another operation is running.", None
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing.", None
            can = self._detach_manual_controller_locked(
                message=f"Turning power supply {label} for node {node}..."
            )
            self.running = True
            self.status = f"Turning power supply {label}."
            self.activity_label = f"Power supply {label}"
            self.activity_step = "Setting controller relays..."
            self.activity_state = "running"
            self.log += f"\n=== Power Supply {label} started ===\n"
            self.status_lines = [self.activity_step]
            self.has_error = False
            return True, "", can

    def finish_power_supply_output(self, enabled: bool, ok: bool, message: str) -> None:
        label = "ON" if enabled else "OFF"
        with self.lock:
            self.running = False
            self.status = "Ready." if ok else f"Power supply {label} failed."
            if ok:
                self.has_error = False
            else:
                self.has_error = True
            self.activity_label = f"Power supply {label}"
            self.activity_step = message or ("Power supply command complete." if ok else "Power supply command failed.")
            self.activity_state = "done" if ok else "fail"
            self.status_lines = [self.activity_step]
        self.append_log(
            f"\n=== Power Supply {label} finished ===\n"
            if ok
            else f"\n=== Power Supply {label} failed ===\n"
        )

    def begin_controller_command(self, node: int, bitrate: int) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            ready, message = self._can_ready_for_node_locked(node, bitrate)
            if not ready:
                return False, message
            self.manual_requests_in_flight += 1
            return True, ""

    def set_controller_enabled(self, node: int, enabled: bool) -> None:
        with self.lock:
            if self.can_connection_node == node:
                self.controller_enabled = enabled

    def _can_ready_for_node_locked(self, node: int, bitrate: int) -> tuple[bool, str]:
        if self.can_check_running:
            return False, "CAN connection check is still running."
        if (
            self.can_connection_ok is not True
            or self.can_connection_node != node
            or self.can_connection_bitrate != bitrate
            or self.manual_mic is None
        ):
            return False, "CAN node is not connected. Wait for the CAN check or run a product task first."
        return True, ""

    def _run_task(
        self,
        task_id: str,
        task_options: dict[str, object] | None = None,
    ) -> None:
        label = TASKS[task_id]
        writer = QueueWriter(self)
        started_at = time.monotonic()
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                result = run_task(task_id, task_options=task_options)
            elapsed = time.monotonic() - started_at
            success = is_success(result)
            if success:
                self.append_log(f"\n=== {label} finished in {elapsed:.1f}s ===\n")
                self.finish_activity(label, f"Finished in {elapsed:.1f}s.", True)
            else:
                self.append_log(
                    f"\n=== {label} finished with result {result!r} in {elapsed:.1f}s ===\n"
                )
                self.finish_activity(label, "Finished with errors. Open Debug for details.", False)
                if task_id in {"start_calibration", "test_calibration", "run_all"}:
                    self.mark_quality_failed_if_pending("calibration stopped before final quality report")
            with self.lock:
                self.status = "Ready." if success else "Finished with errors."
                if success:
                    self.has_error = False
        except Exception:
            self.append_log(format_exc())
            self.append_log(f"\n=== {label} failed ===\n")
            self.finish_activity(label, "Failed. Open Debug for details.", False)
            if task_id in {"start_calibration", "test_calibration", "run_all"}:
                self.mark_quality_failed_if_pending("calibration failed before final quality report")
            with self.lock:
                self.status = "Failed. See log."
        finally:
            with self.lock:
                self.running = False
            if task_id in {
                "run_all",
                "load_script_config",
                "load_script",
                "load_config",
                "start_calibration",
                "test_calibration",
                "run_eol",
                "show_current_zero",
                "start_zeroing",
            }:
                with self.lock:
                    context = self.current_product_context
                if context is not None:
                    node = context.steering_node_id
                    bitrate = context.can_bitrate
                else:
                    node, bitrate = self.active_can_target()
                try:
                    reconnect_gui_can(node, bitrate)
                except Exception:
                    self.append_log(format_exc())
                    self.append_status(
                        f"CAN reconnect failed after {label}.",
                        is_error=True,
                    )


class QueueWriter(io.TextIOBase):
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._line_buffer = ""

    def write(self, text: str) -> int:
        self.state.append_log(text)
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            self.state.observe_log_line(line)
        return len(text)

    def flush(self) -> None:
        if self._line_buffer:
            self.state.observe_log_line(self._line_buffer)
            self._line_buffer = ""
        pass


class LogOnlyWriter(io.TextIOBase):
    def __init__(self, state: AppState) -> None:
        self.state = state

    def write(self, text: str) -> int:
        self.state.append_log(text)
        return len(text)

    def flush(self) -> None:
        pass


def is_success(result) -> bool:
    if result is None:
        return True
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result == 0
    return bool(result)


def gui_safe_execute(func, *args, spinner_text: str | None = None, **kwargs):
    if spinner_text:
        STATE.set_activity(step=spinner_text, state="running", mark_error=False)
    try:
        return func(*args, **kwargs)
    except Exception:
        if spinner_text:
            STATE.set_activity(
                step=f"{spinner_text} failed. Open Debug for details.",
                state="fail",
            )
        raise


def angle_error_deg(measured_angle: float, desired_angle: float) -> float:
    return abs((float(measured_angle) - float(desired_angle) + 180.0) % 360.0 - 180.0)


def format_zero_status(
    zero_data: dict[str, object],
    failed_exc: Exception | None = None,
) -> dict[str, object]:
    error = zero_data.get("error_deg")
    if failed_exc is not None:
        return {"Write Zero": "not OK"}
    if error is None:
        return {"Write Zero": "-"}
    tolerance = float(zero_data.get("tolerance_deg", ZERO_VISUAL_TOLERANCE_DEG))
    ok = bool(zero_data.get("ok", abs(float(error)) <= tolerance))
    return {"Write Zero": "OK" if ok else "not OK"}


def format_quality_summary(events: list[dict[str, object]]) -> str:
    if not events:
        return "-"
    latest_by_encoder: dict[int, dict[str, object]] = {}
    for event in events:
        latest_by_encoder[int(event.get("encoder", 0))] = event
    parts = []
    for encoder, event in sorted(latest_by_encoder.items()):
        status = "PASS" if event.get("ok") else "FAIL"
        residual = event.get("max_abs_analog_residual_lsb")
        margin = event.get("max_abs_phase_margin_pct_of_range_limit")
        parts.append(
            f"E{encoder} {status} r={float(residual):.2f} m={float(margin):.1f}%"
        )
    return "; ".join(parts)


def format_zero_preserving(events: list[dict[str, object]]) -> str:
    if not events:
        return "-"
    return "OK" if all(bool(event.get("ok")) for event in events) else "FAIL"


def format_config_status(status: object) -> str:
    text = str(status or "").strip()
    if not text or text == "No error":
        return "OK"
    return "not OK"


def format_ok_status(ok: object) -> str:
    return "OK" if is_success(ok) else "not OK"


def set_status_bar_barcode(report: RunAllReport, node: int) -> None:
    if not report.qr_code:
        return
    with STATE.lock:
        if STATE.can_connection_ok is True and STATE.can_connection_node == node:
            STATE.can_connection_message = f"{report.qr_code}: CAN connected to node {node}."


def prepare_report_for_context(context: ProductContext) -> RunAllReport:
    node = context.steering_node_id
    desired_angle = context.zero_angle
    report = STATE.get_current_report()
    if report is None or report.qr_code != context.qr_code:
        report = RunAllReport(
            product_dir=context.product_dir,
            qr_code=context.qr_code,
            node=node,
            desired_angle=desired_angle,
        )
        STATE.set_current_report(report)
    else:
        report.update(
            **{
                "nodeID": node,
                "Serial number from QR code": context.qr_code,
            }
        )

    STATE.set_product_context(context)
    refresh_report_controller_serial(report, node, context.can_bitrate)
    set_status_bar_barcode(report, node)
    print(f"[INFO] Result workbook: {report.path}")
    return report


def refresh_report_controller_serial(
    report: RunAllReport | None,
    node: int,
    can_bitrate: int,
) -> bool:
    if report is None:
        return True
    try:
        identity = read_controller_identity(node, can_bitrate=can_bitrate)
    except Exception as exc:
        message = f"Controller identity read skipped: {exc}"
        print(f"[WARN] {message}")
        STATE.append_status(message, is_error=True)
        return False
    if identity:
        report.update(**identity)
    return True


def wait_for_manual_restart_and_reconnect(context: ProductContext, reason: str) -> bool:
    message = (
        f"{reason} Power-cycle/restart the external supply and controller manually, "
        "then press Continue after power cycle."
    )
    print(f"[STATUS] {message}")
    STATE.append_status(message, is_error=True)
    if not STATE.request_power_cycle_confirmation(POWER_CYCLE_CONFIRM_TIMEOUT_S):
        print("[ERROR] Timed out waiting for manual restart confirmation.")
        return False

    connected, can_message = check_can_connection(
        context.steering_node_id,
        can_bitrate=context.can_bitrate,
        create_report=False,
        context=context,
    )
    if connected:
        STATE.append_status(f"Manual restart confirmed. {can_message}")
        return True

    STATE.append_status(
        f"Manual restart confirmed, but CAN is still unavailable: {can_message}",
        is_error=True,
    )
    print(f"[ERROR] {can_message}")
    return False


def read_controller_identity_optional(
    node: int,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> dict[str, object]:
    try:
        return read_controller_identity(node, can_bitrate=can_bitrate)
    except Exception as exc:
        message = f"Controller identity read skipped: {exc}"
        print(f"[WARN] {message}")
        STATE.append_status(message, is_error=True)
        return {}


def steering_can_candidates(context: ProductContext) -> list[tuple[int, int, str, ProductContext]]:
    raw_candidates: list[tuple[int, int, str, ProductContext]] = [
        (STANDARD_NODE_ID, DEFAULT_CAN_BITRATE, "standard node 59", context),
        (
            context.steering_node_id,
            context.can_bitrate,
            "product specification node",
            context,
        ),
    ]
    candidates: list[tuple[int, int, str, ProductContext]] = []
    seen: set[tuple[int, int]] = set()
    for node, bitrate, label, candidate_context in raw_candidates:
        key = (node, bitrate)
        if key in seen:
            continue
        candidates.append((node, bitrate, label, candidate_context))
        seen.add(key)
    return candidates


def _check_configuration_can_candidates(context: ProductContext) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for node, bitrate, label, candidate_context in steering_can_candidates(context):
        print(f"[INFO] Configuration CAN preflight trying {label}: node {node}, {bitrate} kbit/s.")
        connected, message = check_can_connection(
            node,
            can_bitrate=bitrate,
            create_report=False,
            context=candidate_context,
        )
        if connected:
            print(f"[INFO] Configuration CAN preflight accepted {label}: {message}")
            return True, failures
        failures.append(f"{label}: {message}")
    print("[WARN] Configuration CAN preflight failed after trying all steering CAN candidates.")
    return False, failures


def ensure_controller_ready_for_configuration(context: ProductContext) -> None:
    connected, failures = _check_configuration_can_candidates(context)
    if connected:
        return

    print("[STATUS] Controller not reachable on node 59 or product node before Configuration; restarting with relays.")
    try:
        ok, restart_message = restart_controller_with_relays(
            node=None,
            can_bitrate=None,
            context=None,
            reconnect=False,
            off_seconds=CONTROLLER_POWER_CYCLE_OFF_S,
        )
    except Exception as exc:
        ok = False
        restart_message = f"Relay controller restart failed: {exc}"
    STATE.append_status(restart_message, is_error=not ok, mark_error=False)
    if ok:
        connected, failures = _check_configuration_can_candidates(context)
        if connected:
            return

    reason = (
        "Controller is not reachable on standard node 59 or product specification "
        f"node {context.steering_node_id} before Configuration."
    )
    if wait_for_manual_restart_and_reconnect(context, reason):
        connected, failures = _check_configuration_can_candidates(context)
        if connected:
            return

    raise RuntimeError(
        "Could not add CAN node 59 or product specification node "
        f"{context.steering_node_id} before Configuration. "
        + " | ".join(failures)
    )


def ensure_controller_ready_for_task(context: ProductContext, task_label: str) -> None:
    connected, failures = _check_configuration_can_candidates(context)
    if connected:
        return

    print(f"[WARN] Controller is not reachable before {task_label}: {' | '.join(failures)}")
    if restart_controller_with_relays_for_task(
        context,
        f"Controller is not reachable before {task_label}.",
    ):
        return

    if wait_for_manual_restart_and_reconnect(
        context,
        f"Controller is not reachable before {task_label}.",
    ):
        return

    raise RuntimeError(
        f"Could not add CAN node 59 or product node {context.steering_node_id} before {task_label}."
    )


def run_task(task_id: str, task_options: dict[str, object] | None = None):
    task_options = task_options or {}
    if task_id == "run_all":
        return gui_safe_execute(
            run_all,
            tester_name=str(task_options.get("tester_name", "")).strip(),
            spinner_text="Running full steering workflow",
        )

    if task_id == "run_eol":
        product_barcode = str(task_options.get("product_barcode", "")).strip()
        motor_barcode = str(task_options.get("motor_barcode", "")).strip()
        raw_ssi_encoder_restore = task_options.get("ssi_encoder_restore", True)
        ssi_encoder_restore = (
            parse_enabled(raw_ssi_encoder_restore)
            if isinstance(raw_ssi_encoder_restore, str)
            else bool(raw_ssi_encoder_restore)
        )
        if not product_barcode:
            with STATE.lock:
                if STATE.scan_option == SCAN_OPTION_QR_CAMERA:
                    product_barcode = str(STATE.current_barcode or "").strip()
        if not product_barcode:
            raise RuntimeError("Product barcode is required for EOL.")
        if not product_barcode.upper().startswith("SO-1000"):
            raise RuntimeError("Product barcode must start with SO-1000.")
        if not motor_barcode and is_so_unit(product_barcode):
            motor_barcode = "0"
        if not motor_barcode:
            raise RuntimeError("Motor barcode is required for EOL.")
        return gui_safe_execute(
            run_mobotic_eol,
            tester_name=str(task_options.get("tester_name", "")).strip(),
            unit_serial_number=product_barcode,
            motor_number=motor_barcode,
            manual_power=False,
            ssi_encoder_restore=ssi_encoder_restore,
            spinner_text="Running EOL",
        )

    if task_id == "traction_calibration":
        return gui_safe_execute(
            run_traction_calibration,
            task_options.get("motor_barcode", ""),
            spinner_text="Running traction calibration",
        )

    context = gui_safe_execute(
        get_cached_or_scan_product_context,
        spinner_text="Loading product specification",
    )
    STATE.set_product_context(context)
    node = context.steering_node_id
    reportable_tasks = {"load_script_config", "start_calibration", "start_zeroing"}
    report = (
        prepare_report_for_context(context)
        if task_id in reportable_tasks
        else STATE.get_current_report()
    )
    if task_id in reportable_tasks:
        gui_safe_execute(
            refresh_report_controller_serial,
            report,
            node,
            context.can_bitrate,
            spinner_text="Reading controller serial",
        )

    if task_id == "load_script":
        return gui_safe_execute(
            load_steering_script_with_node_fallback,
            context,
            spinner_text="Loading steering script",
        )

    if task_id == "load_script_config":
        try:
            gui_safe_execute(
                ensure_controller_ready_for_configuration,
                context,
                spinner_text="Checking controller before Configuration",
            )
            gui_safe_execute(
                refresh_report_controller_serial,
                report,
                node,
                context.can_bitrate,
                spinner_text="Reading controller serial",
            )
            config_details = gui_safe_execute(
                run_load_script_config_details,
                context,
                spinner_text="Loading steering configuration",
            )
            if report is not None:
                report.update(
                    **read_controller_identity_optional(node, can_bitrate=context.can_bitrate),
                    **{
                        "Configuration": format_config_status(
                            config_details.get(
                                "configuration_error_status",
                                "No error" if config_details.get("ok") else "Configuration failed",
                            )
                        )
                    }
                )
            return bool(config_details.get("ok"))
        except Exception as exc:
            if report is not None:
                report.update(**{"Configuration": "not OK"})
            raise

    if task_id == "load_config":
        return gui_safe_execute(
            run_load_config,
            node=node,
            can_bitrate=context.can_bitrate,
            spinner_text="Loading steering MU config",
        )

    if task_id == "start_calibration":
        from logic import FullCalibration

        print(
            "[INFO] Starting calibration without post-calibration zero write. "
            "Use Write Zero before Calibration when the physical zero must be saved."
        )
        gui_safe_execute(
            ensure_controller_ready_for_task,
            context,
            "Calibration",
            spinner_text="Checking controller before Calibration",
        )
        gui_safe_execute(
            refresh_report_controller_serial,
            report,
            node,
            context.can_bitrate,
            spinner_text="Reading controller serial",
        )
        quality_events: list[dict[str, object]] = []
        zero_preserving_events: list[dict[str, object]] = []

        def calibration_callback(event: dict[str, object]) -> None:
            if event.get("event") == "quality":
                quality_events.append(event)
            elif event.get("event") == "zero_preserving":
                zero_preserving_events.append(event)
            if report is not None:
                report.update(
                    **{
                        "Calibration": "OK"
                        if event.get("ok")
                        else "not OK",
                    }
                )

        try:
            calibration_ok = gui_safe_execute(
                FullCalibration.main,
                serial_last4=SERIAL_LAST4,
                can_bitrate=context.can_bitrate,
                node=node,
                result_callback=calibration_callback,
                power_cycle_wait_fn=automatic_controller_relay_restart,
                spinner_text="Running steering calibration",
            )
        except Exception as exc:
            if report is not None:
                report.update(
                    **{
                        "Calibration": "not OK",
                    }
                )
            raise
        if report is not None:
            report.update(
                **{
                    "Calibration": format_ok_status(calibration_ok),
                }
            )
        return calibration_ok

    if task_id == "test_calibration":
        TestCalibration = load_test_calibration_module()

        gui_safe_execute(
            ensure_controller_ready_for_task,
            context,
            "TestCalibration",
            spinner_text="Checking controller before TestCalibration",
        )
        result = gui_safe_execute(
            TestCalibration.main,
            serial_last4=SERIAL_LAST4,
            can_bitrate=context.can_bitrate,
            node=node,
            spinner_text="Running TestCalibration",
        )
        if not is_success(result):
            return result

        gui_safe_execute(
            wait_for_power_cycle_after_test_calibration,
            automatic_controller_relay_restart,
            spinner_text="Waiting for post-test power cycle",
        )
        gui_safe_execute(
            restore_standalone_test_calibration_controller,
            node=node,
            can_bitrate=context.can_bitrate,
            spinner_text="Restoring controller after TestCalibration",
        )
        return result

    if task_id == "show_current_zero":
        gui_safe_execute(
            ensure_controller_ready_for_task,
            context,
            "Show Current Zero",
            spinner_text="Checking controller before Show Current Zero",
        )
        return gui_safe_execute(
            run_show_current_zero,
            node=node,
            desired_angle=context.zero_angle,
            can_bitrate=context.can_bitrate,
            spinner_text="Reading current zero",
        )

    if task_id == "start_zeroing":
        gui_safe_execute(
            ensure_controller_ready_for_task,
            context,
            "Write Zero",
            spinner_text="Checking controller before Write Zero",
        )
        gui_safe_execute(
            refresh_report_controller_serial,
            report,
            node,
            context.can_bitrate,
            spinner_text="Reading controller serial",
        )
        zero_result: dict[str, object] = {}

        def zero_callback(data: dict[str, object]) -> None:
            zero_result.update(data)
            if report is not None:
                report.update(**format_zero_status(zero_result))

        try:
            result = gui_safe_execute(
                run_zeroing,
                node=node,
                desired_angle=context.zero_angle,
                can_bitrate=context.can_bitrate,
                result_callback=zero_callback,
                spinner_text="Writing steering zero",
            )
        except Exception as exc:
            if report is not None:
                report.update(**format_zero_status(zero_result, failed_exc=exc))
            raise
        if report is not None:
            report.update(**format_zero_status(zero_result))
        return result

    raise ValueError(f"Unknown task: {task_id}")


def run_manual_spin(
    node: int,
    rpm: int,
    seq: int,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> bool:
    can, mic = STATE.get_manual_controller(node, can_bitrate)
    close_after_command = False
    if mic is None:
        can, mic = open_controller(node, can_bitrate=can_bitrate)
        close_after_command = True
    try:
        if not STATE.is_latest_manual_command(seq):
            print(f"[INFO] Ignored stale manual motor command: {rpm} RPM.")
            return True
        mic.enabled(True)
        if not close_after_command:
            STATE.set_controller_enabled(node, True)
        mic.set_velocity_mode()
        mic.set_RPM(rpm)
        if rpm == 0:
            print(f"[STATUS] Manual motor stop sent to node {node}.")
        else:
            print(f"[STATUS] Manual steering spin sent to node {node}: {rpm} RPM.")
        return True
    except Exception:
        if not close_after_command:
            can_to_close = None
            with STATE.lock:
                if STATE.manual_mic is mic:
                    can_to_close = STATE._detach_manual_controller_locked(
                        message=f"CAN disconnected from node {node} after manual command failure."
                    )
            if can_to_close is not None:
                try:
                    can_to_close.close_can()
                except Exception:
                    pass
        raise
    finally:
        if close_after_command:
            try:
                can.close_can()
            except Exception:
                pass


def read_controller_identity_from_mic(mic) -> dict[str, object]:
    serial_number = _safe_controller_read(mic, "get_Serial_number")
    if serial_number is None:
        return {}
    return {"Serial number": serial_number}


def create_report_for_connected_can(
    node: int,
    desired_angle: float,
    mic,
    context: ProductContext | None = None,
) -> RunAllReport:
    if context is None:
        context = get_cached_or_scan_product_context()
    report = RunAllReport(
        product_dir=context.product_dir,
        qr_code=context.qr_code,
        node=node,
        desired_angle=desired_angle,
    )
    report.update(**read_controller_identity_from_mic(mic))
    STATE.set_current_report(report)
    return report


def check_can_connection(
    node: int,
    *,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
    create_report: bool = True,
    context: ProductContext | None = None,
) -> tuple[bool, str]:
    can = None
    try:
        can, mic = open_controller(node, enable=False, can_bitrate=can_bitrate)
    except Exception as exc:
        return False, f"CAN connection failed for node {node}. ({exc})"

    try:
        report = (
            create_report_for_connected_can(
                node,
                context.zero_angle if context is not None else ZERO_ANGLE_DEG,
                mic,
                context=context,
            )
            if create_report and context is not None
            else None
        )
    except Exception as exc:
        try:
            can.close_can()
        except Exception:
            pass
        return False, f"CAN connected to node {node}, but barcode/report failed. ({exc})"

    barcode = (
        report.qr_code
        if report is not None
        else (context.qr_code if context is not None else STATE.current_barcode)
    )
    message = (
        f"{barcode}: CAN connected to node {node}."
        if barcode
        else f"CAN connected to node {node}."
    )
    STATE.set_manual_controller(
        node,
        can_bitrate,
        can,
        mic,
        enabled=False,
        message=message,
        context=context,
    )
    return True, message


def _can_interface_setup_failure_message(
    standard_failure: str,
    product_failure: str | None,
    context: ProductContext | None,
) -> str | None:
    combined = "\n".join(part for part in (standard_failure, product_failure or "") if part)
    if "CAN interface" not in combined:
        return None

    node_text = (
        f" Product specification Steering Node ID is {context.steering_node_id}."
        if context is not None
        else ""
    )
    interface_match = re.search(r"CAN interface\s+([^:\s)]+)", combined)
    interface_name = interface_match.group(1) if interface_match else None
    missing_text = ""
    if "does not exist" in combined:
        missing_text = (
            f" Linux SocketCAN interface {interface_name} does not exist."
            if interface_name
            else " Linux SocketCAN interface does not exist."
        )
        missing_text += (
            " Connect or enable the CAN adapter so it creates the expected interface, "
            "or set ST_CAN_CHANNEL to the actual interface name."
        )
    command_match = re.search(r"Run:\s*(sudo ip link set .+)", combined)
    command_text = f" Run: {command_match.group(1).rstrip(')')}" if command_match else ""
    summary = (
        "CAN interface setup failed. Product specification was read correctly."
        if context is not None
        else "CAN interface setup failed before product-specific CAN could be checked."
    )
    return (
        f"{summary}{node_text}{missing_text}{command_text}"
    )


def check_standard_then_product_can_connection() -> tuple[bool, int, int, str, ProductContext | None]:
    try:
        context = get_cached_or_scan_product_context()
    except Exception as exc:
        unknown_message = (
            "CAN node ID is unknown. QR/product specification could not be read "
            f"or does not contain steering information. ({exc})"
        )
        print(f"[WARN] {unknown_message}")
        return False, DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE, unknown_message, None

    failures: list[str] = []
    for node, bitrate, label, candidate_context in steering_can_candidates(context):
        print(f"[INFO] Checking CAN {label}: node {node}, {bitrate} kbit/s.")
        connected, message = check_can_connection(
            node,
            can_bitrate=bitrate,
            create_report=False,
            context=candidate_context,
        )
        if connected:
            print(f"[INFO] CAN preflight accepted {label}: {message}")
            return True, node, bitrate, message, context
        failures.append(f"{label}: {message}")

    standard_failure = failures[0] if failures else ""
    product_message = failures[-1] if failures else None
    setup_message = _can_interface_setup_failure_message(
        standard_failure,
        product_message,
        context,
    )
    if setup_message is not None:
        print(f"[WARN] {product_message}")
        print(f"[WARN] {setup_message}")
        return False, context.steering_node_id, context.can_bitrate, setup_message, context

    unknown_message = (
        "CAN connection failed after trying standard node 59 and product specification "
        f"Steering Node ID {context.steering_node_id}. "
        + " | ".join(failures)
    )
    print(f"[WARN] {unknown_message}")
    return False, context.steering_node_id, context.can_bitrate, unknown_message, context


def reconnect_gui_can(node: int, can_bitrate: int = DEFAULT_CAN_BITRATE) -> tuple[bool, str]:
    saved_report = STATE.get_current_report()
    with STATE.lock:
        saved_context = STATE.current_product_context
    with STATE.lock:
        can = STATE._detach_manual_controller_locked(message=f"Reconnecting CAN node {node}...")
    if can is not None:
        try:
            can.close_can()
        except Exception:
            pass
    connected, message = check_can_connection(
        node,
        can_bitrate=can_bitrate,
        create_report=False,
        context=saved_context,
    )
    if connected and saved_report is not None:
        STATE.set_current_report(saved_report)
        if saved_report.qr_code:
            message = f"{saved_report.qr_code}: CAN connected to node {node}."
            with STATE.lock:
                STATE.can_connection_message = message
    STATE.append_status(message, is_error=not connected)
    return connected, message


def run_controller_enable(
    node: int,
    enabled: bool,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> tuple[bool, str]:
    _can, mic = STATE.get_manual_controller(node, can_bitrate)
    if mic is None:
        return False, "CAN node is not connected."
    mic.enabled(enabled)
    STATE.set_controller_enabled(node, enabled)
    message = f"Controller node {node} {'enabled' if enabled else 'disabled'}."
    print(f"[STATUS] {message}")
    return True, message


def run_controller_clear_errors(
    node: int,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> tuple[bool, str]:
    _can, mic = STATE.get_manual_controller(node, can_bitrate)
    if mic is None:
        return False, "CAN node is not connected."
    mic.clear_errors()
    message = f"Controller errors cleared on node {node}."
    print(f"[STATUS] {message}")
    return True, message


def run_power_supply_output(node: int, enabled: bool, can_bitrate: int) -> tuple[bool, str]:
    with STATE.lock:
        context = STATE.current_product_context
    return set_controller_power_relays(
        enabled,
        node=node,
        can_bitrate=can_bitrate,
        reconnect=enabled,
        context=context,
    )


def automatic_power_cycle_for_zero(_timeout_s: float) -> bool:
    print("[STATUS] Automatically restarting controller relays for Write Zero verification.")
    STATE.append_status("Automatically restarting controller relays for Write Zero verification.")
    ok = automatic_controller_relay_restart(POWER_CYCLE_CONFIRM_TIMEOUT_S)
    if ok:
        STATE.append_status("Relay restart completed. Continuing zero verification.")
    else:
        with STATE.lock:
            STATE.status = "Write Zero relay restart failed."
        STATE.append_status("Relay restart failed during Write Zero.", is_error=True)
    return ok


def wait_for_power_cycle_after_test_calibration(power_cycle_wait_fn) -> None:
    print(
        "[STATUS] TestCalibration finished. Power-cycle the supply now, "
        "then press Continue after power cycle."
    )
    if power_cycle_wait_fn is None:
        raise RuntimeError("Power-cycle confirmation is not available in this run mode.")
    if not power_cycle_wait_fn(POWER_CYCLE_CONFIRM_TIMEOUT_S):
        raise RuntimeError(
            "Timed out waiting for power-cycle confirmation after TestCalibration."
        )
    print("[INFO] Power-cycle confirmed after TestCalibration.")


def load_test_calibration_module():
    try:
        return importlib.import_module("tests.TestCalibration")
    except ModuleNotFoundError as exc:
        if exc.name not in {"tests", "tests.TestCalibration"}:
            raise
        tests_dir = PROJECT_ROOT / "tests"
        if str(tests_dir) not in sys.path:
            sys.path.insert(0, str(tests_dir))
        return importlib.import_module("TestCalibration")


def restore_controller_after_test_calibration(
    controller,
    *,
    label: str = "TestCalibration",
    reason: str | None = None,
    settle_s: float = 0.5,
    ssi_encoder_enable: bool = True,
) -> None:
    if controller is None:
        return
    suffix = f" ({reason})" if reason else ""
    print(f"[INFO] Restoring controller SSI state after {label}{suffix}.")
    try:
        if hasattr(controller, "restore_extended_ssi_mode"):
            controller.restore_extended_ssi_mode()
    except Exception as exc:
        print(f"[WARN] restore_extended_ssi_mode failed after {label}: {exc}")
    try:
        if hasattr(controller, "SSI_encoder") and controller.SSI_encoder(ssi_encoder_enable):
            print(f"[INFO] SSI_encoder({ssi_encoder_enable}) confirmed after {label}.")
        elif hasattr(controller, "SSI_encoder"):
            print(f"[WARN] SSI_encoder({ssi_encoder_enable}) did not report success after {label}.")
    except Exception as exc:
        print(f"[WARN] SSI_encoder({ssi_encoder_enable}) failed after {label}: {exc}")
    time.sleep(settle_s)
    for _attempt in range(2):
        try:
            if hasattr(controller, "clear_errors"):
                controller.clear_errors()
        except Exception as exc:
            print(f"[WARN] clear_errors failed after {label}: {exc}")
    try:
        status = (
            controller.get_ssi_encoder_status()
            if hasattr(controller, "get_ssi_encoder_status")
            else None
        )
        error = controller.get_error_code() if hasattr(controller, "get_error_code") else None
        position = (
            controller.get_steering_pos()
            if hasattr(controller, "get_steering_pos")
            else None
        )
        print(
            f"[INFO] Controller SSI state after {label} restore: "
            f"status={status} error={error} steering_position={position}"
        )
    except Exception as exc:
        print(f"[WARN] Could not read controller state after {label} restore: {exc}")
    print(f"[INFO] Controller errors cleared after {label}.")


def restore_standalone_test_calibration_controller(
    node: int = DEFAULT_NODE_ID,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> None:
    can, mic, owned = acquire_controller(node, enable=False, can_bitrate=can_bitrate)
    try:
        restore_controller_after_test_calibration(
            mic,
            label="standalone TestCalibration",
        )
    finally:
        release_controller(can, owned)


def run_all(tester_name: str | None = None) -> bool:
    context = get_cached_or_scan_product_context()
    STATE.set_product_context(context)
    node = context.steering_node_id
    target_angle = context.zero_angle
    report: RunAllReport | None = None
    final_zero_required = False
    post_calibration_zero_done = False

    try:
        report = gui_safe_execute(
            prepare_report_for_context,
            context,
            spinner_text="Preparing result workbook",
        )
        gui_safe_execute(
            ensure_controller_ready_for_task,
            context,
            "Run All",
            spinner_text="Checking controller before Run All",
        )

        config_details = gui_safe_execute(
            run_load_script_config_details,
            context,
            spinner_text="Run All: loading steering configuration",
        )
        report.update(
            **read_controller_identity_optional(node, can_bitrate=context.can_bitrate),
            **{
                "Configuration": format_config_status(
                    config_details.get(
                        "configuration_error_status",
                        "No error" if config_details.get("ok") else "Configuration failed",
                    )
                )
            },
        )
        print(f"[INFO] Run All result workbook: {report.path}")
        if not config_details.get("ok"):
            return False

        final_zero_required = True
        zero_result: dict[str, object] = {}

        def zero_callback(data: dict[str, object]) -> None:
            zero_result.update(data)
            if report is not None:
                report.update(**format_zero_status(zero_result))

        print("[INFO] Run All: saving physical zero before calibration.")
        try:
            gui_safe_execute(
                run_zeroing,
                node=node,
                desired_angle=target_angle,
                can_bitrate=context.can_bitrate,
                result_callback=zero_callback,
                spinner_text="Run All: writing steering zero",
            )
        except Exception as exc:
            if report is not None:
                report.update(**format_zero_status(zero_result, failed_exc=exc))
            raise
        if report is not None:
            report.update(**format_zero_status(zero_result))

        from logic import FullCalibration

        quality_events: list[dict[str, object]] = []
        zero_preserving_events: list[dict[str, object]] = []

        def calibration_callback(event: dict[str, object]) -> None:
            if event.get("event") == "quality":
                quality_events.append(event)
            elif event.get("event") == "zero_preserving":
                zero_preserving_events.append(event)
            if report is not None:
                report.update(
                    **{
                        "Calibration": "OK"
                        if event.get("ok")
                        else "not OK",
                    }
                )

        calibration_ok = gui_safe_execute(
            FullCalibration.main,
            serial_last4=SERIAL_LAST4,
            can_bitrate=context.can_bitrate,
            node=node,
            result_callback=calibration_callback,
            power_cycle_wait_fn=automatic_controller_relay_restart,
            spinner_text="Run All: running steering calibration",
        )
        if report is not None:
            report.update(
                **{
                    "Calibration": format_ok_status(calibration_ok),
                }
            )
        if not is_success(calibration_ok):
            return False

        print("[INFO] Run All: moving controller to current zero before EOL.")
        for pass_idx in range(1, 3):
            gui_safe_execute(
                return_motor_to_zero_for_run_all,
                node,
                can_bitrate=context.can_bitrate,
                context=f"run all post-calibration zero pass {pass_idx}",
                spinner_text=f"Run All: moving to current zero pass {pass_idx}",
            )
        post_calibration_zero_done = True
        final_zero_required = False

        print("[INFO] Run All: starting EOL-case mobotic_EOL program.")
        eol_ok = gui_safe_execute(
            run_mobotic_eol,
            tester_name=tester_name,
            context=context,
            spinner_text="Run All: running EOL",
        )
        print("[INFO] Run All completed after configuration, zero write, calibration, current zero, and EOL.")
        return is_success(eol_ok)
    finally:
        if report is not None and final_zero_required and not post_calibration_zero_done:
            try:
                final_zero_status = gui_safe_execute(
                    return_motor_to_zero_for_run_all,
                    node,
                    can_bitrate=context.can_bitrate,
                    context="run all final zero cleanup",
                    spinner_text="Run All: final zero cleanup",
                )
            except Exception as exc:
                final_zero_status = "FAIL"
                print(f"[WARN] Run All final motor zero failed: {exc}")


def _is_eol_case_import(name: str) -> bool:
    return any(
        name == prefix or name.startswith(f"{prefix}.")
        for prefix in EOL_CASE_IMPORT_PREFIXES
    )


@contextlib.contextmanager
def _external_eol_import_scope():
    if not EOL_CASE_MAIN_PATH.is_file():
        raise FileNotFoundError(f"EOL-case entrypoint not found: {EOL_CASE_MAIN_PATH}")

    eol_root_str = str(EOL_CASE_ROOT)
    previous_project_root = os.environ.get("PROJECT_ROOT")
    previous_eol_root = os.environ.get("EOL_ROOT")
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if _is_eol_case_import(name)
    }

    os.environ["PROJECT_ROOT"] = str(MANUFACTURING_ROOT)
    os.environ["EOL_ROOT"] = eol_root_str
    sys.path.insert(0, eol_root_str)
    for name in list(saved_modules):
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        for name in list(sys.modules):
            if _is_eol_case_import(name):
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
        try:
            sys.path.remove(eol_root_str)
        except ValueError:
            pass
        if previous_project_root is None:
            os.environ.pop("PROJECT_ROOT", None)
        else:
            os.environ["PROJECT_ROOT"] = previous_project_root
        if previous_eol_root is None:
            os.environ.pop("EOL_ROOT", None)
        else:
            os.environ["EOL_ROOT"] = previous_eol_root


def _load_eol_case_module():
    spec = importlib.util.spec_from_file_location("eol_case_mobotic_EOL", EOL_CASE_MAIN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {EOL_CASE_MAIN_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_eol_product_family_resolution() -> None:
    from io_helpers import requirements_doc as eol_requirements_doc
    from io_helpers import find_product_folder as eol_find_product_folder

    original_find_product_spec_v2 = eol_requirements_doc.find_product_spec_v2

    def resolve_product_spec_from_scan(scan_text):
        text = str(scan_text or "").strip()
        if not text:
            raise ValueError("Empty QR code; cannot resolve product specification.")

        scanned_path = Path(os.path.expanduser(text))
        if scanned_path.exists():
            scanned_path = scanned_path.resolve()
            product_dir = scanned_path.parent if scanned_path.is_file() else scanned_path
        else:
            old_cwd = os.getcwd()
            try:
                product_dir_raw = eol_find_product_folder.find_config(text)
            finally:
                try:
                    os.chdir(old_cwd)
                except Exception:
                    pass
            if not product_dir_raw:
                raise FileNotFoundError(f"[ERROR] No matching folder found for QR code: {text}")
            product_base = configured_product_base_path(
                getattr(eol_find_product_folder, "config", None)
            )
            if product_base is None and hasattr(eol_find_product_folder, "get_products_root"):
                product_base = eol_find_product_folder.get_products_root()
            product_dir = resolve_product_family_dir(
                text,
                product_dir_raw,
                product_base,
            )

        spec_path = original_find_product_spec_v2(product_dir)
        return product_dir, spec_path

    eol_requirements_doc.resolve_product_spec_from_scan = resolve_product_spec_from_scan


def _patch_eol_so_test_calibration_restore(
    unit_serial_number: str | None,
    motor_number: str | None,
) -> None:
    if not (is_so_unit(unit_serial_number) and str(motor_number or "").strip() == "0"):
        return

    from managers import test_manager as eol_test_manager

    original_test_calibration = eol_test_manager.TestRunner.test_calibration
    original_position_ready = eol_test_manager.TestRunner._controller_position_ready_or_raise
    original_show_current_zero = getattr(eol_test_manager.TestRunner, "show_current_zero", None)

    try:
        eol_full_calibration = importlib.import_module("logic.FullCalibration")
    except Exception as exc:
        print(f"[WARN] Could not patch EOL controller restart helper: {exc}")
    else:
        def restart_controller_without_owon(
            can,
            mic,
            node: int,
            can_bitrate: int,
            power_cycle_wait_fn=None,
        ):
            power_cycled = False
            if power_cycle_wait_fn is not None:
                print("[STATUS] Restarting EOL controller power through relay control.")
                power_cycled = bool(power_cycle_wait_fn(600.0))
            if not power_cycled and mic and getattr(mic, "added_node", None):
                try:
                    from utils.config_processing import nmt_reset_node_compat

                    print("[STATUS] Restarting EOL controller through CAN NMT reset.")
                    nmt_reset_node_compat(mic.added_node.nmt)
                except Exception as exc:
                    print(f"[WARN] Failed to request EOL controller reset: {exc}")
            try:
                can.close_can()
            except Exception as exc:
                print(f"[WARN] Failed to close EOL CAN before restart: {exc}")
            if not power_cycled:
                time.sleep(3.0)

            eol_driver_can = importlib.import_module("drivers.driver_can")
            eol_driver_micontrol = importlib.import_module("drivers.driver_miControlF35")
            new_can = eol_driver_can.DriverCan(can_bitrate=can_bitrate)
            new_mic = eol_driver_micontrol.MicontrolF35_CAN(
                can=new_can.can_network,
                node=node,
            )
            if not getattr(new_mic, "added_node", None):
                print("[ERROR] Could not add EOL CAN node after restart.")
                return None, None
            new_mic.clear_errors()
            return new_can, new_mic

        eol_full_calibration.restart_controller = restart_controller_without_owon

    def set_eol_relay_mask(arduino, mask: int, label: str) -> None:
        target = int(mask) & 0x1FFF
        if hasattr(arduino, "_set_relays_bits"):
            if arduino._set_relays_bits(target):
                print(f"[INFO] {label}: relay mask set to 0x{target:03X}.")
                return
        command = ",".join(
            f"q{relay_number}={1 if target & (1 << (relay_number - 1)) else 0}"
            for relay_number in range(1, 14)
        )
        if hasattr(arduino, "send_and_confirm_relay_state"):
            if arduino.send_and_confirm_relay_state(command):
                print(f"[INFO] {label}: relay mask confirmed 0x{target:03X}.")
                return
        if hasattr(arduino, "set_relay_state") and arduino.set_relay_state(command):
            print(f"[INFO] {label}: relay mask set to 0x{target:03X}.")
            return
        raise RuntimeError(f"Could not set EOL relay mask 0x{target:03X} for {label}.")

    def eol_relay_power_cycle_and_reconnect(self, info: dict[str, object]) -> None:
        can_driver = info.get("can")
        node = int(info.get("node") or DEFAULT_NODE_ID)
        can_bitrate = int(float(info.get("can_bitrate") or DEFAULT_CAN_BITRATE))
        try:
            if can_driver is not None:
                can_driver.close_can()
        except Exception as exc:
            print(f"[WARN] Failed to close EOL CAN before relay power cycle: {exc}")

        print("[STATUS] EOL TestCalibration passed. Relay power-cycling controller before zero return.")
        set_eol_relay_mask(self.arduino, 0, "EOL controller restart power off")
        time.sleep(CONTROLLER_POWER_CYCLE_OFF_S)
        set_eol_relay_mask(
            self.arduino,
            controller_power_relay_mask(),
            "EOL controller restart power on",
        )
        time.sleep(CONTROLLER_POWER_ON_SETTLE_S)

        eol_driver_can = importlib.import_module("drivers.driver_can")
        eol_driver_micontrol = importlib.import_module("drivers.driver_miControlF35")
        new_can = eol_driver_can.DriverCan(can_bitrate=can_bitrate)
        new_controller = eol_driver_micontrol.MicontrolF35_CAN(
            can=new_can.can_network,
            node=node,
        )
        if not getattr(new_controller, "added_node", None):
            try:
                new_can.close_can()
            except Exception:
                pass
            raise RuntimeError(f"Could not reconnect EOL controller node {node} after relay power cycle.")
        new_controller.clear_errors()
        info["can"] = new_can
        info["controller"] = new_controller
        self.controller = new_controller
        print("[INFO] EOL controller reconnected after relay power cycle.")

    def test_calibration_result_ok(result: object) -> bool:
        if result is None or not hasattr(result, "columns"):
            return False
        try:
            return not eol_test_manager.TestRunner._result_table_failed(result)
        except Exception as exc:
            print(f"[WARN] Could not evaluate EOL TestCalibration result table: {exc}")
            return False

    def mark_visual_zero_informational(result):
        if result is None or not hasattr(result, "columns"):
            return result
        if "Parameters" not in result.columns or "Match" not in result.columns:
            return result
        try:
            mask = result["Parameters"].astype(str).str.strip().str.lower() == "visual zero angle"
            result.loc[mask, "Match"] = "Info"
            if "Details" in result.columns:
                result.loc[
                    mask,
                    "Details",
                ] = (
                    "Camera angle is recorded for reference only; "
                    "EOL pass/fail uses the controller zero position."
                )
        except Exception as exc:
            print(f"[WARN] Could not mark EOL visual zero row as informational: {exc}")
        return result

    if original_show_current_zero is not None:
        def show_current_zero_visual_info(self):
            return mark_visual_zero_informational(original_show_current_zero(self))

    def test_calibration_with_restore(self, info, product_parameters):
        TestCalibration = importlib.import_module("tests.TestCalibration")
        original_return_controller_to_zero = getattr(
            TestCalibration,
            "return_controller_to_zero",
            None,
        )
        zero_return_rpm = ZERO_MOVE_RPM

        def defer_return_controller_to_zero(_controller, rpm=ZERO_MOVE_RPM):
            nonlocal zero_return_rpm
            zero_return_rpm = rpm
            print(
                "[INFO] EOL zero return deferred until TestCalibration result is PASS "
                "and relay power cycle is complete."
            )

        if original_return_controller_to_zero is not None:
            TestCalibration.return_controller_to_zero = defer_return_controller_to_zero
        result = None
        try:
            result = original_test_calibration(self, info, product_parameters)
        finally:
            if original_return_controller_to_zero is not None:
                TestCalibration.return_controller_to_zero = original_return_controller_to_zero
            restore_controller_after_test_calibration(
                getattr(self, "controller", None),
                label="EOL TestCalibration",
                reason="post-test",
                ssi_encoder_enable=bool(getattr(self, "ssi_encoder_restore", True)),
            )
        if test_calibration_result_ok(result):
            eol_relay_power_cycle_and_reconnect(self, info)
            restore_controller_after_test_calibration(
                getattr(self, "controller", None),
                label="EOL TestCalibration",
                reason="post-relay-restart",
                ssi_encoder_enable=bool(getattr(self, "ssi_encoder_restore", True)),
            )
            if original_return_controller_to_zero is not None:
                original_return_controller_to_zero(
                    getattr(self, "controller", None),
                    rpm=zero_return_rpm,
                )
                time.sleep(2.0)
            restore_controller_after_test_calibration(
                getattr(self, "controller", None),
                label="EOL TestCalibration",
                reason="post-zero-return",
                ssi_encoder_enable=bool(getattr(self, "ssi_encoder_restore", True)),
            )
        return result

    def position_ready_with_restore_retry(self, rpm=ZERO_MOVE_RPM):
        try:
            return original_position_ready(self, rpm=rpm)
        except Exception as first_exc:
            print(
                "[WARN] Controller position-ready check failed after EOL TestCalibration; "
                f"restoring SSI and retrying once. ({first_exc})"
            )
            restore_controller_after_test_calibration(
                getattr(self, "controller", None),
                label="EOL TestCalibration",
                reason="position-ready retry",
                ssi_encoder_enable=bool(getattr(self, "ssi_encoder_restore", True)),
            )
            return original_position_ready(self, rpm=rpm)

    eol_test_manager.TestRunner.test_calibration = test_calibration_with_restore
    eol_test_manager.TestRunner._controller_position_ready_or_raise = position_ready_with_restore_retry
    if original_show_current_zero is not None:
        eol_test_manager.TestRunner.show_current_zero = show_current_zero_visual_info


def _run_eol_case_program(
    tester_name: str,
    unit_serial_number: str | None = None,
    motor_number: str | None = None,
    manual_power: bool = False,
    ssi_encoder_restore: bool = True,
):
    with _external_eol_import_scope():
        mobotic_eol = _load_eol_case_module()
        _patch_eol_product_family_resolution()
        _patch_eol_so_test_calibration_restore(unit_serial_number, motor_number)
        kwargs = {
            "tester_name": tester_name,
            "test_mode": "full",
            "manual_power": manual_power,
            "ssi_encoder_restore": bool(ssi_encoder_restore),
        }
        if unit_serial_number:
            kwargs["unit_serial_number"] = unit_serial_number
        if motor_number:
            kwargs["motor_number"] = motor_number
        return mobotic_eol.main(**kwargs)


def run_mobotic_eol(
    tester_name: str | None = None,
    context: ProductContext | None = None,
    unit_serial_number: str | None = None,
    motor_number: str | None = None,
    manual_power: bool = False,
    ssi_encoder_restore: bool = True,
):
    tester_name = str(tester_name or "").strip()
    if not tester_name:
        raise RuntimeError("Tester name is required for EOL.")

    previous_noninteractive = os.environ.get("ST_NONINTERACTIVE")
    os.environ["ST_NONINTERACTIVE"] = "1"
    try:
        with STATE.lock:
            has_relay_arduino = STATE.relay_arduino is not None
        if has_relay_arduino and not manual_power:
            print("[INFO] Releasing GUI relay Arduino before starting EOL-case.")
            STATE.close_relay_arduino()
        if context is None:
            return _run_eol_case_program(
                tester_name=tester_name,
                unit_serial_number=str(unit_serial_number or "").strip() or None,
                motor_number=str(motor_number or "").strip() or None,
                manual_power=manual_power,
                ssi_encoder_restore=ssi_encoder_restore,
            )

        STATE.set_product_context(context)
        prepare_report_for_context(context)
        print("[INFO] Starting EOL-case mobotic_EOL program from resolved product context.")
        return _run_eol_case_program(
            tester_name=tester_name,
            unit_serial_number=context.qr_code,
            motor_number=str(motor_number or "").strip() or None,
            manual_power=manual_power,
            ssi_encoder_restore=ssi_encoder_restore,
        )
    finally:
        if previous_noninteractive is None:
            os.environ.pop("ST_NONINTERACTIVE", None)
        else:
            os.environ["ST_NONINTERACTIVE"] = previous_noninteractive


def open_controller(
    node: int = DEFAULT_NODE_ID,
    enable: bool = True,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
):
    from drivers.driver_can import DriverCan
    import drivers.driver_miControlF35 as driver_miControlF35

    driver_miControlF35 = importlib.reload(driver_miControlF35)
    MicontrolF35_CAN = driver_miControlF35.MicontrolF35_CAN

    can = DriverCan(can_bitrate=can_bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        can.close_can()
        raise RuntimeError(f"Could not add CAN node {node}.")
    if enable:
        mic.enabled(True)
    return can, mic


def acquire_controller(
    node: int = DEFAULT_NODE_ID,
    enable: bool = True,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
):
    can, mic = STATE.get_manual_controller(node, can_bitrate)
    if mic is not None:
        if enable:
            mic.enabled(True)
            STATE.set_controller_enabled(node, True)
        return can, mic, False

    can, mic = open_controller(node, enable=enable, can_bitrate=can_bitrate)
    return can, mic, True


def release_controller(can, owned: bool) -> None:
    if not owned:
        return
    try:
        can.close_can()
    except Exception:
        pass


def _safe_controller_read(mic, method_name: str):
    try:
        method = getattr(mic, method_name)
        return method()
    except Exception as exc:
        print(f"[WARN] Could not read {method_name}: {exc}")
        return None


def read_controller_identity(
    node: int,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> dict[str, object]:
    can, mic, owned = acquire_controller(node, enable=False, can_bitrate=can_bitrate)
    try:
        return read_controller_identity_from_mic(mic)
    finally:
        release_controller(can, owned)


def return_motor_to_zero_for_run_all(
    node: int,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
    context: str = "run all final zero",
) -> str:
    can, mic, owned = acquire_controller(node, can_bitrate=can_bitrate)
    try:
        steering_pos = move_controller_to_zero(
            mic,
            context=context,
            require_ssi_ready=True,
        )
        return "OK"
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def load_steering_script_with_node_fallback(context: ProductContext) -> dict[str, object]:
    from logic import FlashSteeringScript

    candidate_nodes = [STANDARD_NODE_ID]
    if context.steering_node_id not in candidate_nodes:
        candidate_nodes.append(context.steering_node_id)

    last_error = None
    for candidate_node in candidate_nodes:
        try:
            label = (
                "standard"
                if candidate_node == STANDARD_NODE_ID
                else "product specification"
            )
            print(
                f"[INFO] Loading steering script at {label} node {candidate_node}..."
            )
            script_info = FlashSteeringScript.main(
                desired_node_id=candidate_node,
                qr_info=context.script_info(),
            ) or {}
            if candidate_node != STANDARD_NODE_ID:
                print(
                    f"[INFO] Steering script loaded using product node {candidate_node}; "
                    "unit was already configured to the product Node ID."
                )
            return script_info
        except Exception as exc:
            last_error = exc
            print(f"[WARN] Steering script load failed on node {candidate_node}: {exc}")

    raise RuntimeError(
        "Steering script could not be loaded on standard node "
        f"{STANDARD_NODE_ID} or product node {context.steering_node_id}: {last_error}"
    )


def run_load_script_config_details(context: ProductContext) -> dict[str, object]:
    script_info = load_steering_script_with_node_fallback(context)
    node = context.steering_node_id
    print(f"[INFO] Steering script loaded. Loading MU config on product node {node}...")
    if not run_load_config(node=node, can_bitrate=context.can_bitrate):
        return {
            **script_info,
            "ok": False,
            "node": node,
            "configuration_error_status": "Configuration failed",
        }
    print("[INFO] Script and MU config loaded. Checking that controller error -1092 is absent...")
    check_ok, configuration_status = run_ssi_configuration_check_status(
        node=node,
        can_bitrate=context.can_bitrate,
    )
    return {
        **script_info,
        "ok": check_ok,
        "node": node,
        "configuration_error_status": configuration_status,
    }


def run_load_script_config(context: ProductContext) -> bool:
    return bool(run_load_script_config_details(context).get("ok"))


def run_load_config(
    node: int = DEFAULT_NODE_ID,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> bool:
    from logic import FlashConfigZero

    FlashConfigZero = importlib.reload(FlashConfigZero)
    from logic.FlashConfigZero import MU_Handle, mu, write_just_conf

    can, mic, owned = acquire_controller(node, can_bitrate=can_bitrate)

    try:
        handle = MU_Handle()
        ok = write_just_conf(mu, handle, mic, SERIAL_LAST4)
        if not ok:
            raise RuntimeError("MU config load failed.")
        return True
    finally:
        release_controller(can, owned)


def run_ssi_configuration_check_status(
    node: int = DEFAULT_NODE_ID,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> tuple[bool, str]:
    can, mic, owned = acquire_controller(node, can_bitrate=can_bitrate)
    try:
        ok = bool(mic.get_extended_ssi())
        error_value = getattr(mic, "last_ssi_configuration_error", None)
        if not ok:
            status = "-1092" if error_value == -1092 else f"Error {error_value}"
            print(f"[RESULT] ssi_configuration_check ok=False error={status}")
            return False, status
        print("[RESULT] ssi_configuration_check ok=True error=0")
        return True, "No error"
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def run_ssi_configuration_check(
    node: int = DEFAULT_NODE_ID,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> bool:
    ok, _status = run_ssi_configuration_check_status(node=node, can_bitrate=can_bitrate)
    return ok


def run_spin_check_90(
    node: int = DEFAULT_NODE_ID,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> bool:
    can, mic, owned = acquire_controller(node, can_bitrate=can_bitrate)
    try:
        ok = spin_to_angle_and_verify(
            mic,
            angle_deg=SPIN_CHECK_DEG,
            rpm=SPIN_CHECK_RPM,
            timeout_s=SPIN_CHECK_TIMEOUT_S,
        )
        if ok:
            print(f"[RESULT] spin_check_{SPIN_CHECK_DEG:.0f}_deg ok=True")
            return True

        print(f"[ERROR] Spin check failed; writing controller error {SPIN_FAILURE_ERROR}.")
        mic.set_error(SPIN_FAILURE_ERROR)
        print(f"[RESULT] spin_check_{SPIN_CHECK_DEG:.0f}_deg ok=False error={SPIN_FAILURE_ERROR}")
        return False
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def run_show_current_zero(
    node: int = DEFAULT_NODE_ID,
    desired_angle: float = ZERO_ANGLE_DEG,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
) -> bool:
    can, mic, owned = acquire_controller(node, can_bitrate=can_bitrate)
    try:
        print("[INFO] Show Current Zero flow version: controller-reference-v2")
        print(
            "[STATUS] Showing current zero using the controller's current steering-position "
            "reference; no restart or encoder reconfiguration."
        )
        steering_pos = move_controller_to_zero(
            mic,
            context="show current zero",
            require_ssi_ready=False,
        )
        visual_angle = read_camera_angle_deg("show current zero")
        visual_error = angle_error_deg(visual_angle, desired_angle)
        print(
            "[RESULT] Show current zero -> "
            f"controller_position={steering_pos} "
            f"target_position=0 "
            f"tolerance_counts={ZERO_POSITION_TOLERANCE_COUNTS} "
            f"visual_angle={visual_angle:.2f} "
            f"target_angle={desired_angle:.2f} "
            f"visual_error={visual_error:.2f} "
            f"visual_tolerance={ZERO_VISUAL_TOLERANCE_DEG:.2f}"
        )
        ok = (
            steering_pos is not None
            and abs(steering_pos) <= ZERO_POSITION_TOLERANCE_COUNTS
            and visual_error <= ZERO_VISUAL_TOLERANCE_DEG
        )
        return ok
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def prepare_controller_ssi_encoder(mic, context: str) -> tuple[int | None, int | None, int | None, bool]:
    preferred = CONTROLLER_ENCODER_DIGITAL_OUTPUT
    candidates = (preferred, not preferred)
    last_status = None
    last_direct_pos = None
    last_steering_pos = None
    last_mux = preferred

    mic.clear_errors()
    mic.clear_errors()

    for mux in candidates:
        last_mux = mux
        if mic.SSI_encoder(False):
            print("[INFO] SSI encoder disabled before mux selection.")
        else:
            print("[WARN] SSI encoder disable did not report success before mux selection.")
        time.sleep(0.25)
        mic.set_digital_output(mux)
        print(
            f"[INFO] Controller encoder mux selected before {context}: "
            f"digital_output={mux}"
        )
        time.sleep(0.25)
        mic.clear_errors()
        mic.clear_errors()
        if mic.SSI_encoder(True):
            print("[INFO] SSI encoder enabled before zero move.")
        else:
            print("[WARN] SSI encoder enable did not report success before zero move.")

        deadline = time.monotonic() + 4.0
        while True:
            last_status = mic.get_ssi_encoder_status()
            last_direct_pos = mic.get_ssi_direct_position()
            last_steering_pos = mic.get_steering_pos()
            print(
                "[INFO] Controller SSI state before zero move: "
                f"mux={mux} status={last_status} "
                f"direct_position={last_direct_pos} steering_position={last_steering_pos}"
            )
            if last_status == SSI_READY_STATUS:
                return last_status, last_direct_pos, last_steering_pos, mux
            if time.monotonic() >= deadline:
                break
            time.sleep(0.5)

        print(
            "[WARN] SSI encoder did not reach ready status "
            f"{SSI_READY_STATUS} with digital_output={mux}; trying next mux state."
        )

    raise RuntimeError(
        "Controller SSI encoder is not ready for motion: "
        f"last mux={last_mux} status={last_status} "
        f"direct_position={last_direct_pos} steering_position={last_steering_pos}."
    )


def move_controller_to_zero(
    mic,
    context: str = "zero check",
    require_ssi_ready: bool = True,
) -> int | None:
    initial_pos = mic.get_steering_pos()
    print(f"[INFO] Controller steering position before {context}: {initial_pos}")

    if require_ssi_ready:
        _ssi_status, _ssi_direct_pos, start_pos, _mux = prepare_controller_ssi_encoder(mic, context)
    else:
        mic.clear_errors()
        start_pos = initial_pos
        if start_pos is None:
            raise RuntimeError(
                f"Could not read controller steering position before {context}."
            )
        print(
            f"[INFO] Using existing controller steering reference for {context}: "
            f"position={start_pos}; SSI readiness check skipped."
        )

    if start_pos is not None and abs(start_pos) <= ZERO_POSITION_TOLERANCE_COUNTS:
        print(
            "[INFO] Controller is already at steering position 0; "
            f"position={start_pos} counts within tolerance "
            f"+/-{ZERO_POSITION_TOLERANCE_COUNTS}; "
            "no physical move needed."
        )
        return start_pos

    print("[STATUS] Commanding controller steering position 0.")

    mic.set_device_mode_position()
    mic.set_RPM(ZERO_MOVE_RPM)
    mic.set_steering_RPM(ZERO_MOVE_RPM)
    mic.enabled(True)
    try:
        mic.set_steering_pos(0)
    except Exception as exc:
        print(f"[WARN] Absolute zero move command failed: {exc}")
        if start_pos is None:
            raise
        print(f"[STATUS] Trying relative zero move by {-int(start_pos)} counts.")
        try:
            mic.set_steering_relative(-int(start_pos))
        except Exception as rel_exc:
            raise RuntimeError(
                "Controller refused both absolute and relative zero move commands. "
                f"Initial move error: {exc}; relative move error: {rel_exc}"
            ) from rel_exc

    deadline = time.monotonic() + ZERO_MOVE_TIMEOUT_S
    steering_pos = start_pos
    velocity = None
    while time.monotonic() < deadline:
        time.sleep(0.25)
        steering_pos = mic.get_steering_pos()
        velocity = mic.get_velocity()
        if (
            steering_pos is not None
            and abs(steering_pos) <= ZERO_POSITION_TOLERANCE_COUNTS
            and (velocity is None or abs(velocity) <= 1)
        ):
            break

    time.sleep(ZERO_MOVE_SETTLE_S)
    steering_pos = mic.get_steering_pos()
    velocity = mic.get_velocity()
    print(
        f"[INFO] Controller steering position after {context}: "
        f"{steering_pos} velocity={velocity}"
    )
    if steering_pos is not None and abs(steering_pos) > ZERO_POSITION_TOLERANCE_COUNTS:
        error_code = mic.get_error_code()
        raise RuntimeError(
            "Controller did not reach steering position 0: "
            f"position={steering_pos} velocity={velocity} error={error_code}."
        )
    if steering_pos is None:
        error_code = mic.get_error_code()
        raise RuntimeError(
            "Controller steering position could not be read after zero move: "
            f"velocity={velocity} error={error_code}."
        )
    return steering_pos


def spin_to_angle_and_verify(mic, angle_deg: float, rpm: int, timeout_s: float) -> bool:
    target_counts = int(round(angle_deg * ENCODER_COUNTS_PER_REV / 360.0))
    start_pos = mic.get_actual_position()
    print(
        f"[INFO] Commanding relative {angle_deg:.0f} deg spin "
        f"({target_counts} counts) at {rpm} RPM; start_pos={start_pos}"
    )

    mic.clear_errors()
    mic.set_device_mode_position()
    mic.set_RPM(rpm)
    mic.enabled(True)
    mic.set_steering_relative(target_counts)

    deadline = time.monotonic() + timeout_s
    last_pos = start_pos
    last_velocity = None
    while time.monotonic() < deadline:
        time.sleep(0.2)
        last_pos = mic.get_actual_position()
        last_velocity = mic.get_velocity()
        moved = (
            start_pos is not None
            and last_pos is not None
            and abs(last_pos - start_pos) >= 10
        )
        spinning = last_velocity is not None and abs(last_velocity) > 0
        if moved or spinning:
            print(
                f"[INFO] Spin verified: pos={last_pos} "
                f"delta={None if start_pos is None or last_pos is None else last_pos - start_pos} "
                f"velocity={last_velocity}"
            )
            return True

    print(
        f"[ERROR] No spin detected after {timeout_s:.1f}s: "
        f"start_pos={start_pos} last_pos={last_pos} velocity={last_velocity}"
    )
    return False


def read_camera_angle_deg(context: str) -> float:
    from drivers.driver_cam_st import AngleDetection

    for attempt in range(1, ANGLE_READ_ATTEMPTS + 1):
        print(f"[STATUS] Waiting {ANGLE_SETTLE_S:.1f}s for camera angle to stabilize.")
        time.sleep(ANGLE_SETTLE_S)
        print(
            f"[STATUS] Reading camera angle for {context} "
            f"({ANGLE_SAMPLES} samples, timeout {ANGLE_TIMEOUT_S:.0f}s, "
            f"attempt {attempt}/{ANGLE_READ_ATTEMPTS})."
        )
        angle = AngleDetection(debug=False, return_after=ANGLE_SAMPLES, timeout_s=ANGLE_TIMEOUT_S)
        if angle is not None:
            print(f"[INFO] Camera angle for {context}: {float(angle):.2f} deg")
            return float(angle)
        if attempt < ANGLE_READ_ATTEMPTS:
            print("[WARN] Camera angle was not detected; retrying once.")

    raise RuntimeError(
        f"Could not measure steering angle during {context}. "
        "Check that the webcam is connected, accessible, not already in use, "
        "and that the marker is visible. If needed, set ST_CAMERA_ID to the correct camera index."
    )


def run_zeroing(
    node: int = DEFAULT_NODE_ID,
    desired_angle: float = ZERO_ANGLE_DEG,
    can_bitrate: int = DEFAULT_CAN_BITRATE,
    result_callback=None,
) -> None:
    from logic import FlashConfigZero

    FlashConfigZero = importlib.reload(FlashConfigZero)
    from logic.FlashConfigZero import write_des_zero_process

    zero_saved = write_des_zero_process(
        serial_last4=SERIAL_LAST4,
        node=node,
        desired_angle=desired_angle,
        can_bitrate=can_bitrate,
        read_angle_fn=lambda: read_camera_angle_deg("zeroing"),
        prepare_controller_fn=prepare_controller_ssi_encoder,
        power_cycle_wait_fn=automatic_power_cycle_for_zero,
        preserve_current_encoder_config=True,
        result_callback=result_callback,
    )
    if not zero_saved:
        raise RuntimeError("Zeroing parameters were not saved to both encoders.")


STATE = AppState()


def startup_product_scan_and_can_check() -> None:
    with STATE.lock:
        scan_option = STATE.scan_option
    if scan_option != SCAN_OPTION_QR_CAMERA:
        STATE.request_product_scan_input()
        return
    run_product_scan_and_can_check(None)


def run_product_scan_and_can_check(scan_text: object | None) -> None:
    if not STATE.begin_product_scan():
        return

    try:
        result = gui_safe_execute(
            scan_product_context if scan_text is None else resolve_product_scan_text,
            *(() if scan_text is None else (scan_text,)),
            spinner_text=(
                "Scanning product QR code"
                if scan_text is None
                else "Loading product specification"
            ),
        )
        STATE.set_product_scan_result(result)
    except Exception as exc:
        STATE.append_log(format_exc())
        STATE.set_product_scan_failed(f"Product QR/specification scan failed: {exc}")
        return

    if result.context is None:
        return

    if not controller_power_relays_are_on():
        message = controller_power_off_message()
        STATE.mark_can_not_connected(
            node=result.context.steering_node_id,
            bitrate=result.context.can_bitrate,
            message=message,
        )
        STATE.append_status(message, mark_error=False)
        return

    ok, error = STATE.begin_can_check(DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE)
    if not ok:
        STATE.append_status(error, is_error=True, mark_error=False)
        return

    try:
        connected, node, bitrate, message, context = gui_safe_execute(
            _check_gui_can_with_st_can0_retry,
            explicit_target=False,
            node=DEFAULT_NODE_ID,
            bitrate=DEFAULT_CAN_BITRATE,
            spinner_text="Checking CAN connection",
        )
        public_message = message if connected else "CAN not connected."
        STATE.finish_can_check(
            node,
            bitrate,
            connected,
            public_message if not connected else message,
            context=context,
            mark_error=False,
        )
        STATE.append_status(message, is_error=not connected, mark_error=False)
    except Exception as exc:
        STATE.append_log(format_exc())
        message = f"CAN startup check failed after product scan. ({exc})"
        STATE.finish_can_check(
            DEFAULT_NODE_ID,
            DEFAULT_CAN_BITRATE,
            False,
            "CAN not connected.",
            mark_error=False,
        )
        STATE.append_status(message, is_error=True, mark_error=False)


def kill_all_programs() -> None:
    STATE.append_status("Kill All Programs pressed. Stopping GUI process.", is_error=True)

    def force_exit() -> None:
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=force_exit, daemon=True).start()


def parse_manual_rpm(raw_value: str) -> int:
    rpm = int(raw_value)
    if rpm == 0:
        return rpm
    if not MANUAL_SPIN_MIN_RPM <= abs(rpm) <= MANUAL_SPIN_MAX_RPM:
        raise ValueError(
            f"Manual RPM must be 0 or between +/-{MANUAL_SPIN_MIN_RPM} "
            f"and +/-{MANUAL_SPIN_MAX_RPM}."
        )
    return rpm


def parse_manual_seq(raw_value: str) -> int:
    seq = int(raw_value)
    if seq < 0:
        raise ValueError("Manual command sequence must be positive.")
    return seq


def parse_can_node(raw_value: str) -> int:
    node = int(raw_value)
    if not 1 <= node <= 127:
        raise ValueError("CAN node ID must be between 1 and 127.")
    return node


def parse_can_bitrate(raw_value: str) -> int:
    bitrate = int(raw_value)
    if not 1 <= bitrate <= 1000:
        raise ValueError("CAN bitrate must be between 1 and 1000 kbit/s.")
    return bitrate


def parse_enabled(raw_value: str) -> bool:
    if raw_value in {"1", "true", "True", "on"}:
        return True
    if raw_value in {"0", "false", "False", "off"}:
        return False
    raise ValueError("Enabled value must be 1 or 0.")


def parse_scan_option(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if value not in SCAN_OPTIONS:
        raise ValueError("Scan option must be QR Camera, QR Scanner, Barcode Scanner, or Manual.")
    return value


def parse_relay_action(raw_value: str) -> str:
    if raw_value in {
        "power_on",
        "power_off",
        "restart",
        "operation",
        "test_all",
        "end_all",
        "set_mask",
        "check_termination",
    }:
        return raw_value
    raise ValueError(
        "Relay action must be power_on, power_off, restart, operation, test_all, end_all, set_mask, or check_termination."
    )


def parse_relay_mask(raw_value: str) -> int:
    try:
        mask = int(str(raw_value).strip(), 0)
    except Exception as exc:
        raise ValueError("Relay mask must be an integer.") from exc
    if not 0 <= mask <= 0x1FFF:
        raise ValueError("Relay mask must be in range 0..0x1FFF.")
    return mask


def _relay_mask(*relay_numbers: int) -> int:
    mask = 0
    for relay_number in relay_numbers:
        if not 1 <= int(relay_number) <= 13:
            raise ValueError(f"Relay q{relay_number} is outside q1..q13.")
        mask |= 1 << (int(relay_number) - 1)
    return mask


def controller_power_relay_mask() -> int:
    return _relay_mask(*CONTROLLER_POWER_RELAYS)


def controller_power_relays_are_on() -> bool:
    with STATE.lock:
        arduino = STATE.relay_arduino
    if arduino is None:
        return False
    try:
        relay_mask = int(arduino.get_relays()) & 0x1FFF
    except Exception as exc:
        print(f"[WARN] Could not read controller power relay state: {exc}")
        return False
    return (relay_mask & controller_power_relay_mask()) == controller_power_relay_mask()


def controller_power_off_message() -> str:
    return "Controller power relays are OFF. Press Power On before CAN check."


def operation_relay_mask(motor_voltage: object | None = None) -> int:
    return controller_power_relay_mask()


def _confirmed_set_relays(arduino, mask: int, label: str, stable_reads: int = 3) -> None:
    target = int(mask) & 0x1FFF
    if not arduino._set_relays_bits(target):
        raise RuntimeError(f"Failed to set {label} relay mask 0x{target:03X}.")

    stable = 0
    last = None
    for _ in range(10):
        try:
            last = arduino.get_relays() & 0x1FFF
            if last == target:
                stable += 1
                if stable >= stable_reads:
                    print(f"[INFO] {label}: relay mask confirmed 0x{target:03X}.")
                    return
            else:
                stable = 0
        except Exception:
            stable = 0
        time.sleep(0.03)

    raise RuntimeError(
        f"Relay readback mismatch for {label}: expected 0x{target:03X}, "
        f"last={None if last is None else f'0x{last:03X}'}"
    )


def _get_or_connect_relay_arduino(timeout_s: float = 8.0):
    deadline = time.monotonic() + timeout_s
    while True:
        with STATE.lock:
            arduino = STATE.relay_arduino
            connecting = STATE.relay_connecting
            message = STATE.relay_connection_message
        if arduino is not None:
            return arduino
        if not connecting:
            STATE.connect_relay_arduino()
            with STATE.lock:
                arduino = STATE.relay_arduino
                message = STATE.relay_connection_message
            if arduino is not None:
                return arduino
        if time.monotonic() >= deadline:
            raise RuntimeError(message or "Relay Arduino is not connected.")
        time.sleep(0.1)


def _detach_manual_can_for_power_change(message: str) -> None:
    with STATE.lock:
        can = STATE._detach_manual_controller_locked(message=message)
    if can is not None:
        try:
            can.close_can()
        except Exception:
            pass


def _controller_reconnect_after_relay_power_on(
    node: int | None = None,
    can_bitrate: int | None = None,
    context: ProductContext | None = None,
) -> tuple[bool, str]:
    if context is None:
        with STATE.lock:
            context = STATE.current_product_context
    if context is not None:
        return check_can_connection(
            context.steering_node_id,
            can_bitrate=context.can_bitrate,
            create_report=False,
            context=context,
        )
    if node is not None:
        return check_can_connection(
            node,
            can_bitrate=can_bitrate or DEFAULT_CAN_BITRATE,
            create_report=False,
        )
    connected, _node, _bitrate, message, _context = check_standard_then_product_can_connection()
    return connected, message


def restart_st_can0_service(
    service_name: str = ST_CAN_SERVICE_NAME,
    timeout_s: float = ST_CAN_SERVICE_RESTART_TIMEOUT_S,
) -> tuple[bool, str]:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, "systemctl is not available; could not restart st-can0.service."

    print(f"[STATUS] Restarting {service_name} after CAN reconnect failure.")
    try:
        result = subprocess.run(
            [systemctl, "restart", service_name],
            text=True,
            capture_output=True,
            timeout=max(0.1, float(timeout_s)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"Restarting {service_name} timed out."
    except Exception as exc:
        return False, f"Could not restart {service_name}: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return False, f"Could not restart {service_name}: {detail or 'unknown error'}"
    return True, f"Restarted {service_name}."


def _retry_controller_reconnect_after_st_can0_restart(
    *,
    node: int | None,
    can_bitrate: int | None,
    context: ProductContext | None,
    first_failure: str,
) -> tuple[bool, str]:
    restart_ok, restart_message = restart_st_can0_service()
    STATE.append_status(restart_message, is_error=not restart_ok, mark_error=False)
    if not restart_ok:
        return False, f"{first_failure} {restart_message}"

    time.sleep(ST_CAN_SERVICE_RESTART_SETTLE_S)
    connected, retry_message = _controller_reconnect_after_relay_power_on(
        node=node,
        can_bitrate=can_bitrate,
        context=context,
    )
    if connected:
        STATE.append_status(f"{restart_message} {retry_message}")
        return True, f"{restart_message} {retry_message}"
    return False, f"{first_failure} {restart_message} Retry failed: {retry_message}"


def _check_gui_can_with_st_can0_retry(
    *,
    explicit_target: bool,
    node: int,
    bitrate: int,
) -> tuple[bool, int, int, str, ProductContext | None]:
    if explicit_target:
        connected, message = check_can_connection(
            node,
            can_bitrate=bitrate,
            create_report=False,
        )
        result_node = node
        result_bitrate = bitrate
        context = None
    else:
        connected, result_node, result_bitrate, message, context = (
            check_standard_then_product_can_connection()
        )
    if connected:
        return connected, result_node, result_bitrate, message, context

    restart_ok, restart_message = restart_st_can0_service()
    STATE.append_status(restart_message, is_error=not restart_ok, mark_error=False)
    if not restart_ok:
        return False, result_node, result_bitrate, f"{message} {restart_message}", context

    time.sleep(ST_CAN_SERVICE_RESTART_SETTLE_S)
    if explicit_target:
        connected, retry_message = check_can_connection(
            node,
            can_bitrate=bitrate,
            create_report=False,
        )
        result_node = node
        result_bitrate = bitrate
        retry_context = None
    else:
        connected, result_node, result_bitrate, retry_message, retry_context = (
            check_standard_then_product_can_connection()
        )
    if connected:
        return True, result_node, result_bitrate, f"{restart_message} {retry_message}", retry_context
    return (
        False,
        result_node,
        result_bitrate,
        f"{message} {restart_message} Retry failed: {retry_message}",
        retry_context,
    )


def set_controller_power_relays(
    enabled: bool,
    *,
    node: int | None = None,
    can_bitrate: int | None = None,
    reconnect: bool = True,
    context: ProductContext | None = None,
    fail_on_reconnect_error: bool = True,
) -> tuple[bool, str]:
    label = "ON" if enabled else "OFF"
    if not enabled:
        _detach_manual_can_for_power_change("Controller power relays are OFF.")

    arduino = _get_or_connect_relay_arduino()
    mask = controller_power_relay_mask() if enabled else 0
    _confirmed_set_relays(arduino, mask, f"controller power {label}")
    print(f"[STATUS] Controller power relays {label}: mask 0x{mask:03X}.")

    if not enabled:
        return True, "Controller power relays are OFF. CAN is disconnected until Power On."

    time.sleep(CONTROLLER_POWER_ON_SETTLE_S)
    if not reconnect:
        return True, f"Controller power relays are ON: mask 0x{mask:03X}."

    connected, message = _controller_reconnect_after_relay_power_on(
        node=node,
        can_bitrate=can_bitrate,
        context=context,
    )
    if not connected:
        connected, message = _retry_controller_reconnect_after_st_can0_restart(
            node=node,
            can_bitrate=can_bitrate,
            context=context,
            first_failure=message,
        )
    if not connected:
        if not fail_on_reconnect_error:
            can_node = context.steering_node_id if context is not None else node
            can_speed = context.can_bitrate if context is not None else can_bitrate
            STATE.mark_can_not_connected(node=can_node, bitrate=can_speed)
            print(f"[WARN] Controller power relays are ON, but {message}")
            return True, f"Controller power relays are ON: mask 0x{mask:03X}. {message}"
        return False, f"Controller power relays are ON, but {message}"
    return True, f"Controller power relays are ON. {message}"


def restart_controller_with_relays(
    *,
    node: int | None = None,
    can_bitrate: int | None = None,
    context: ProductContext | None = None,
    reconnect: bool = True,
    fail_on_reconnect_error: bool = True,
    off_seconds: float = CONTROLLER_POWER_CYCLE_OFF_S,
) -> tuple[bool, str]:
    _detach_manual_can_for_power_change("Restarting controller with relay power cycle...")
    arduino = _get_or_connect_relay_arduino()
    on_mask = controller_power_relay_mask()

    print("[STATUS] Controller relay restart: power OFF.")
    _confirmed_set_relays(arduino, 0, "controller restart power off")
    time.sleep(max(0.0, float(off_seconds)))

    print("[STATUS] Controller relay restart: power ON.")
    _confirmed_set_relays(arduino, on_mask, "controller restart power on")
    time.sleep(CONTROLLER_POWER_ON_SETTLE_S)
    if not reconnect:
        return True, "Controller relay restart complete. CAN reconnect deferred."

    connected, message = _controller_reconnect_after_relay_power_on(
        node=node,
        can_bitrate=can_bitrate,
        context=context,
    )
    if not connected:
        connected, message = _retry_controller_reconnect_after_st_can0_restart(
            node=node,
            can_bitrate=can_bitrate,
            context=context,
            first_failure=message,
        )
    if not connected:
        if not fail_on_reconnect_error:
            can_node = context.steering_node_id if context is not None else node
            can_speed = context.can_bitrate if context is not None else can_bitrate
            STATE.mark_can_not_connected(node=can_node, bitrate=can_speed)
            print(f"[WARN] Controller relay restart finished, but {message}")
            return True, f"Controller relay restart complete. {message}"
        return False, f"Controller relay restart finished, but {message}"
    return True, f"Controller relay restart complete. {message}"


def restart_controller_with_relays_for_task(context: ProductContext, reason: str) -> bool:
    message = f"{reason} Restarting controller with relays."
    print(f"[STATUS] {message}")
    STATE.append_status(message)
    try:
        ok, result_message = restart_controller_with_relays(
            context=context,
            off_seconds=CONTROLLER_POWER_CYCLE_OFF_S,
        )
    except Exception as exc:
        result_message = f"Relay controller restart failed: {exc}"
        print(f"[WARN] {result_message}")
        STATE.append_status(result_message, is_error=True, mark_error=False)
        return False
    STATE.append_status(result_message, is_error=not ok, mark_error=False)
    if not ok:
        print(f"[WARN] {result_message}")
    return ok


def automatic_controller_relay_restart(_timeout_s: float) -> bool:
    with STATE.lock:
        context = STATE.current_product_context
        node = STATE.can_connection_node
        bitrate = STATE.can_connection_bitrate
    try:
        ok, message = restart_controller_with_relays(
            node=node,
            can_bitrate=bitrate,
            context=context,
            off_seconds=CONTROLLER_POWER_CYCLE_OFF_S,
        )
    except Exception as exc:
        message = f"Automatic relay restart failed: {exc}"
        print(f"[ERROR] {message}")
        STATE.append_status(message, is_error=True)
        return False
    STATE.append_status(message, is_error=not ok)
    if not ok:
        print(f"[ERROR] {message}")
    return ok


def current_motor_supply_voltage() -> object | None:
    with STATE.lock:
        context = STATE.current_product_context
    if context is None:
        return None
    try:
        params = read_product_spec_parameters(find_product_spec_path(context.product_dir))
        return params.get("Motor supply voltage")
    except Exception as exc:
        print(f"[WARN] Could not read motor supply voltage for relay group: {exc}")
        return None


def relay_snapshot(arduino, ok: bool = True) -> dict[str, object]:
    relays = {}
    voltage = "--"
    resistance = "--"
    current = "--"
    controller_power_on = False
    try:
        state = arduino.get_state()
        if isinstance(state, dict):
            relays = state.get("relay_states", {}) or {}
            voltage = state.get("voltage") if state.get("voltage") is not None else "--"
            resistance = state.get("resistance", "--")
            current = state.get("current", "--")
        relay_mask = int(arduino.get_relays()) & 0x1FFF
        controller_power_on = (
            relay_mask & controller_power_relay_mask()
        ) == controller_power_relay_mask()
    except Exception as exc:
        print(f"[WARN] Could not read relay state/measurements: {exc}")
    return {
        "ok": ok,
        "relays": relays,
        "voltage": voltage,
        "resistance": resistance,
        "current": current,
        "controller_power_relays_on": controller_power_on,
    }


def expected_can_termination_value() -> object | None:
    with STATE.lock:
        params = dict(STATE.current_product_params)
    return params.get("CAN Termination")


def _termination_expected_present(termination: object | None) -> bool:
    text = str(termination).strip().upper() if termination is not None else ""
    if text in {"YES", "TRUE", "ON", "120", "120.0"}:
        return True
    try:
        return float(text) == 120.0
    except Exception:
        return False


def _termination_expected_absent(termination: object | None) -> bool:
    text = str(termination).strip().upper() if termination is not None else ""
    if termination is None or text in {"", "NO", "FALSE", "OFF", "0", "0.0"}:
        return True
    try:
        return float(text) == 0.0
    except Exception:
        return False


def check_can_termination_with_relays(max_attempts: int = 3) -> dict[str, object]:
    arduino = _get_or_connect_relay_arduino()
    desired_mask = _relay_mask(6)

    _confirmed_set_relays(arduino, 0, "clear relays before CAN termination")
    _confirmed_set_relays(arduino, desired_mask, "CAN termination measurement relay")

    resistance = None
    try:
        for _ in range(max_attempts):
            try:
                value = arduino.get_resistance()
                if value is not None and not (isinstance(value, float) and value != value):
                    resistance = float(value)
                    break
            except Exception:
                pass
            time.sleep(0.05)
    finally:
        _confirmed_set_relays(arduino, 0, "clear relays after CAN termination")
        _detach_manual_can_for_power_change(
            "Controller power relays are OFF after CAN termination check."
        )

    if resistance is None:
        return {
            "ok": False,
            "resistance": None,
            "message": "CAN termination failed. Could not read resistance.",
        }

    termination = expected_can_termination_value()
    if _termination_expected_present(termination):
        ok = 84.0 <= resistance <= 156.0
        status = "CAN Termination confirmed" if ok else "CAN Termination failed"
    elif _termination_expected_absent(termination):
        ok = resistance < 10.0
        status = "No Termination confirmed" if ok else "No Termination failed"
    else:
        ok = False
        status = "CAN termination configuration unclear"

    return {
        "ok": ok,
        "resistance": resistance,
        "message": f"{status}. R={resistance:.2f} Ohm. Controller power relays are OFF.",
    }


def run_relay_action(action: str, mask: int | None = None) -> dict[str, object]:
    action_labels = {
        "power_on": "Power on controller relays",
        "power_off": "Power off controller relays",
        "restart": "Restart controller relays",
        "operation": "Activate operation relays",
        "test_all": "Test all relays",
        "end_all": "End all relays",
        "set_mask": "Set relay selection",
        "check_termination": "Check CAN termination",
    }
    label = action_labels[action]
    ok, error = STATE.begin_relay_command(label)
    if not ok:
        payload = {"ok": False, "error": error, "message": ""}
        return payload

    writer = QueueWriter(STATE)
    success = False
    message = ""
    try:
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            arduino = _get_or_connect_relay_arduino()
            if action == "power_on":
                node, bitrate = STATE.active_can_target()
                ok, message = gui_safe_execute(
                    set_controller_power_relays,
                    True,
                    node=node,
                    can_bitrate=bitrate,
                    reconnect=True,
                    fail_on_reconnect_error=False,
                    spinner_text="Powering controller relays on",
                )
                if not ok:
                    raise RuntimeError(message)
            elif action == "power_off":
                ok, message = gui_safe_execute(
                    set_controller_power_relays,
                    False,
                    reconnect=False,
                    spinner_text="Powering controller relays off",
                )
                if not ok:
                    raise RuntimeError(message)
            elif action == "restart":
                node, bitrate = STATE.active_can_target()
                ok, message = gui_safe_execute(
                    restart_controller_with_relays,
                    node=node,
                    can_bitrate=bitrate,
                    off_seconds=CONTROLLER_POWER_CYCLE_OFF_S,
                    fail_on_reconnect_error=False,
                    spinner_text="Restarting controller relays",
                )
                if not ok:
                    raise RuntimeError(message)
            elif action == "operation":
                operation_mask = operation_relay_mask()
                gui_safe_execute(
                    _confirmed_set_relays,
                    arduino,
                    operation_mask,
                    "operation relays",
                    spinner_text="Activating operation relays",
                )
                message = f"Operation relays active: mask 0x{operation_mask:03X}."
            elif action == "set_mask":
                if mask is None:
                    raise RuntimeError("Missing relay mask.")
                gui_safe_execute(
                    _confirmed_set_relays,
                    arduino,
                    mask,
                    "manual relay selection",
                    spinner_text="Setting selected relays",
                )
                message = f"Relay mask set to 0x{mask:03X}."
            elif action == "test_all":
                for relay_number in range(1, 14):
                    mask = _relay_mask(relay_number)
                    gui_safe_execute(
                        _confirmed_set_relays,
                        arduino,
                        mask,
                        f"q{relay_number}",
                        stable_reads=2,
                        spinner_text=f"Testing relay q{relay_number}",
                    )
                    time.sleep(0.15)
                gui_safe_execute(
                    _confirmed_set_relays,
                    arduino,
                    0,
                    "all relays off after test",
                    spinner_text="Switching all relays off",
                )
                message = "All relays q1..q13 tested and switched off."
            elif action == "end_all":
                gui_safe_execute(
                    _confirmed_set_relays,
                    arduino,
                    0,
                    "all relays off",
                    spinner_text="Switching all relays off",
                )
                message = "All relays q1..q13 are off."
            elif action == "check_termination":
                result = gui_safe_execute(
                    check_can_termination_with_relays,
                    spinner_text="Checking CAN termination",
                )
                message = str(result.get("message") or "")
                if not result.get("ok"):
                    raise RuntimeError(message or "CAN termination check failed.")
            success = True
            payload = relay_snapshot(arduino, ok=True)
            payload.update({"message": message, "error": ""})
            return payload
    except Exception as exc:
        STATE.append_log(format_exc())
        message = f"{label} failed. ({exc})"
        payload = {"ok": False, "message": "", "error": message}
        try:
            arduino = STATE.get_relay_arduino()
            payload.update(relay_snapshot(arduino, ok=False))
            payload["message"] = ""
            payload["error"] = message
        except Exception:
            pass
        return payload
    finally:
        STATE.finish_relay_command(label, success, message)


class CalibrationRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return
        if parsed.path == "/logo.png":
            self._send_file(LOGO_PATH, "image/png")
            return
        if parsed.path == "/status":
            self._send_json(STATE.snapshot())
            return
        if parsed.path == "/eol-report":
            with STATE.lock:
                product_dir = STATE.current_product_dir
                product_qr_code = STATE.current_barcode
            report_path = eol_done_report_for_product(product_dir, product_qr_code)
            if report_path is None:
                self.send_error(404)
                return
            self._send_file(
                report_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                download_name=report_path.name,
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/clear-log":
            STATE.clear_log()
            self._send_json({"ok": True})
            return

        if parsed.path == "/kill-all":
            kill_all_programs()
            self._send_json({"ok": True})
            return

        if parsed.path == "/confirm-power-cycle":
            ok = STATE.confirm_power_cycle()
            self._send_json({"ok": ok})
            return

        if parsed.path == "/scan-option":
            query = parse_qs(parsed.query)
            try:
                scan_option = parse_scan_option(query.get("option", [""])[0])
                STATE.set_scan_option(scan_option)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return
            self._send_json({"ok": True})
            return

        if parsed.path == "/scan-product":
            query = parse_qs(parsed.query)
            product_code = query.get("product_code", [""])[0].strip()
            if not product_code:
                self._send_json({"ok": False, "error": "Product code is required."})
                return
            threading.Thread(
                target=run_product_scan_and_can_check,
                args=(product_code,),
                daemon=True,
            ).start()
            self._send_json({"ok": True})
            return

        if parsed.path == "/disconnect-can":
            ok, message = STATE.disconnect_can()
            STATE.append_status(message, is_error=not ok)
            self._send_json({"ok": ok, "message": message, "error": "" if ok else message})
            return

        if parsed.path == "/check-can":
            query = parse_qs(parsed.query)
            explicit_target = "node" in query
            try:
                node = parse_can_node(query.get("node", [str(DEFAULT_NODE_ID)])[0])
                bitrate = parse_can_bitrate(query.get("bitrate", [str(DEFAULT_CAN_BITRATE)])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc), "quiet": False})
                return

            if not controller_power_relays_are_on():
                message = controller_power_off_message()
                STATE.mark_can_not_connected(node=node, bitrate=bitrate, message=message)
                STATE.append_status(message, mark_error=False)
                self._send_json(
                    {
                        "ok": False,
                        "message": "",
                        "error": message,
                        "quiet": True,
                        "controller_enabled": False,
                    }
                )
                return

            ok, error = STATE.begin_can_check(node, bitrate)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = LogOnlyWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    connected, node, bitrate, message, context = gui_safe_execute(
                        _check_gui_can_with_st_can0_retry,
                        explicit_target=explicit_target,
                        node=node,
                        bitrate=bitrate,
                        spinner_text=(
                            f"Checking CAN node {node}"
                            if explicit_target
                            else "Checking CAN connection"
                        ),
                    )
                public_message = message if connected else "CAN not connected."
                STATE.finish_can_check(
                    node,
                    bitrate,
                    connected,
                    public_message,
                    context=context,
                    mark_error=False,
                )
                if connected:
                    STATE.append_status(message, is_error=False)
                self._send_json(
                    {
                        "ok": connected,
                        "message": message if connected else "",
                        "error": "" if connected else message,
                        "quiet": not connected,
                        "controller_enabled": False,
                    }
                )
            except Exception as exc:
                message = f"CAN connection failed for node {node}. ({exc})"
                STATE.append_log(format_exc())
                STATE.finish_can_check(
                    node,
                    bitrate,
                    False,
                    "CAN not connected.",
                    mark_error=False,
                )
                self._send_json({"ok": False, "error": message, "quiet": True})
            return

        if parsed.path == "/controller-enable":
            query = parse_qs(parsed.query)
            try:
                enabled = parse_enabled(query.get("enabled", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node, bitrate = STATE.active_can_target()
            ok, error = STATE.begin_controller_command(node, bitrate)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = gui_safe_execute(
                        run_controller_enable,
                        node=node,
                        enabled=enabled,
                        can_bitrate=bitrate,
                        spinner_text=f"{'Enabling' if enabled else 'Disabling'} controller",
                    )
                STATE.append_status(message, is_error=not ok)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                        "controller_enabled": enabled if ok else STATE.snapshot()["controller_enabled"],
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Controller {'enable' if enabled else 'disable'} failed on node {node}. ({exc})"
                STATE.append_status(message, is_error=True)
                self._send_json({"ok": False, "error": message})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path == "/clear-controller-errors":
            node, bitrate = STATE.active_can_target()
            ok, error = STATE.begin_controller_command(node, bitrate)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = gui_safe_execute(
                        run_controller_clear_errors,
                        node=node,
                        can_bitrate=bitrate,
                        spinner_text="Clearing controller errors",
                    )
                STATE.append_status(message, is_error=not ok)
                if ok:
                    with STATE.lock:
                        STATE.has_error = False
                        STATE._update_controller_error_state_locked(0)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Clear error failed on node {node}. ({exc})"
                STATE.append_status(message, is_error=True)
                self._send_json({"ok": False, "error": message})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path == "/power-supply-output":
            query = parse_qs(parsed.query)
            try:
                enabled = parse_enabled(query.get("enabled", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node, bitrate = STATE.active_can_target()
            ok, error, can_to_close = STATE.begin_power_supply_output(node, enabled)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            if can_to_close is not None:
                try:
                    can_to_close.close_can()
                except Exception:
                    pass

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = gui_safe_execute(
                        run_power_supply_output,
                        node,
                        enabled,
                        bitrate,
                        spinner_text=(
                            "Turning power supply on"
                            if enabled
                            else "Turning power supply off"
                        ),
                    )
                STATE.finish_power_supply_output(enabled, ok, message)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                        "can_connection_ok": ok and enabled,
                        "controller_enabled": False,
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Power supply {'ON' if enabled else 'OFF'} failed. ({exc})"
                STATE.finish_power_supply_output(enabled, False, message)
                self._send_json({"ok": False, "error": message})
            return

        if parsed.path == "/relays":
            query = parse_qs(parsed.query)
            try:
                action = parse_relay_action(query.get("action", [""])[0])
                mask = (
                    parse_relay_mask(query.get("mask", [""])[0])
                    if action == "set_mask"
                    else None
                )
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc), "message": ""})
                return

            self._send_json(run_relay_action(action, mask=mask))
            return

        if parsed.path == "/manual-spin":
            query = parse_qs(parsed.query)
            try:
                rpm = parse_manual_rpm(query.get("rpm", [""])[0])
                seq = parse_manual_seq(query.get("seq", ["0"])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node, bitrate = STATE.active_can_target()
            ok, error = STATE.begin_manual_command(seq, node, bitrate, rpm)
            if not ok:
                self._send_json({"ok": not error, "error": error})
                return

            STATE.append_log("\n=== Manual Motor Spin started ===\n")
            STATE.append_status(
                "Manual motor stop requested." if rpm == 0 else f"Manual motor requested: {rpm} RPM"
            )

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    run_manual_spin(node=node, rpm=rpm, seq=seq, can_bitrate=bitrate)
                STATE.append_log("\n=== Manual Motor Spin finished ===\n")
                STATE.append_status(
                    "Manual motor stopped." if rpm == 0 else f"Manual motor command: {rpm} RPM"
                )
                self._send_json({"ok": True})
            except Exception as exc:
                STATE.append_log(format_exc())
                STATE.append_log("\n=== Manual Motor Spin failed ===\n")
                STATE.append_status(
                    "Error: Manual motor command failed. Open Debug for details.",
                    is_error=True,
                )
                self._send_json({"ok": False, "error": str(exc)})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path != "/start":
            self.send_error(404)
            return

        query = parse_qs(parsed.query)
        task_id = query.get("task", [""])[0]
        task_options = {
            "tester_name": query.get("tester_name", [""])[0],
            "product_barcode": query.get("product_barcode", [""])[0],
            "motor_barcode": query.get("motor_barcode", [""])[0],
            "ssi_encoder_restore": query.get("ssi_encoder_restore", ["1"])[0],
        }

        ok, error = STATE.start_task(task_id, task_options=task_options)
        self._send_json({"ok": ok, "error": error})

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(
        self,
        path: Path,
        content_type: str,
        download_name: str | None = None,
    ) -> None:
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if download_name:
            self.send_header("Content-Disposition", f'inline; filename="{download_name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), CalibrationRequestHandler)
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Calibration GUI running at {url}")
    print("Press Ctrl+C three times quickly in this terminal to stop it.")

    def open_browser() -> None:
        browser_commands = (
            "firefox",
            "google-chrome",
            "chromium",
            "chromium-browser",
            "xdg-open",
        )
        for command in browser_commands:
            executable = shutil.which(command)
            if executable is None:
                continue
            try:
                subprocess.Popen(
                    [executable, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                print(f"[INFO] Opened GUI in browser via {command}.")
                return
            except Exception as exc:
                print(f"[WARN] Could not open browser with {command}: {exc}")

        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[WARN] Could not open browser automatically: {exc}")

    threading.Thread(target=STATE.connect_relay_arduino, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()
    restore_sigint = install_deferred_keyboard_interrupt(
        label="Calibration GUI",
        on_interrupt=lambda signum, frame: threading.Thread(
            target=server.shutdown,
            daemon=True,
        ).start(),
    )
    try:
        server.serve_forever()
    finally:
        restore_sigint()
        STATE.close_relay_arduino()
        server.server_close()


if __name__ == "__main__":
    main()
