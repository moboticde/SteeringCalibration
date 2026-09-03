from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


MANUFACTURING_ROOT = Path("/home/mobotic/Manufacturing")
EOL_RECIPE_DIR_NAME = "02_EOL_Recepies"
EOL_TRACTION_RECIPE = "TractionRecepie.xlsx"
EOL_STEERING_RECIPE_FILES = (
    "SteeringAppRecepie.xlsx",
    "SteeringMotorRecepie.xlsx",
)



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
    product_dir: Path | None
    spec_path: Path | None
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


def has_traction_information(params: dict[str, object]) -> bool:
    if not _product_value_present(params.get("Traction Controller Type")):
        return False
    try:
        _require_int_param(params, "Traction Node ID", 1, 127)
    except Exception:
        return False
    return True


def is_valid_xlsx(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return "[Content_Types].xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def required_eol_recipe_files(params: dict[str, object]) -> list[str]:
    required: list[str] = []
    if has_traction_information(params):
        required.append(EOL_TRACTION_RECIPE)
    if has_steering_information(params):
        required.extend(EOL_STEERING_RECIPE_FILES)
    return required


def validate_eol_recipe_files(
    product_dir: Path | None,
    params: dict[str, object],
) -> tuple[bool, str, str]:
    if product_dir is None:
        return False, "EOL disabled: product folder not found.", ""

    required = required_eol_recipe_files(params)
    if not required:
        return (
            False,
            "EOL disabled: product specification has no traction or steering controller information.",
            "",
        )

    recipe_dir = product_dir / EOL_RECIPE_DIR_NAME
    if not recipe_dir.is_dir():
        return False, f"EOL disabled: recipe folder not found: {recipe_dir.name}.", str(recipe_dir)

    missing = [name for name in required if not (recipe_dir / name).is_file()]
    if missing:
        missing_text = ", ".join(missing)
        return False, f"EOL disabled: missing recipe files: {missing_text}.", str(recipe_dir)

    invalid = [name for name in required if not is_valid_xlsx(recipe_dir / name)]
    if invalid:
        invalid_text = ", ".join(invalid)
        return False, f"EOL disabled: invalid recipe workbooks: {invalid_text}.", str(recipe_dir)

    return True, "EOL recipes found.", str(recipe_dir)


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
            message = (
                f"{qr_code}: no product folder found. "
                "Steering tab disabled; traction calibration can use the product number."
            )
            print(f"[INFO] {message}")
            return ProductSpecCache(
                qr_code=str(qr_code),
                product_dir=None,
                spec_path=None,
                params={},
                context=None,
                steering_available=False,
                message=message,
            )
    else:
        product_dir = resolve_product_family_dir(
            qr_code,
            Path(product_dir_raw),
            product_base,
        )
    try:
        spec_path = find_product_spec_path(product_dir)
    except FileNotFoundError:
        message = (
            f"{qr_code}: product specification not found. "
            "Steering tab disabled; traction calibration can use the product number."
        )
        print(f"[INFO] {message}")
        return ProductSpecCache(
            qr_code=str(qr_code),
            product_dir=product_dir,
            spec_path=None,
            params={},
            context=None,
            steering_available=False,
            message=message,
        )
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
