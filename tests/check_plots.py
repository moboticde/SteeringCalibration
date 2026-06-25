import os
import sys
import re
import glob
import shutil
from typing import Optional

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from processing.data_processing import DataProcessing
from processing.plot_generator import PlotGenerator
from io_helpers.requirements_doc import ConfigReader, is_valid_xlsx  # <- use validator from ConfigReader
# is_valid_xlsx ensures the path is a real .xlsx (zip structure), not just a .xlsx suffix. :contentReference[oaicite:1]{index=1}


class DirectConfig(ConfigReader):
    def __init__(self, excel_path):
        self.results_excel_path = excel_path if excel_path.endswith(".xlsx") else excel_path + ".xlsx"
        self.BASE_PATH = os.path.dirname(os.path.dirname(self.results_excel_path))
        self.SAVE_RESULTS_PATH = os.path.dirname(self.results_excel_path)
        self.parameters = {}
        self.recepies = {}


def clean_unit_serial_number(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"\s*\(copy(?:\s+\d+)?\)$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_test$", "", stem, flags=re.IGNORECASE)
    return stem


def copy_index_from_path(p: str) -> int:
    stem = os.path.splitext(os.path.basename(p))[0]
    m = re.search(r"\(copy(?:\s+(\d+))?\)$", stem, flags=re.IGNORECASE)
    if not m:
        return 0
    return int(m.group(1)) if m.group(1) else 1


def find_latest_for_unit(results_dir: str, unit: int) -> Optional[str]:
    """
    Pick the newest among:
      *-<unit>_test.xlsx
      *-<unit>_test (copy).xlsx
      *-<unit>_test (copy N).xlsx
    """
    pattern = os.path.join(results_dir, f"*-{unit}_test*.xlsx")
    candidates = glob.glob(pattern)

    if not candidates:
        # defensive fallback
        alt = glob.glob(os.path.join(results_dir, "*_test*.xlsx"))
        candidates = [p for p in alt if f"-{unit}_test" in os.path.basename(p)]

    if not candidates:
        return None

    candidates.sort(key=lambda p: (copy_index_from_path(p), os.path.getmtime(p)), reverse=True)
    return candidates[0]


def uniquify(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{base} ({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def assert_exact_xlsx(path: str) -> str:
    """Verify that 'path' points to an existing and valid .xlsx."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Excel file not found: {path}")
    if not path.lower().endswith(".xlsx"):
        raise ValueError(f"Not an .xlsx file: {path}")
    if not is_valid_xlsx(path):
        raise ValueError(f"File is not a valid Excel workbook: {path}")
    return path


def get_desktop_dir() -> str:
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "OneDrive - Mobotic GmbH", "Desktop"),
        os.path.join(home, "Desktop"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[-1]


def assert_dir(path: str) -> str:
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Results directory not found: {path}")
    return path


def build_results_dir(base_root: str, unit_name: str) -> str:
    return os.path.join(base_root, unit_name, unit_name, "04_EOL_Results")


def parse_unit_range(text: str) -> tuple[int, int]:
    raw = text.strip()
    if not raw:
        raise ValueError("Unit range is empty.")
    if "-" in raw:
        left, right = raw.split("-", 1)
        return int(left.strip()), int(right.strip())
    value = int(raw)
    return value, value


def plot_from_file(excel_path: str, html_out_dir: Optional[str] = None) -> str:
    # Strict check of the exact file
    excel_path = assert_exact_xlsx(excel_path)

    dp = DataProcessing()
    pg = PlotGenerator()

    config = DirectConfig(excel_path)
    unit_serial_number = clean_unit_serial_number(config.results_excel_path)
    print(f"[INFO] Generating report for: {unit_serial_number}")

    # --- motor feedback plots ---
    sections = config.extract_motor_combined_feedback(dp, pg)

    # --- brake test plots ---
    try:
        brake_torque = config.get_product_parameter("Nominal Brake Torque", default=11)
        brake_sections = config.extract_brake_feedback(dp, pg, brake_torque=brake_torque)
        if isinstance(brake_sections, list):
            sections.extend(brake_sections)
        else:
            sections.append(brake_sections)
        print("[INFO] Brake test section(s) added.")
    except Exception as e:
        print(f"[WARNING] Could not extract brake plots: {e}")

    # --- metadata & HTML report ---
    metadata = config.get_metadata(dp=dp)
    # FIX: render_tabs_html only takes (sections, metadata) and names HTML after the Excel file. :contentReference[oaicite:2]{index=2}
    html_path = config.render_tabs_html(sections, metadata)

    # Move HTML into new folder if requested
    if html_out_dir:
        os.makedirs(html_out_dir, exist_ok=True)
        dest = uniquify(os.path.join(html_out_dir, os.path.basename(html_path)))
        try:
            shutil.move(html_path, dest)
            print(f"[SUCCESS] Report moved to: {dest}")
            return dest
        except Exception as e:
            print(f"[WARNING] Could not move HTML -> leaving at {html_path}: {e}")
            return html_path
    else:
        print(f"[SUCCESS] Report generated: {html_path}")
        return html_path

def plot_from_range(results_dir: str, start_unit: int, end_unit: int, html_out_dir: Optional[str] = None) -> None:
    results_dir = assert_dir(results_dir)
    if start_unit > end_unit:
        start_unit, end_unit = end_unit, start_unit

    generated = 0
    missing = []
    for unit in range(start_unit, end_unit + 1):
        latest = find_latest_for_unit(results_dir, unit)
        if not latest:
            missing.append(unit)
            continue
        try:
            plot_from_file(latest, html_out_dir=html_out_dir)
            generated += 1
        except Exception as e:
            print(f"[ERROR] Failed for unit {unit}: {e}")

    print(f"[INFO] Range done. Generated: {generated}, Missing: {len(missing)}")
    if missing:
        print(f"[INFO] Missing units: {missing}")


if __name__ == "__main__":
    # --- CONFIG ---
    # Option A: exact Excel file (set to None to use range)
    excel_path = "/S-1000-200/S-1000-200-01/04_Results/S-1000-200_done.xlsx"

    if excel_path:
        # Put HTML next to the Excel, under '05_HTML_Reports'
        html_out_dir = os.path.join(os.path.dirname(excel_path), "05_HTML_Reports")
    else:
        # Base folder and unit name to assemble the results path
        base_results_root = r"/home/user/Mobotic GmbH/Mobotic - Manufacturing/01_Products"
        unit_name = "DD-RR-500-225-54SB-48-C-6"
        unit_range = "314-329"
        results_dir = build_results_dir(base_results_root, unit_name)
        # Output folder on Desktop
        html_out_dir = os.path.join(get_desktop_dir(), "EOL_Plots")

    try:
        if excel_path:
            print(f"[INFO] Using: {os.path.basename(excel_path)}")
            plot_from_file(excel_path, html_out_dir=html_out_dir)
        else:
            start_unit, end_unit = parse_unit_range(unit_range)
            print(f"[INFO] Using range {start_unit}..{end_unit} in: {results_dir}")
            plot_from_range(results_dir, start_unit, end_unit, html_out_dir=html_out_dir)
    except Exception as e:
        print(f"[ERROR] Failed: {e}")
