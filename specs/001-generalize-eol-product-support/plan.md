# Implementation Plan: Generalize EOL Product Support

**Branch/Spec**: `001-generalize-eol-product-support`  
**Date**: 2026-07-21

## Summary

Replace SO-only EOL assumptions with product-folder/specification-driven EOL eligibility. Preserve the existing operator scan modes, status workbook compatibility, and external EOL-case execution path.

## Technical Context

- GUI/runtime: `main/CalibrationGUI.py`
- Product lookup/spec parsing: `main/product_context.py`, `io_helpers/find_product_folder.py`
- Status workbook and EOL preparation gate: `main/reporting.py`
- External EOL runner integration: EOL functions currently inside `main/CalibrationGUI.py`
- Production product root: `/home/mobotic/Manufacturing`
- Product folder contract: `ProductSpecifications_V2.xlsx`, `01_SwConfiguration/`, `02_EOL_Recepies/`, `04_Results/`

## Constitution Check

- Production safety: EOL eligibility changes must fail closed when required files or preparation status are missing.
- Existing hardware boundaries: no new CAN, relay, camera, MU, or EOL hardware wrappers.
- Product truth: use product specifications and product folders, not hard-coded barcode prefixes.
- Traceability: keep status/done workbook naming and report paths compatible.
- Hardware-free tests: required for eligibility and scan-mode logic.
- Operator workflow: messages must stay actionable in the GUI.

## Proposed Structure

No broad restructuring is required for this feature. Add small helpers near existing ownership boundaries:

- `main/product_context.py`: expose recipe/path validation helpers if they belong with product-folder contracts.
- `main/reporting.py`: expose steering preparation gate helpers.
- `main/CalibrationGUI.py`: keep task dispatch and state changes; replace SO-only checks with product eligibility calls.

A later refactor can extract `main/eol_runner.py`, but that is not required to complete this feature safely.

## Implementation Approach

1. Identify and remove SO-only EOL blocks in `AppState.snapshot()`, `AppState.start_task()`, and `run_task()`.
2. Add product EOL eligibility helper that accepts product directory, product code, product parameters, and steering availability.
3. Validate required EOL recipe files before enabling or launching EOL.
4. Preserve steering preparation gate only for products with steering information.
5. Keep camera auto-scan and scanner/manual input behavior unchanged.
6. Update operator-facing messages for missing folder/spec/recipes/status/tester input.
7. Add hardware-free tests for SO and non-SO products.

## Risks

- Some non-SO product workflows may still require motor barcode input; do not assume a universal default.
- External EOL-case may contain its own product-family assumptions; GUI tests should verify launch arguments, while hardware/manual validation must confirm end-to-end behavior.
- `resources/config.yaml` still points `product_base` at the repo; production config should align with `/home/mobotic/Manufacturing` or callers outside the GUI may resolve differently.

## Validation

Automated:

- Product lookup tests for Manufacturing roots.
- EOL eligibility tests for steering prepared/not prepared products.
- EOL eligibility tests for non-steering products with valid recipes.
- Scan-mode tests for QR camera auto-scan and scanner/manual input.
- Existing focused tests: `tests/test_product_family_folder.py`, `tests/test_eol_conf_status.py`, `tests/test_can_interface_messages.py`, `tests/test_eol_startup_safety.py`.

Manual hardware validation:

- Run EOL with one SO product.
- Run EOL with at least one non-SO product from Manufacturing.
- Verify report files are written under the resolved product folder `04_Results/`.
- Verify missing recipe/spec cases show clear GUI errors and do not start hardware tests.
