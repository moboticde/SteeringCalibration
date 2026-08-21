# Implementation Plan: Product-Driven Traction Calibration

**Branch/Spec**: `002-product-driven-traction-calibration`  
**Date**: 2026-07-21

## Summary

Move traction calibration from a motor-barcode prompt to a product-number workflow. Product scan can register traction-only numbers without requiring a Manufacturing folder. The backend chooses DD/ST from barcode markers and keeps writing calibration statistics.

## Technical Context

- GUI/runtime: `main/CalibrationGUI.py`
- Product scan fallback: `main/product_context.py`
- Browser UI: `main/CalibrationGUI.html`
- Tests: `tests/test_product_family_folder.py`
- External script root: `/home/mobotic/Internal Projects/TrCalibration-Linux`
- Statistics workbook: `/home/mobotic/Manufacturing/Calibration.xlsx`

## Implementation Approach

1. Let product scans without a product folder return a traction-only product cache with steering disabled.
2. Add a traction eligibility helper based on the scanned product number.
3. Change the traction prompt and request parameter from motor barcode to product number/`product_barcode`.
4. Keep backend compatibility with old `motor_barcode` callers.
5. Preserve marker-based DD/ST script selection and attempt 9 PASS/FAIL parsing.
6. Save workbook rows under a `Product Number` header while migrating the legacy `Motor Number` header.
7. Add hardware-free tests for the new scan, selection, and workbook behaviors.

## Risks

- The external traction scripts may later need the product number passed as an argument; this plan preserves current no-argument execution because that is the existing contract.
- More DD markers may be required as new products are introduced. Keep marker configuration centralized.
- SO exclusion is still a policy assumption; replace `traction_calibration_status_for_product()` if real product-spec rules supersede it.

## Validation

Automated:

- `python3 -m py_compile main/CalibrationGUI.py main/product_context.py tests/test_product_family_folder.py`
- Focused pytest module when pytest is installed: `python3 -m pytest tests/test_product_family_folder.py`

Manual hardware validation:

- Scan product number `99038922252125052947221126788` and confirm Traction is available without a product folder.
- Run Traction Calibration and confirm `DD_Calibration.py` is selected.
- Run a product number without DD markers and confirm `ST_Calibration.py` is selected.
- Confirm `/home/mobotic/Manufacturing/Calibration.xlsx` receives product number, program, and PASS/FAIL status.
