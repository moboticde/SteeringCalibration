# Feature Specification: Generalize EOL Product Support

**Feature Branch**: `001-generalize-eol-product-support`  
**Created**: 2026-07-21  
**Status**: Draft  
**Input**: EOL must work for different products resolved from Manufacturing product folders, not only SO-1000. Operators either scan/type the product number in the UI input flow, or QR camera mode scans automatically.

## User Scenarios & Testing

### Scenario 1 - Run EOL For Any Resolved Product

An operator selects EOL, provides the product number by scanner/manual input or uses QR camera auto-scan, and the application resolves the matching product folder under `/home/mobotic/Manufacturing`. If the folder contains a valid `ProductSpecifications_V2.xlsx` and the required `02_EOL_Recepies/` files, EOL can run for that product family without requiring an `SO-1000` barcode prefix.

**Why this matters**: The manufacturing workflow supports multiple product families. SO-only gating blocks valid products and creates hard-coded behavior that conflicts with product-folder truth.

**Independent Test**: Use fake Manufacturing product folders for an SO product and a non-SO product, each with product specification and EOL recipe placeholders. Verify EOL availability and launch arguments are derived from the scanned or entered product number, not from an SO prefix check.

### Scenario 2 - Scan Mode Behavior Is Preserved

When QR camera mode is selected and relay hardware is ready, the GUI starts product scanning automatically. When QR scanner, barcode scanner, or manual mode is selected, the GUI shows the product-code input flow and waits for the operator to scan or type the product number.

**Why this matters**: Operators use different scan devices on the production floor. EOL support must not break the established input workflow.

**Independent Test**: Stub camera scanning and manual input paths. Verify camera mode triggers automatic product resolution, while the other scan modes require submitted input before EOL preflight.

### Scenario 3 - Product-Specific EOL Gating

For products with steering preparation requirements, EOL remains blocked until Configuration, Write Zero, and Calibration are OK in sequence. For products without steering information, EOL may still be allowed when the product specification and `02_EOL_Recepies/` define valid EOL tests.

**Why this matters**: Steering safety gates must remain strict, but non-steering products should not be blocked by missing steering-only data.

**Independent Test**: Verify three cases: steering product missing preparation is blocked, steering product with OK sequence is allowed, non-steering product with recipes is allowed without steering status workbook gating.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST remove runtime EOL eligibility checks that require product barcodes to start with `SO-1000`.
- **FR-002**: The system MUST resolve EOL product data from the scanned or entered product number using the configured Manufacturing product-folder lookup.
- **FR-003**: The system MUST support product folders under `/home/mobotic/Manufacturing/01_Products` and direct product-family folders under `/home/mobotic/Manufacturing`.
- **FR-004**: The system MUST require a valid `ProductSpecifications_V2.xlsx` before launching EOL.
- **FR-005**: The system MUST require `02_EOL_Recepies/` files needed by the external EOL/test-manager flow before launching EOL, and it MUST show an actionable operator error if they are missing.
- **FR-006**: For products with steering information, the system MUST preserve the existing EOL preparation gate: Configuration, Write Zero, and Calibration must be OK in sequence unless EOL is already done.
- **FR-007**: For products without steering information, the system MUST not require steering-only status rows before EOL if product-specific EOL recipes exist.
- **FR-008**: QR camera mode MUST keep automatic scan behavior after relay hardware is ready.
- **FR-009**: QR scanner, barcode scanner, and manual modes MUST keep the appearing product-code input flow.
- **FR-010**: EOL launch arguments MUST pass the resolved product number as the unit serial/product barcode. Motor barcode handling MUST remain product-specific and must not default to `0` except where the product workflow explicitly requires it.
- **FR-011**: Existing status workbook and done workbook naming MUST remain compatible: `<product>/04_Results/<barcode>_status.xlsx` and `<product>/04_Results/<barcode>_done.xlsx`.
- **FR-012**: Operator-facing messages MUST explain whether EOL is blocked by missing product folder, missing product specification, missing recipes, missing steering preparation, active task state, or tester-name input.

### Non-Functional Requirements

- **NFR-001**: Changes must reuse `main/product_context.py`, `main/reporting.py`, `io_helpers/find_product_folder.py`, and the existing external EOL runner path.
- **NFR-002**: Hardware-free automated tests must cover product resolution, EOL eligibility, and scan-mode behavior.
- **NFR-003**: The implementation must not create a second product resolver, EOL runner, report workbook format, CAN layer, or recipe parser.
- **NFR-004**: Hardware-affecting behavior must fail closed and surface clear GUI status.

## Key Entities

- **Product Code**: Value read from QR camera, QR scanner, barcode scanner, or manual input.
- **Product Folder**: Manufacturing folder resolved from product code; provides specs, configuration, recipes, and results.
- **Product Specification**: `ProductSpecifications_V2.xlsx`, source of product parameters and steering availability.
- **EOL Recipes**: Workbooks under `02_EOL_Recepies/` consumed by the external EOL/test-manager flow.
- **Preparation Status Workbook**: `<barcode>_status.xlsx`, used to gate steering-product EOL.
- **EOL Done Workbook**: `<barcode>_done.xlsx`, final EOL success marker/report.

## Assumptions

- Production product data is under `/home/mobotic/Manufacturing`.
- Product families may appear either below `01_Products/` or directly under Manufacturing.
- Products with steering information require steering preparation before EOL.
- Products without steering information can still have valid EOL recipes.
- External EOL-case remains the owner of executing product tests; this feature only fixes GUI eligibility, product resolution, validation, and launch arguments.

## Out Of Scope

- Rewriting the external EOL-case project.
- Changing CAN, relay, MU SDK, or camera driver behavior.
- Changing workbook file format beyond compatibility-preserving validation.
- Adding new product-folder naming conventions.
