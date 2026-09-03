# Tasks: Generalize EOL Product Support

**Input**: `spec.md`, `plan.md`, project memory.  
**Goal**: EOL works for multiple Manufacturing product families and no longer depends on SO-1000 barcode checks.

## Phase 1 - Baseline Tests

- [x] T001 Add or update tests for EOL eligibility with a prepared steering product.
- [x] T002 Add tests for EOL eligibility with a non-steering product that has valid `02_EOL_Recepies/`.
- [x] T003 Add tests proving non-SO product barcodes are not rejected by GUI EOL availability or launch validation.
- [x] T004 Add scan-mode tests showing QR camera auto-scan still starts automatically and scanner/manual modes still wait for input.

## Phase 2 - Product And Recipe Validation

- [x] T005 Add a product-folder EOL recipe validation helper using the existing resolved product directory.
- [x] T006 Define actionable validation messages for missing product folder, missing `ProductSpecifications_V2.xlsx`, missing `02_EOL_Recepies/`, and missing required recipe workbooks.
- [x] T007 Ensure the helper supports both `/home/mobotic/Manufacturing/01_Products/<family>` and `/home/mobotic/Manufacturing/<family>` layouts.

## Phase 3 - Remove SO-Only EOL Gating

- [x] T008 Replace `AppState.snapshot()` SO-only EOL availability logic with product eligibility logic.
- [x] T009 Replace `AppState.start_task()` SO-only `run_eol` check with product eligibility and preparation checks.
- [x] T010 Replace `run_task("run_eol")` `SO-1000` prefix validation with resolved product validation.
- [x] T011 Remove or narrow default `motor_barcode = "0"` behavior so it only applies to product workflows that explicitly require it.

## Phase 4 - Preserve Steering Safety Gate

- [x] T012 Keep Configuration -> Write Zero -> Calibration sequence gating for products with steering information.
- [x] T013 Allow products without steering information to proceed to EOL when product spec and recipes are valid.
- [x] T014 Keep existing done-workbook behavior: a present `<barcode>_done.xlsx` reports EOL already complete.

## Phase 5 - Operator Feedback

- [x] T015 Update GUI status messages to distinguish missing tester name, missing product code, missing recipes, missing steering preparation, and active task conflicts.
- [x] T016 Verify the EOL button/report state remains coherent across scan option changes and completed scans.

## Phase 6 - Verification

- [ ] T017 Run focused hardware-free tests: `ST_NONINTERACTIVE=1 .venv/bin/python -m pytest -q tests/test_product_family_folder.py tests/test_eol_conf_status.py tests/test_can_interface_messages.py tests/test_eol_startup_safety.py`.
- [ ] T018 Run any new EOL eligibility tests added for this feature.
- [ ] T019 Document manual validation steps and results for SO and non-SO product EOL runs.

## Dependencies

- T001-T004 must be completed before implementation changes where practical.
- T005-T007 should be completed before T008-T011.
- T012-T014 depend on T008-T011.
- T017-T019 are final verification tasks.
