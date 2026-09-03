from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


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
