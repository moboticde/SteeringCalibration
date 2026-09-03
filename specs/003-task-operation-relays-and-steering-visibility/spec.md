# Feature Specification: Task Operation Relays And Steering Visibility

**Feature Branch**: `003-task-operation-relays-and-steering-visibility`
**Created**: 2026-07-22
**Status**: Draft
**Input**: When an operator clicks a GUI program button, relays for operation should activate at the beginning of the program and deactivate at the end. The GUI should not show steering controls when there is no product or when the product has no steering data.

## User Scenarios & Testing

### Scenario 1 - Program Run Owns Operation Relay Window

An operator starts a GUI operation that can execute configuration, write zero, calibration, TestCalibration, traction calibration, script loading, or config loading. Before that operation body begins, the GUI activates the task start relay mask that matches manual Power On. When the operation finishes, fails, or raises an exception, the GUI deactivates task relays.

**Why this matters**: Operators should not manually prepare and clear task relays around each program run, and relays must not remain active after a completed or failed task.

**Independent Test**: Stub the relay Arduino and a task body. Verify the operation relay mask is set before task execution and mask `0` is set in task cleanup for success and failure.

### Scenario 2 - Relay Failure Blocks The Program

An operator starts a program while relay hardware is missing or cannot confirm the operation mask. The GUI fails closed, the program body is not executed, and the operator sees an actionable message.

**Why this matters**: Starting motion or EOL work with an unknown relay state is unsafe.

**Independent Test**: Stub relay activation to raise or return failure. Verify task execution is skipped, task status becomes failed, and relay cleanup is attempted only when activation may have changed outputs.

### Scenario 3 - Steering Controls Appear Only For Steering Products

Before a product is scanned or entered, the Steering workflow tab and steering program buttons are not shown. If the scanned product resolves with steering information, the Steering workflow appears. If the scanned product is traction-only or its product specification has no steering information, steering controls stay hidden and the active workflow moves to Traction or EOL when available.

**Why this matters**: Steering actions depend on product-specific steering node ID, CAN bitrate, zero angle, and steering script. Showing steering actions without a steering product creates invalid operator choices.

**Independent Test**: Feed `/status` snapshots for no product, steering product, and traction-only/no-steering product. Verify steering tab and steering task buttons are hidden except for the steering-product snapshot.

## Requirements

### Functional Requirements

- **FR-001**: The GUI MUST activate task start relays before executing started operation task bodies for `run_all`, `traction_calibration`, `load_script_config`, `load_script`, `load_config`, `start_calibration`, `test_calibration`, and `start_zeroing`.
- **FR-002**: Task relay activation MUST reuse the existing Arduino relay path and MUST start with `task_start_relay_mask()` (`0x0CF`, matching manual Power On); it MUST NOT introduce a second relay protocol.
- **FR-003**: If task relay activation cannot be confirmed, the task body MUST NOT execute and the GUI MUST show a failed status explaining that task relays could not be activated.
- **FR-004**: The GUI MUST deactivate task relays at task completion, task failure, or task exception by setting the relay mask to `0`.
- **FR-005**: Relay deactivation failure MUST be reported in the GUI log/status without hiding the original task failure.
- **FR-006**: Existing internal power-cycle flows MAY temporarily change relay masks during a task, but final task cleanup MUST still leave operation relays deactivated.
- **FR-006a**: Steering operation tasks MUST connect CAN after task start relays have been activated and settled. Configuration-style tasks (`run_all`, `load_script_config`, and `load_script`) MUST try the standard node `59` and the resolved product steering node; post-configuration tasks MUST use the resolved product steering node. They MUST NOT run the old standard-node/product-node CAN preflight gate before relays are active.
- **FR-006b**: MU configuration loading MUST enable operation auxiliary relay q6 only around the MU config write, then restore the previous relay mask.
- **FR-007**: Manual relay controls (`Power On`, `Restart`, `Power Off`, termination check, manual relay selection) MUST remain manual controls and MUST NOT recursively trigger task lifecycle relay wrapping.
- **FR-007a**: `run_eol` and `show_current_zero` MUST NOT use the GUI task-level operation-relay lifecycle; their own internal power-cycle or read/move flows remain responsible for relay/power behavior.
- **FR-008**: The `/status` payload MUST distinguish "no product scanned" from "product scanned with no steering information" so the browser can hide steering controls for both cases while preserving traction-only availability.
- **FR-009**: Before a product is scanned or entered, the browser MUST hide the Steering workflow tab and steering program controls.
- **FR-010**: After product resolution, the browser MUST show Steering workflow controls only when `steering_available` is true.
- **FR-011**: For traction-only product numbers with no Manufacturing folder, Traction availability from spec `002` MUST remain available while Steering remains hidden.
- **FR-012**: EOL availability from spec `001` MUST remain product-eligibility driven and MUST NOT be blocked solely because the Steering workflow is hidden.

