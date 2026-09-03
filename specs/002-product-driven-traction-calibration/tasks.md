# Tasks: Product-Driven Traction Calibration

**Input**: `spec.md`, `plan.md`, current GUI traction workflow.  
**Goal**: Traction calibration uses product numbers, does not require product folders, selects DD/ST by barcode marker, and preserves statistics logging.

## Phase 1 - Product Scan And Availability

- [x] T001 Allow product scans without a Manufacturing product folder to register a traction-only product number.
- [x] T002 Add traction eligibility helper and expose its message in `/status`.
- [x] T003 Replace hard-coded GUI SO-disabled traction text with backend-provided eligibility messages.

## Phase 2 - Product Number Traction Start

- [x] T004 Change the Traction Calibration prompt from motor barcode to product number.
- [x] T005 Send `product_barcode` for traction calibration.
- [x] T006 Keep backend fallback for existing `motor_barcode` callers.

## Phase 3 - Script Selection And Statistics

- [x] T007 Verify long product number `99038922252125052947221126788` selects DD.
- [x] T008 Preserve marker-based DD/ST script selection.
- [x] T009 Store traction statistics with a `Product Number` header.
- [x] T010 Migrate legacy `Motor Number` workbook headers without dropping rows.

## Phase 4 - Verification

- [x] T011 Add hardware-free tests for no-folder traction-only scan behavior.
- [x] T012 Add hardware-free tests for product-number marker selection.
- [x] T013 Add hardware-free tests for legacy workbook header migration.
- [ ] T014 Run focused pytest module once pytest is installed in the environment.
- [ ] T015 Run manual hardware validation with one DD product number and one ST product number.
