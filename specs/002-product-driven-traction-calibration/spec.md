# Feature Specification: Product-Driven Traction Calibration

**Feature Branch**: `002-product-driven-traction-calibration`  
**Created**: 2026-07-21  
**Status**: Draft  
**Input**: Traction calibration should use the scanned/entered product number, for example `99038922252125052947221126788`, without requiring a Manufacturing product folder. The barcode content selects the DD or ST external calibration script and results are saved to the calibration statistics workbook.

## User Scenarios & Testing

### Scenario 1 - Run Traction From Product Number

An operator scans or enters a product number and opens the Traction tab. The GUI prompts for the product number for traction calibration, defaults to the scanned product number when available, and starts the traction calibration task.

**Why this matters**: The traction workflow is identified by the product number itself and should not be blocked by missing product-family folders or steering specifications.

**Independent Test**: Resolve a product number with no product folder and verify steering is disabled while traction remains available. Start traction with that product number and verify the backend uses it for program selection.

### Scenario 2 - Select Correct DD/ST Script

The backend checks the product number text for known DD markers. Product numbers containing `1126788` or `1058534` run `DD_Calibration.py`; all other product numbers run `ST_Calibration.py`.

**Why this matters**: Operators should not manually choose DD or ST, and product folders are not required for this decision.

**Independent Test**: Verify `99038922252125052947221126788` selects DD, the individual marker values select DD, and unrelated numbers select ST.

### Scenario 3 - Save Statistical Results

After the external script exits, the GUI parses attempt 9 calibration output and appends a PASS/FAIL result to `/home/mobotic/Manufacturing/Calibration.xlsx`.

**Why this matters**: Manufacturing needs a consistent statistics workbook for traction calibration outcomes.

**Independent Test**: Stub subprocess output and verify the workbook receives date, product number, selected program, and PASS/FAIL status. Verify legacy `Motor Number` headers migrate without losing existing rows.

## Requirements

### Functional Requirements

- **FR-001**: The GUI MUST allow traction calibration for a scanned or entered non-SO product number even when no product folder or product specification exists.
- **FR-002**: The Traction Calibration prompt MUST ask for a product number, not a motor barcode.
- **FR-003**: The backend MUST accept `product_barcode` for traction calibration and keep `motor_barcode` as a compatibility fallback.
- **FR-004**: The backend MUST select `DD_Calibration.py` when the product number contains `1126788` or `1058534`.
- **FR-005**: The backend MUST select `ST_Calibration.py` when no DD marker is present.
- **FR-006**: The backend MUST continue running scripts from `/home/mobotic/Internal Projects/TrCalibration-Linux`.
- **FR-007**: The backend MUST continue deriving PASS only when subprocess exit code is 0 and attempt 9 has `SinOff`, `CosOff`, `GainC`, and `Harm4` equal to 0.
- **FR-008**: The backend MUST append traction results to `/home/mobotic/Manufacturing/Calibration.xlsx` with product number, selected program, and status.
- **FR-009**: Existing traction statistics workbooks using the legacy `Motor Number` column MUST keep prior rows and migrate the header to `Product Number`.
- **FR-010**: Operator-facing disabled messages MUST come from traction eligibility state rather than hard-coded SO-only GUI text.

### Non-Functional Requirements

- **NFR-001**: Changes must reuse the existing GUI task dispatch, subprocess execution, stdout parsing, and workbook helpers.
- **NFR-002**: Hardware-free tests must cover no-folder product scan behavior, DD/ST marker selection, attempt 9 parsing, and workbook logging.
- **NFR-003**: The change must not add a product-folder dependency to traction calibration.

## Key Entities

- **Product Number**: Barcode value used to enable traction and choose ST/DD script.
- **DD Markers**: Product-number substrings `1126788` and `1058534`.
- **Traction Script Root**: `/home/mobotic/Internal Projects/TrCalibration-Linux`.
- **Statistics Workbook**: `/home/mobotic/Manufacturing/Calibration.xlsx`.

## Assumptions

- SO-prefixed units remain excluded from traction calibration unless a later product rule changes this.
- External traction scripts remain responsible for hardware interaction and do not currently require the product number as an argv argument.
- Attempt 9 stdout format remains the result contract for PASS/FAIL classification.

## Out Of Scope

- Rewriting `DD_Calibration.py` or `ST_Calibration.py`.
- Adding product-folder recipes for traction calibration.
- Changing CAN, relay, MU SDK, or camera driver behavior.
