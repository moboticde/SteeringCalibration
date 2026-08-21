# Implementation Plan: Task Operation Relays And Steering Visibility

**Branch/Spec**: `003-task-operation-relays-and-steering-visibility`
**Date**: 2026-07-22

## Summary

Wrap GUI-started task execution with operation relay activation and final relay deactivation. Update browser state handling so steering workflow controls are hidden until a resolved steering product is present, while preserving traction-only and EOL availability rules from specs `001` and `002`.

## Technical Context

- GUI/runtime: `main/CalibrationGUI.py`
- Browser UI: `main/CalibrationGUI.html`
- Relay driver boundary: `drivers/driver_arduino.py`
- Existing relay helpers: `_get_or_connect_relay_arduino()`, `_confirmed_set_relays()`, `operation_relay_mask()`, `relay_snapshot()`
- Existing task lifecycle: `AppState.start_task()` accepts tasks and `_run_task()` executes `run_task()`
- Existing product state: `/status` exposes `product_scan_completed`, `steering_available`, `traction_available`, and `eol_available`

## Constitution Check

- Production safety: Relay activation must fail closed and skip task execution if the operation mask cannot be confirmed; cleanup sets mask `0`.
- Existing hardware boundaries: reuse `driver_arduino.py` through existing GUI relay helpers.
- Product truth: steering visibility follows resolved product data, not hard-coded product family defaults.
- Traceability: task reports/workbooks are unchanged.
- Hardware-free tests: cover relay lifecycle and UI visibility state with fakes.
- Operator workflow: task status must explain relay activation or cleanup failures.

## Implementation Approach

1. Add a small task lifecycle relay helper in `CalibrationGUI.py` that activates `operation_relay_mask()` before `run_task()` and deactivates mask `0` in a `finally` block.
2. Call the helper from `_run_task()` so every accepted `POST /start` task gets the same relay behavior without wrapping manual relay routes.
3. Preserve original task exceptions and status while appending cleanup failure information if final deactivation fails.
4. Expose a clear status value if needed for "product scanned" versus "no product scanned"; otherwise reuse existing `product_scan_completed` and `steering_available`.
5. Update `CalibrationGUI.html` polling logic to hide the Steering tab/panel and all steering task buttons unless a product has been scanned and `steering_available === true`.
6. Ensure active tab selection moves away from Steering when Steering becomes hidden.
7. Add hardware-free tests for relay activation/cleanup order and activation failure behavior.
8. Add a lightweight UI logic check where practical, or keep browser behavior covered by deterministic JavaScript state rules and manual validation if no JS test harness exists.

## Risks

- Some existing task internals intentionally power-cycle relays. Final cleanup to `0` is required by the request, but manual hardware validation must confirm operators expect power to be off after each program.
- `run_eol` releases the GUI relay Arduino before starting EOL-case. The wrapper must either reacquire the Arduino for cleanup or report cleanup failure without masking the EOL result.
- Traction calibration delegates to an external project. Activation and cleanup in the GUI process should still bound the delegated subprocess lifetime.

## Validation

Automated:

- `python3 -m py_compile main/CalibrationGUI.py`
- Focused pytest for relay/CAN/product GUI behavior, for example:
  `ST_NONINTERACTIVE=1 .venv/bin/python -m pytest -q tests/test_can_interface_messages.py tests/test_product_family_folder.py`

Manual hardware validation:

- Start each steering program button and verify operation relays activate before movement/configuration and are off after completion.
- Start Traction Calibration and verify relays are off after the external script exits.
- Start EOL and verify relays are off after EOL completes or fails.
- Simulate/disconnect relay Arduino before a task and verify the task does not start.
- Open GUI with no product scanned and verify Steering is hidden; scan a steering product and verify Steering appears; scan a traction-only/no-steering product and verify Steering stays hidden.