### Non-Functional Requirements

- **NFR-001**: Changes must be scoped to `main/CalibrationGUI.py`, `main/CalibrationGUI.html`, and focused hardware-free tests unless implementation discovers an existing helper needs a narrow extension.
- **NFR-002**: Hardware-free tests must cover lifecycle relay success, lifecycle relay activation failure, lifecycle relay cleanup after failure, and steering UI visibility state.
- **NFR-003**: Hardware-affecting behavior must fail closed: unknown relay state before an operation task starts blocks that task, and cleanup attempts to set mask `0`.
- **NFR-004**: Operator messages must remain coherent while background tasks are running and must not require debug-log inspection for normal next steps.

## Key Entities

- **Task Start Relays**: The relay mask returned by `task_start_relay_mask()`, currently the controller power relays (`0x0CF`) matching the manual Power On path used before CAN connect.
- **Operation Auxiliary Relay**: Relay q6, added to controller power by `operation_relay_mask()` (`0x0EF`) only for the MU/encoder configuration window.
- **Task Lifecycle**: The period beginning after a GUI task button is accepted by `AppState.start_task()` and ending when `_run_task()` records success or failure.
- **Steering Product**: A resolved product context whose product specification provides steering controller type, steering node ID, CAN bitrate, and zero angle.
- **Traction-Only Product Number**: A scanned or entered product number that enables traction calibration without a Manufacturing product folder and without steering controls.

## Assumptions

- "Program button" means task buttons served through `POST /start?task=...`; manual relay and CAN utility buttons are control actions, not program runs.
- The task-start relay state must match manual Power On (`0x0CF`); enabling q6 before CAN connect can prevent the controller from responding. q6 is still required during MU config write, so it is enabled only for that narrow step.
- Configuration, Write Zero, and Calibration start from the same operator-facing sequence as the manual Power On flow: switch task relays on, wait for the hardware to settle, then connect CAN before running the task body. Configuration-style tasks may connect on standard node `59` because fresh units may not yet have the product Node ID.
- Product scan state is already available in `/status` as `product_scan_completed` and steering capability as `steering_available`.
- Relay cleanup to mask `0` is the requested "deactivated" end state.
- Failure mode: if activation/readback fails for one of the operation tasks, the task body is skipped and cleanup attempts relay mask `0`; if cleanup fails, the GUI reports the cleanup failure and marks the task failed.
- Manual validation: on hardware, run `load_script_config`, `start_zeroing`, `start_calibration`, `run_eol`, and `show_current_zero` in automatic relay mode. Confirm Configuration activates task mask `0x0CF`, waits for relay settle, tries CAN on node `59` and/or the product node before task body work, enables auxiliary relay to `0x0EF` for MU config load, reaches MU Set Interface, restores the previous relay mask after MU config, and that only the operation tasks show task relay activation/deactivation status while EOL/Show Current Zero do not show the GUI task-level relay messages.

## Out Of Scope

- Changing the Arduino relay protocol or relay numbering.
- Changing product-folder resolution, EOL recipe validation, or traction DD/ST program selection.
- Rewriting external EOL-case or TrCalibration-Linux scripts.
- Changing manual hardware controls outside the visibility needed for steering workflow controls.
