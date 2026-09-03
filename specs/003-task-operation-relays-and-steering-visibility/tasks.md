# Tasks: Task Operation Relays And Steering Visibility

**Input**: `spec.md`, `plan.md`, current GUI task lifecycle.
**Goal**: GUI-started tasks activate operation relays while running, deactivate relays when finished, and hide steering controls until a steering product is resolved.

## Phase 1 - Relay Lifecycle Tests

- [x] T001 Add hardware-free tests proving a successful GUI task activates the operation relay mask before task execution and sets mask `0` after task execution.
- [x] T002 Add hardware-free tests proving task exceptions still trigger mask `0` cleanup.
- [x] T003 Add hardware-free tests proving operation relay activation failure prevents the task body from running and reports a relay activation error.

## Phase 2 - Relay Lifecycle Implementation

- [x] T004 Add a scoped task relay lifecycle helper in `main/CalibrationGUI.py` using `_get_or_connect_relay_arduino()`, `_confirmed_set_relays()`, and `operation_relay_mask()`.
- [x] T005 Route `_run_task()` execution through the lifecycle helper for all `POST /start` tasks.
- [x] T006 Preserve original task result/exception handling while appending cleanup failure details when mask `0` cannot be confirmed.
- [x] T007 Confirm manual relay routes and power-supply routes do not use the lifecycle helper.

## Phase 3 - Steering Visibility

- [x] T008 Update `/status` usage or payload fields so the browser can determine that no product is scanned separately from no-steering product state.
- [x] T009 Hide the Steering workflow tab/panel and steering task buttons in `main/CalibrationGUI.html` unless `product_scan_completed === true` and `steering_available === true`.
- [x] T010 Keep Traction visible/available for traction-only product numbers from spec `002`.
- [x] T011 Keep EOL visibility/availability driven by product eligibility from spec `001`.
- [x] T012 Ensure active workflow tab changes away from hidden Steering controls.

## Phase 4 - Verification

- [x] T013 Run `python3 -m py_compile main/CalibrationGUI.py`.
- [x] T014 Run focused hardware-free pytest coverage for relay lifecycle and product/UI state.
- [ ] T015 Document manual hardware validation results for relay activation/deactivation and steering visibility.

## Dependencies

- T001-T003 should be written before T004-T006 where practical.
- T008 depends on understanding existing `/status` fields.
- T009-T012 depend on T008.
- T013-T015 are final verification tasks.
