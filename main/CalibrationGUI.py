import contextlib
import importlib
import io
import json
import os
import re
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

from utils.interrupt_guard import install_deferred_keyboard_interrupt


BASE_DIR = PROJECT_ROOT
LOGO_PATH = BASE_DIR / "resources" / "mobotic-logo.png"
SERIAL_LAST4 = ""
DEFAULT_CAN_BITRATE = 125
STANDARD_NODE_ID = 59
DEFAULT_NODE_ID = STANDARD_NODE_ID
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


TASKS = {
    "run_all": "Run all program",
    "run_eol": "Run EOL",
    "load_script_config": "Configuration",
    "load_script": "Load Script",
    "load_config": "Load Config",
    "start_calibration": "Calibration",
    "test_calibration": "TestCalibration",
    "show_current_zero": "Show Current Zero",
    "start_zeroing": "Write Zero",
}

TASKS_REQUIRING_TESTER_NAME = {"run_all", "run_eol"}


RUN_ALL_REPORT_COLUMNS = (
    "Serial number",
    "Configuration",
    "Write Zero",
    "Calibration",
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


class RunAllReport:
    def __init__(self, product_dir: Path, qr_code: object, node: int, desired_angle: float):
        timestamp = datetime.now()
        self.qr_code = str(qr_code or "")
        self.product_dir = product_dir
        result_dir = product_dir / "04_Results"
        filename = f"{safe_filename_token(qr_code, 'barcode')}_status.xlsx"
        self.path = result_dir / filename
        rows = read_conf_xlsx_rows(self.path)
        header = list(RUN_ALL_REPORT_COLUMNS)
        if not rows or rows[0] != header:
            if rows:
                print(
                    f"[WARN] Existing result workbook has unexpected columns; "
                    f"rewriting report table: {self.path}"
                )
            rows = [header]
        self.rows = rows
        self.values = {
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


def resolve_product_context() -> ProductContext:
    from drivers.driver_QRreader import run_qr_reader
    from io_helpers.find_product_folder import find_config

    print("[INFO] Scanning product QR code.")
    qr_code = run_qr_reader(show=True, once=True, return_first=True)
    if not qr_code:
        raise RuntimeError("Barcode could not be read from QR camera.")

    old_cwd = os.getcwd()
    try:
        product_dir_raw = find_config(str(qr_code))
    finally:
        try:
            os.chdir(old_cwd)
        except Exception:
            pass
    if not product_dir_raw:
        raise RuntimeError(f"No product folder found for QR: {qr_code}")

    spec_path = find_product_spec_path(Path(product_dir_raw))
    product_dir = spec_path.parent
    params = read_product_spec_parameters(spec_path)
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
    return context


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Steering Calibration</title>
  <style>
    :root {
      --black: #000000;
      --blue: #1ba9e1;
      --white: #ffffff;
      --muted: #9a9a9a;
      --error: #ff6b6b;
      --danger: #d71920;
      --ok: #49d17d;
      --panel: rgba(0, 0, 0, 0.9);
      --shadow: 0 18px 55px rgba(0, 0, 0, 0.46);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--white);
      background: var(--black);
      font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
    }

    main {
      width: min(940px, calc(100vw - 16px));
      margin: 0 auto;
      padding: 18px 18px 20px;
      border-radius: 18px;
      border: 2px solid var(--blue);
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .topbar {
      display: grid;
      grid-template-columns: 255px minmax(0, 1fr);
      align-items: center;
      gap: 14px;
      margin-bottom: 6px;
    }

    .logo {
      width: 280px;
      height: auto;
      flex: 0 0 auto;
    }

    h1 {
      margin: 0;
      font-size: clamp(34px, 4.3vw, 42px);
      color: var(--muted);
      text-align: right;
    }

    #status {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 19px;
      font-weight: 800;
      text-align: right;
    }

    #status.ok {
      color: var(--ok);
    }

    #status.fail {
      color: var(--error);
    }

    .power-controls {
      display: grid;
      grid-template-columns: repeat(2, 72px);
      gap: 8px;
      justify-content: end;
    }

    .power-toggle {
      min-height: 42px;
      padding: 5px 8px;
      border-radius: 0;
      color: var(--blue);
      font-size: 13px;
    }

    button {
      border: 2px solid var(--blue);
      border-radius: 14px;
      color: var(--muted);
      background: var(--black);
      box-shadow: none;
      cursor: pointer;
      font-weight: 800;
      transition: transform 150ms ease, opacity 150ms ease, box-shadow 150ms ease, background 150ms ease;
    }

    button:hover {
      transform: translateY(-2px);
      background: var(--blue);
      box-shadow: 0 18px 32px rgba(27, 169, 225, 0.34);
    }

    .run-all {
      width: 100%;
      min-height: 72px;
      margin-bottom: 12px;
      font-size: 20px;
      color: var(--blue);
    }

    .kill-all {
      min-height: 36px;
      padding: 7px 14px;
      border-color: var(--danger);
      color: var(--white);
      background: #220000;
      font-size: 13px;
    }

    .continue-power {
      display: none;
      width: 100%;
      min-height: 54px;
      margin: 0 0 12px;
      border-color: var(--ok);
      color: var(--black);
      background: var(--ok);
      font-size: 18px;
    }

    .continue-power.visible {
      display: block;
    }

    .continue-power:hover {
      background: var(--ok);
      box-shadow: 0 18px 32px rgba(73, 209, 125, 0.34);
    }

    .kill-all:hover {
      background: var(--danger);
      box-shadow: 0 18px 32px rgba(215, 25, 32, 0.34);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .grid button {
      min-height: 58px;
      padding: 12px;
      color: var(--muted);
      font-size: 14px;
    }

    .settings {
      display: grid;
      grid-template-columns: max-content max-content max-content;
      align-items: center;
      justify-content: center;
      gap: 26px;
      margin: 0 0 14px;
      padding: 16px 18px;
      border: 2px solid var(--blue);
      border-radius: 14px;
    }

    .can-controls {
      display: grid;
      grid-template-columns: 116px;
      gap: 10px;
    }

    .can-controls button {
      min-height: 38px;
      padding: 6px 9px;
      border-radius: 12px;
      color: var(--muted);
      font-size: 12px;
    }

    label {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 17px;
      font-weight: 800;
    }

    input {
      width: 108px;
      min-height: 42px;
      padding: 9px 12px;
      border: 2px solid var(--blue);
      border-radius: 12px;
      color: var(--muted);
      background: var(--black);
      font: 16px "DejaVu Sans", "Liberation Sans", sans-serif;
      outline: none;
    }

    input:focus {
      box-shadow: 0 0 0 3px rgba(27, 169, 225, 0.28);
    }

    .manual-spin {
      display: grid;
      grid-template-columns: 42px 72px 42px;
      align-items: center;
      gap: 8px;
    }

    .manual-spin button {
      min-height: 38px;
      padding: 5px;
      color: var(--muted);
      font-size: 16px;
    }

    .spin-arrow {
      width: 42px;
      min-width: 42px;
      font-size: 22px;
      line-height: 1;
      touch-action: none;
      user-select: none;
    }

    .rpm-control {
      display: grid;
      grid-template-rows: 30px 24px 30px;
      gap: 4px;
      align-items: stretch;
    }

    .rpm-control button {
      min-height: 30px;
      padding: 3px;
      font-size: 18px;
      line-height: 1;
    }

    #manual-rpm {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      border: 2px solid var(--blue);
      border-radius: 10px;
      color: var(--muted);
      background: var(--black);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }

    .view-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }

    .view-head strong {
      font-size: 17px;
      color: var(--muted);
    }

    .view-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 8px;
    }

    .view-actions button {
      padding: 8px 14px;
      border-radius: 12px;
      background: var(--black);
      box-shadow: none;
      font-size: 13px;
    }

    .view-actions button.active {
      color: var(--black);
      background: var(--blue);
    }

    .view-actions .kill-all {
      border-color: var(--danger);
      background: #220000;
    }

    .view-actions .kill-all:hover {
      background: var(--danger);
      box-shadow: 0 18px 32px rgba(215, 25, 32, 0.34);
    }

    .view {
      display: none;
    }

    .view.active {
      display: block;
    }

    #status-feed {
      height: min(42vh, 392px);
      min-height: 340px;
      margin: 0;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      border-radius: 14px;
      border: 2px solid var(--blue);
      color: var(--muted);
      background: var(--black);
      font: 15px/1.55 "DejaVu Sans Mono", "Liberation Mono", monospace;
    }

    #status-feed.fail {
      color: var(--error);
    }

    #log {
      height: min(44vh, 430px);
      min-height: 220px;
      margin: 0;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      border-radius: 14px;
      border: 2px solid var(--blue);
      color: var(--muted);
      background: var(--black);
      font: 14px/1.45 "DejaVu Sans Mono", "Liberation Mono", monospace;
    }

    .error-status {
      margin: 14px 0 0 22px;
      color: var(--muted);
      font-size: 20px;
      font-weight: 800;
    }

    .error-status.fail {
      color: var(--error);
    }

    @media (max-width: 760px) {
      main {
        margin: 16px auto;
        padding: 18px;
        border-radius: 18px;
      }

      .grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .settings {
        grid-template-columns: 1fr;
        justify-content: center;
        justify-items: center;
        padding: 12px;
      }

      .power-controls {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .manual-spin {
        justify-content: start;
      }

      input {
        width: 100%;
      }

      .topbar {
        grid-template-columns: 1fr;
        align-items: start;
        gap: 16px;
      }

      h1 {
        text-align: right;
      }

      #status {
        text-align: right;
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <img class="logo" src="/logo.png" alt="MOBOTIC logo">
      <div>
        <h1>Steering Software Control</h1>
        <div id="status">Switch On Power Supply</div>
      </div>
    </div>

    <div class="settings">
      <div class="can-controls" aria-label="CAN controller controls">
        <button id="drive-enable" type="button">Enable</button>
        <button id="clear-errors" type="button">Clear error</button>
      </div>
      <div class="manual-spin" aria-label="Manual motor spin">
        <button id="spin-left" class="spin-arrow" type="button" title="Hold to spin left">←</button>
        <div class="rpm-control">
          <button id="rpm-plus" type="button" title="Increase RPM">+</button>
          <div id="manual-rpm">1000 RPM</div>
          <button id="rpm-minus" type="button" title="Decrease RPM">-</button>
        </div>
        <button id="spin-right" class="spin-arrow" type="button" title="Hold to spin right">→</button>
      </div>
      <div class="power-controls" aria-label="Power supply controls">
        <button id="ps-on" class="power-toggle" type="button">PS:<br>ON</button>
        <button id="ps-off" class="power-toggle" type="button">PS:<br>OFF</button>
      </div>
    </div>

    <button class="run-all" data-task="run_all">Run all program</button>
    <button id="continue-power-cycle" class="continue-power" type="button">
      Continue after power cycle
    </button>

    <div class="grid">
      <button data-task="load_script_config">Configuration</button>
      <button data-task="start_zeroing">Write Zero</button>
      <button data-task="start_calibration">Calibration</button>
      <button data-task="test_calibration">TestCalibration</button>
      <button data-task="show_current_zero">Show Current Zero</button>
      <button data-task="run_eol">Run EOL</button>
    </div>

    <div class="view-head">
      <strong id="view-title">Status</strong>
      <div class="view-actions">
        <button id="status-tab" class="active" type="button">Status</button>
        <button id="debug-tab" type="button">Debug</button>
        <button id="clear-log" type="button">Clear view</button>
        <button id="kill-all" class="kill-all" type="button">Kill All</button>
      </div>
    </div>

    <section id="status-view" class="view active">
      <pre id="status-feed">Ready.</pre>
    </section>

    <section id="debug-view" class="view">
      <pre id="log"></pre>
    </section>
    <div id="error-status" class="error-status">Error Status: --</div>
  </main>

  <script>
    const statusEl = document.querySelector("#status");
    const statusFeedEl = document.querySelector("#status-feed");
    const logEl = document.querySelector("#log");
    const driveEnableEl = document.querySelector("#drive-enable");
    const clearErrorsEl = document.querySelector("#clear-errors");
    const psOnEl = document.querySelector("#ps-on");
    const psOffEl = document.querySelector("#ps-off");
    const killAllEl = document.querySelector("#kill-all");
    const continuePowerCycleEl = document.querySelector("#continue-power-cycle");
    const spinLeftEl = document.querySelector("#spin-left");
    const spinRightEl = document.querySelector("#spin-right");
    const rpmPlusEl = document.querySelector("#rpm-plus");
    const rpmMinusEl = document.querySelector("#rpm-minus");
    const manualRpmEl = document.querySelector("#manual-rpm");
    const statusViewEl = document.querySelector("#status-view");
    const debugViewEl = document.querySelector("#debug-view");
    const statusTabEl = document.querySelector("#status-tab");
    const debugTabEl = document.querySelector("#debug-tab");
    const viewTitleEl = document.querySelector("#view-title");
    const errorStatusEl = document.querySelector("#error-status");
    const buttons = [...document.querySelectorAll("[data-task]")];
    const manualButtons = [spinLeftEl, spinRightEl, rpmPlusEl, rpmMinusEl];
    const MANUAL_RPM_DEFAULT = 1000;
    const MANUAL_RPM_STEP = 200;
    const MANUAL_RPM_MIN = 200;
    const MANUAL_RPM_MAX = 5000;
    const TASKS_REQUIRING_TESTER_NAME = new Set(["run_all", "run_eol"]);
    let lastLength = 0;
    let lastStatusText = "";
    let manualRpm = MANUAL_RPM_DEFAULT;
    let heldSpinDirection = 0;
    let manualCommandSeq = 0;
    let canConnected = false;
    let canCheckRunning = true;
    let controllerEnabled = false;

    function setBusy(isBusy) {
      updateCanControls(isBusy);
    }

    function updateCanControls(isBusy = false) {
      driveEnableEl.textContent = controllerEnabled ? "Disable" : "Enable";
    }

    function setMainStatus(text, state) {
      statusEl.textContent = text;
      statusEl.classList.toggle("ok", state === "ok");
      statusEl.classList.toggle("fail", state === "fail");
    }

    function setCanStatus(text, state) {
      setMainStatus(text, state);
    }

    function updateManualRpm(delta) {
      manualRpm = Math.max(MANUAL_RPM_MIN, Math.min(MANUAL_RPM_MAX, manualRpm + delta));
      manualRpmEl.textContent = `${manualRpm} RPM`;
    }

    function setView(viewName) {
      const debug = viewName === "debug";
      statusViewEl.classList.toggle("active", !debug);
      debugViewEl.classList.toggle("active", debug);
      statusTabEl.classList.toggle("active", !debug);
      debugTabEl.classList.toggle("active", debug);
      viewTitleEl.textContent = debug ? "Debug" : "Status";
    }

    async function startTask(task) {
      if (!canConnected) {
        statusFeedEl.textContent = "Switch On Power Supply";
        statusFeedEl.classList.remove("fail");
        setCanStatus("Switch On Power Supply", "");
        setMainStatus("Switch On Power Supply", "");
        setView("status");
        return;
      }
      const params = new URLSearchParams({ task });
      if (TASKS_REQUIRING_TESTER_NAME.has(task)) {
        const previousTesterName = localStorage.getItem("eolTesterName") || "";
        const testerName = window.prompt("Tester name for EOL", previousTesterName);
        if (testerName === null) {
          return;
        }
        const trimmedTesterName = testerName.trim();
        if (!trimmedTesterName) {
          statusFeedEl.textContent = "Tester name is required for EOL.";
          statusFeedEl.classList.add("fail");
          setView("status");
          return;
        }
        localStorage.setItem("eolTesterName", trimmedTesterName);
        params.set("tester_name", trimmedTesterName);
      }
      try {
        const response = await fetch(`/start?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not start task.";
          statusFeedEl.classList.add("fail");
          setView("status");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      await refreshStatus();
    }

    function manualSpin(rpm, seq = ++manualCommandSeq) {
      if (!canConnected && rpm !== 0) {
        statusFeedEl.textContent = "CAN node is not connected. Wait for the CAN check or run a product task first.";
        statusFeedEl.classList.add("fail");
        setView("status");
        return Promise.resolve();
      }
      const params = new URLSearchParams({ rpm: String(rpm), seq: String(seq) });
      return fetch(`/manual-spin?${params.toString()}`, { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          if (!data.ok) {
            statusFeedEl.textContent = data.error || "Could not command motor.";
            statusFeedEl.classList.add("fail");
            setView("status");
          }
          return refreshStatus();
        })
        .catch((error) => {
          statusFeedEl.textContent = `Server connection problem: ${error}`;
          statusFeedEl.classList.add("fail");
          setView("status");
        });
    }

    function startHeldSpin(direction, event) {
      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      if (heldSpinDirection !== 0) {
        return;
      }
      heldSpinDirection = direction;
      manualSpin(direction * manualRpm);
    }

    function stopHeldSpin() {
      if (heldSpinDirection === 0) {
        return;
      }
      heldSpinDirection = 0;
      manualSpin(0);
    }

    function sendReleaseBeacon() {
      if (heldSpinDirection === 0) {
        return;
      }
      heldSpinDirection = 0;
      const params = new URLSearchParams({ rpm: "0", seq: String(++manualCommandSeq) });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(`/manual-spin?${params.toString()}`);
      } else {
        fetch(`/manual-spin?${params.toString()}`, { method: "POST", keepalive: true });
      }
    }

    async function refreshStatus() {
      try {
        const response = await fetch("/status");
        const data = await response.json();
        statusFeedEl.classList.toggle("fail", data.has_error === true);
        canConnected = data.can_connection_ok === true;
        canCheckRunning = data.can_check_running === true;
        controllerEnabled = data.controller_enabled === true;
        let connectionText = "";
        let connectionState = "";
        if (canCheckRunning) {
          connectionText = "Checking CAN connection...";
          connectionState = "";
        } else if (data.can_connection_ok === true) {
          connectionText = data.can_connection_message || "CAN connected.";
          connectionState = "ok";
        } else {
          const disconnected = (
            (data.can_connection_message || "").startsWith("CAN disconnected")
            || (data.can_connection_message || "") === "CAN not connected."
          );
          connectionText = data.can_connection_message || "CAN connection failed.";
          connectionState = disconnected ? "" : "fail";
        }
        if (data.running === true || data.awaiting_power_cycle === true) {
          setMainStatus(data.status || "Running.", "");
        } else if (data.has_error === true && data.status && !["Choose one operation", "Ready."].includes(data.status)) {
          setMainStatus(data.status, "fail");
        } else if (canCheckRunning || data.can_connection_ok === true) {
          setMainStatus(connectionText, connectionState);
        } else {
          const idleStatus = data.status || "Choose one operation";
          setMainStatus(
            ["Ready.", "Choose one operation"].includes(idleStatus)
              ? "Switch On Power Supply"
              : idleStatus,
            ""
          );
        }
        const errorCode = data.controller_error_code;
        errorStatusEl.textContent = errorCode === null || errorCode === undefined
          ? "Error Status: --"
          : `Error Status: ${errorCode}`;
        errorStatusEl.classList.toggle("fail", errorCode !== null && errorCode !== undefined && Number(errorCode) !== 0);
        setBusy(data.running);
        continuePowerCycleEl.classList.toggle("visible", data.awaiting_power_cycle === true);

        if (data.status_feed !== lastStatusText) {
          statusFeedEl.textContent = data.status_feed || "Ready.";
          statusFeedEl.scrollTop = statusFeedEl.scrollHeight;
          lastStatusText = data.status_feed;
        }

        if (data.log.length !== lastLength) {
          logEl.textContent = data.log;
          logEl.scrollTop = logEl.scrollHeight;
          lastLength = data.log.length;
        }
      } catch (error) {
        statusFeedEl.textContent = "Server connection problem. Open Debug after the server is reachable again.";
        statusFeedEl.classList.add("fail");
      }
    }

    async function checkCanConnection() {
      canConnected = false;
      canCheckRunning = true;
      setCanStatus("Checking CAN connection...", "");
      setBusy(true);
      try {
        const response = await fetch("/check-can", { method: "POST" });
        const data = await response.json();
        canConnected = data.ok === true;
        canCheckRunning = false;
        controllerEnabled = data.controller_enabled === true;
        if (data.ok) {
          setCanStatus(data.message || "CAN connected.", "ok");
          statusFeedEl.classList.remove("fail");
        } else if (data.quiet === true) {
          setCanStatus("CAN not connected.", "");
          statusFeedEl.classList.remove("fail");
        } else {
          setCanStatus(data.error || "CAN connection failed.", "fail");
          statusFeedEl.textContent = data.error || "CAN connection failed.";
          statusFeedEl.classList.add("fail");
          setView("status");
        }
      } catch (error) {
        canConnected = false;
        canCheckRunning = false;
        setCanStatus(`CAN check failed: ${error}`, "fail");
        statusFeedEl.textContent = `CAN check failed: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function toggleControllerEnabled() {
      if (!canConnected) {
        return;
      }
      const nextEnabled = !controllerEnabled;
      const params = new URLSearchParams({ enabled: nextEnabled ? "1" : "0" });
      setBusy(true);
      try {
        const response = await fetch(`/controller-enable?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not change controller enable state.";
          statusFeedEl.classList.add("fail");
          setView("status");
        } else {
          controllerEnabled = data.controller_enabled === true;
          statusFeedEl.textContent = data.message || "Controller state changed.";
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function clearControllerErrors() {
      if (!canConnected) {
        return;
      }
      const params = new URLSearchParams();
      setBusy(true);
      try {
        const response = await fetch(`/clear-controller-errors?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not clear controller errors.";
          statusFeedEl.classList.add("fail");
          setView("status");
        } else {
          statusFeedEl.textContent = data.message || "Controller errors cleared.";
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function setPowerSupplyOutput(enabled) {
      setBusy(true);
      statusFeedEl.textContent = enabled ? "Turning power supply on..." : "Turning power supply off...";
      statusFeedEl.classList.remove("fail");
      setView("status");
      const params = new URLSearchParams({ enabled: enabled ? "1" : "0" });
      try {
        const response = await fetch(`/power-supply-output?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not control power supply.";
          statusFeedEl.classList.add("fail");
        } else {
          canConnected = data.can_connection_ok === true;
          controllerEnabled = data.controller_enabled === true;
          statusFeedEl.textContent = data.message || (enabled ? "Power supply on." : "Power supply off.");
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      setBusy(false);
      await refreshStatus();
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => startTask(button.dataset.task));
    });

    driveEnableEl.addEventListener("click", toggleControllerEnabled);
    clearErrorsEl.addEventListener("click", clearControllerErrors);
    psOnEl.addEventListener("click", () => setPowerSupplyOutput(true));
    psOffEl.addEventListener("click", () => setPowerSupplyOutput(false));

    rpmPlusEl.addEventListener("click", () => updateManualRpm(MANUAL_RPM_STEP));
    rpmMinusEl.addEventListener("click", () => updateManualRpm(-MANUAL_RPM_STEP));
    spinLeftEl.addEventListener("pointerdown", (event) => startHeldSpin(-1, event));
    spinRightEl.addEventListener("pointerdown", (event) => startHeldSpin(1, event));
    [spinLeftEl, spinRightEl].forEach((button) => {
      button.addEventListener("pointerup", stopHeldSpin);
      button.addEventListener("pointercancel", stopHeldSpin);
      button.addEventListener("pointerleave", stopHeldSpin);
      button.addEventListener("lostpointercapture", stopHeldSpin);
    });
    window.addEventListener("blur", stopHeldSpin);
    window.addEventListener("pagehide", sendReleaseBeacon);

    continuePowerCycleEl.addEventListener("click", async () => {
      try {
        await fetch("/confirm-power-cycle", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Could not confirm power cycle: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      await refreshStatus();
    });

    killAllEl.addEventListener("click", async () => {
      statusFeedEl.textContent = "Stopping all programs...";
      statusFeedEl.classList.add("fail");
      try {
        await fetch("/kill-all", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Programs stopped. Server connection closed: ${error}`;
      }
    });

    statusTabEl.addEventListener("click", () => setView("status"));
    debugTabEl.addEventListener("click", () => setView("debug"));

    document.querySelector("#clear-log").addEventListener("click", async () => {
      try {
        await fetch("/clear-log", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Could not clear debug log: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      logEl.textContent = "";
      statusFeedEl.textContent = "Ready.";
      lastLength = 0;
      lastStatusText = "";
      await refreshStatus();
    });

    setInterval(refreshStatus, 750);
  </script>
</body>
</html>
"""


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.log = ""
        self.status = "Switch On Power Supply"
        self.quality = "Calibration quality: no result yet."
        self.quality_ok: bool | None = None
        self._quality_fields: dict[str, str] = {}
        self.status_lines: list[str] = ["Switch On Power Supply"]
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
        self.controller_enabled = False
        self.controller_error_code: int | None = None
        self.controller_error_active = False
        self.current_barcode = ""
        self.current_product_dir: Path | None = None
        self.current_product_context: ProductContext | None = None
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
            timestamp = time.strftime("%H:%M:%S")
            if self.status_lines and self.status_lines[-1].endswith(f"  {clean}"):
                return
            self.status_lines.append(f"{timestamp}  {clean}")
            self.status_lines = self.status_lines[-12:]
            if is_error and mark_error:
                self.has_error = True

    def clear_log(self) -> None:
        with self.lock:
            self.log = ""
            self.status_lines = ["Ready."]
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
            if level == "WARN":
                return f"Note: {message}", False
            if level == "ERROR":
                return f"Issue: {message}", True
            return message, False

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
        with self.lock:
            return {
                "log": self.log,
                "status": self.status,
                "quality": self.quality,
                "quality_ok": self.quality_ok,
                "status_feed": "\n".join(self.status_lines),
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
            timestamp = time.strftime("%H:%M:%S")
            self.status_lines.append(
                f"{timestamp}  Waiting for supply power cycle. Press Continue after power is back on."
            )
            self.status_lines = self.status_lines[-12:]
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

        can_to_close = None
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            self.running = True
            self.status = f"Running: {TASKS[task_id]}"
            self.log += f"\n=== {TASKS[task_id]} started ===\n"
            self.status_lines.append(f"{time.strftime('%H:%M:%S')}  Started: {TASKS[task_id]}")
            self.status_lines = self.status_lines[-12:]
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
            if not ok:
                self.controller_enabled = False
            if not ok and mark_error:
                self.has_error = True
            if ok:
                self.has_error = False

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
            self.log += f"\n=== Power Supply {label} started ===\n"
            self.status_lines.append(f"{time.strftime('%H:%M:%S')}  Turning power supply {label}.")
            self.status_lines = self.status_lines[-12:]
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
        self.append_log(
            f"\n=== Power Supply {label} finished ===\n"
            if ok
            else f"\n=== Power Supply {label} failed ===\n"
        )
        self.append_status(message, is_error=not ok)

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
                self.append_status(f"Finished: {label}")
            else:
                self.append_log(
                    f"\n=== {label} finished with result {result!r} in {elapsed:.1f}s ===\n"
                )
                self.append_status(f"Error: {label} finished with result {result!r}", is_error=True)
                if task_id in {"start_calibration", "test_calibration", "run_all"}:
                    self.mark_quality_failed_if_pending("calibration stopped before final quality report")
            with self.lock:
                self.status = "Ready." if success else "Finished with errors."
                if success:
                    self.has_error = False
        except Exception:
            self.append_log(format_exc())
            self.append_log(f"\n=== {label} failed ===\n")
            self.append_status(f"Error: {label} failed. Open Debug for details.", is_error=True)
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
) -> None:
    if report is None:
        return
    identity = read_controller_identity(node, can_bitrate=can_bitrate)
    if identity:
        report.update(**identity)


def run_task(task_id: str, task_options: dict[str, object] | None = None):
    task_options = task_options or {}
    if task_id == "run_all":
        return run_all(tester_name=str(task_options.get("tester_name", "")).strip())

    if task_id == "run_eol":
        return run_steering_eol(
            tester_name=str(task_options.get("tester_name", "")).strip(),
        )

    context = resolve_product_context()
    STATE.set_product_context(context)
    node = context.steering_node_id
    reportable_tasks = {"load_script_config", "start_calibration", "start_zeroing"}
    report = (
        prepare_report_for_context(context)
        if task_id in reportable_tasks
        else STATE.get_current_report()
    )
    if task_id in reportable_tasks:
        refresh_report_controller_serial(report, node, context.can_bitrate)

    if task_id == "load_script":
        from logic import FlashSteeringScript

        return FlashSteeringScript.main(
            desired_node_id=STANDARD_NODE_ID,
            qr_info=context.script_info(),
        )

    if task_id == "load_script_config":
        try:
            refresh_report_controller_serial(report, node, context.can_bitrate)
            config_details = run_load_script_config_details(context)
            if report is not None:
                report.update(
                    **read_controller_identity(node, can_bitrate=context.can_bitrate),
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
        return run_load_config(node=node, can_bitrate=context.can_bitrate)

    if task_id == "start_calibration":
        from logic import FullCalibration

        print(
            "[INFO] Starting calibration without post-calibration zero write. "
            "Use Write Zero before Calibration when the physical zero must be saved."
        )
        refresh_report_controller_serial(report, node, context.can_bitrate)
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
            calibration_ok = FullCalibration.main(
                serial_last4=SERIAL_LAST4,
                can_bitrate=context.can_bitrate,
                node=node,
                result_callback=calibration_callback,
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
        import TestCalibration

        result = TestCalibration.main(
            serial_last4=SERIAL_LAST4,
            can_bitrate=context.can_bitrate,
            node=node,
        )
        if not is_success(result):
            return result

        wait_for_power_cycle_after_test_calibration(STATE.request_power_cycle_confirmation)
        return result

    if task_id == "show_current_zero":
        return run_show_current_zero(
            node=node,
            desired_angle=context.zero_angle,
            can_bitrate=context.can_bitrate,
        )

    if task_id == "start_zeroing":
        refresh_report_controller_serial(report, node, context.can_bitrate)
        zero_result: dict[str, object] = {}

        def zero_callback(data: dict[str, object]) -> None:
            zero_result.update(data)
            if report is not None:
                report.update(**format_zero_status(zero_result))

        try:
            result = run_zeroing(
                node=node,
                desired_angle=context.zero_angle,
                can_bitrate=context.can_bitrate,
                result_callback=zero_callback,
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
        context = resolve_product_context()
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
    connected, message = check_can_connection(
        DEFAULT_NODE_ID,
        can_bitrate=DEFAULT_CAN_BITRATE,
        create_report=False,
    )
    if connected:
        return True, DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE, message, None

    standard_failure = message
    print(f"[WARN] {standard_failure}")
    print("[INFO] Standard node failed; scanning QR and reading product specification.")
    try:
        context = resolve_product_context()
    except Exception as exc:
        setup_message = _can_interface_setup_failure_message(
            standard_failure,
            None,
            None,
        )
        if setup_message is not None:
            print(f"[WARN] {setup_message}")
            return False, DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE, setup_message, None
        unknown_message = (
            "CAN node ID is unknown. Standard node 59 failed, and QR/product "
            f"specification could not be read. ({exc})"
        )
        print(f"[WARN] {unknown_message}")
        return False, DEFAULT_NODE_ID, DEFAULT_CAN_BITRATE, unknown_message, None

    connected, product_message = check_can_connection(
        context.steering_node_id,
        can_bitrate=context.can_bitrate,
        create_report=False,
        context=context,
    )
    if connected:
        return True, context.steering_node_id, context.can_bitrate, product_message, context

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
        "CAN node ID is unknown. Standard node 59 failed, and product specification "
        f"Steering Node ID {context.steering_node_id} also failed."
    )
    print(f"[WARN] {product_message}")
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
    import drivers.driver_owon as driver_owon

    driver_owon = importlib.reload(driver_owon)

    print(f"[STATUS] Turning OWON power supply output {'ON' if enabled else 'OFF'}.")
    driver_owon.set_owon_spe6053_output(
        enabled=enabled,
        voltage_v=24.0,
        current_a=5.0,
        required=True,
    )
    if not enabled:
        return True, "Power supply output is OFF. CAN is disconnected until PS: ON."

    connected, _node, _bitrate, message, _context = check_standard_then_product_can_connection()
    if not connected:
        return False, f"Power supply output is ON, but {message}"
    return True, f"Power supply output is ON. {message}"


def automatic_power_cycle_for_zero(_timeout_s: float) -> bool:
    can_to_close = None
    with STATE.lock:
        can_to_close = STATE._detach_manual_controller_locked(
            message="Power-cycling supply for Write Zero verification..."
        )
    if can_to_close is not None:
        try:
            can_to_close.close_can()
        except Exception:
            pass

    import drivers.driver_owon as driver_owon

    driver_owon = importlib.reload(driver_owon)
    print("[STATUS] Automatically power-cycling OWON supply for Write Zero verification.")
    STATE.append_status("Automatically power-cycling OWON supply for Write Zero verification.")
    try:
        ok = bool(
            driver_owon.power_cycle_owon_spe6053(
                off_seconds=3.0,
                voltage_v=24.0,
                current_a=5.0,
            )
        )
    except Exception as exc:
        with STATE.lock:
            STATE.status = "Write Zero power cycle failed."
        STATE.append_status(
            f"OWON power cycle failed during Write Zero: {exc}",
            is_error=True,
        )
        raise
    if ok:
        STATE.append_status("OWON power cycle completed. Continuing zero verification.")
    else:
        with STATE.lock:
            STATE.status = "Write Zero power cycle failed."
        STATE.append_status("OWON power cycle failed during Write Zero.", is_error=True)
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


def run_all(tester_name: str | None = None) -> bool:
    context = resolve_product_context()
    STATE.set_product_context(context)
    node = context.steering_node_id
    target_angle = context.zero_angle
    report: RunAllReport | None = None
    final_zero_required = False
    post_calibration_zero_done = False

    try:
        report = prepare_report_for_context(context)

        config_details = run_load_script_config_details(context)
        identity = read_controller_identity(node, can_bitrate=context.can_bitrate)
        report.update(
            **identity,
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
            run_zeroing(
                node=node,
                desired_angle=target_angle,
                can_bitrate=context.can_bitrate,
                result_callback=zero_callback,
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

        calibration_ok = FullCalibration.main(
            serial_last4=SERIAL_LAST4,
            can_bitrate=context.can_bitrate,
            node=node,
            result_callback=calibration_callback,
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
            return_motor_to_zero_for_run_all(
                node,
                can_bitrate=context.can_bitrate,
                context=f"run all post-calibration zero pass {pass_idx}",
            )
        post_calibration_zero_done = True
        final_zero_required = False

        print("[INFO] Run All: starting steering EOL program.")
        eol_ok = run_steering_eol(tester_name=tester_name)
        print("[INFO] Run All completed after configuration, zero write, calibration, current zero, and EOL.")
        return is_success(eol_ok)
    finally:
        if report is not None and final_zero_required and not post_calibration_zero_done:
            try:
                final_zero_status = return_motor_to_zero_for_run_all(
                    node,
                    can_bitrate=context.can_bitrate,
                    context="run all final zero cleanup",
                )
            except Exception as exc:
                final_zero_status = "FAIL"
                print(f"[WARN] Run All final motor zero failed: {exc}")


def run_steering_eol(tester_name: str | None = None):
    tester_name = str(tester_name or "").strip()
    if not tester_name:
        raise RuntimeError("Tester name is required for EOL.")
    print("[INFO] Starting steering_EOL program.")
    steering_EOL = importlib.import_module("main.steering_EOL")
    steering_EOL = importlib.reload(steering_EOL)
    previous_noninteractive = os.environ.get("ST_NONINTERACTIVE")
    os.environ["ST_NONINTERACTIVE"] = "1"
    try:
        return steering_EOL.main(tester_name=tester_name)
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


def parse_enabled(raw_value: str) -> bool:
    if raw_value in {"1", "true", "True", "on"}:
        return True
    if raw_value in {"0", "false", "False", "off"}:
        return False
    raise ValueError("Enabled value must be 1 or 0.")


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

        if parsed.path == "/disconnect-can":
            ok, message = STATE.disconnect_can()
            STATE.append_status(message, is_error=not ok)
            self._send_json({"ok": ok, "message": message, "error": "" if ok else message})
            return

        if parsed.path == "/check-can":
            node = DEFAULT_NODE_ID
            bitrate = DEFAULT_CAN_BITRATE
            ok, error = STATE.begin_can_check(node, bitrate)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = LogOnlyWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    connected, node, bitrate, message, context = (
                        check_standard_then_product_can_connection()
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
                    ok, message = run_controller_enable(
                        node=node,
                        enabled=enabled,
                        can_bitrate=bitrate,
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
                    ok, message = run_controller_clear_errors(
                        node=node,
                        can_bitrate=bitrate,
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
                    ok, message = run_power_supply_output(node, enabled, bitrate)
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

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
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
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[WARN] Could not open browser automatically: {exc}")

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
        server.server_close()


if __name__ == "__main__":
    main()
