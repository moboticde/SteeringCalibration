# StCalibration-Linux Constitution

## Core Principles

### I. Production Safety Is Mandatory

The application controls steering motors, relays, controller power, CAN
communication, and encoder EEPROM. Any change that can move hardware, write
controller parameters, write encoder parameters, change relay state, or alter EOL
eligibility must fail closed, surface clear operator status, and preserve existing
cleanup paths. Non-interactive execution must raise errors instead of waiting for
operator input.

### II. Existing Hardware Boundaries Are Reused

Device access belongs in the existing driver and logic boundaries. New code must
reuse:

- `drivers/driver_can.py` for CANopen and SocketCAN setup.
- `drivers/driver_miControlF35.py` for MiControl F35 SDO operations.
- `drivers/driver_arduino.py` for relay and measurement protocol access.
- `drivers/driver_cam_st.py` and `drivers/driver_QRreader.py` for camera
  operations.
- `logic/FullCalibration.py` and `logic/FlashConfigZero.py` for MU SDK and
  encoder write flows.

Duplicated hardware wrappers are not allowed unless the plan identifies an
explicit replacement and migration path.

### III. Product Specification Is Product Truth

Product-specific values are resolved from scanned product codes and
`ProductSpecifications_V2.xlsx` through the existing product resolution path.
New features must not hard-code product family, node ID, CAN bitrate, zero angle,
or steering availability when those values can be resolved from product data.

### IV. Calibration Results Must Be Traceable

Configuration, Write Zero, Calibration, EOL, and traction-calibration outcomes
must remain traceable to product or motor barcode, timestamp, operator/tester
input where required, and the status workbook or calibration report that recorded
the result. Any change to workbook schema or report naming must include
compatibility behavior or a migration plan.

### V. Hardware-Free Tests Protect Logic

Logic that can be tested without physical devices must be covered by automated
tests. Hardware imports and device constructors should be isolated or stubbed so
tests can validate state machines, parsing, math, report normalization, product
resolution, and safety behavior without connecting CAN, USB, camera, relays, or
the MU interface.

### VI. Operator Workflow Stability Comes First

The browser GUI is the operator surface. New behavior must keep task state,
status lines, error messages, button availability, and report downloads coherent
while background tasks are running. Operators must not need to inspect debug logs
to understand normal next steps.

## Quality Gates

Every spec and implementation plan must answer:

- Which existing module owns this behavior today?
- What physical hardware can this affect?
- What happens if CAN, camera, Arduino, MU adapter, power supply, or product
  files are unavailable?
- Which behavior is covered by automated tests, and which behavior needs manual
  hardware validation?
- What existing report, workbook, log, or product data does the change read or
  write?

## Development Workflow

- Keep feature changes scoped to the owning module.
- Prefer small pure helpers for parsing, workbook, state-machine, and math logic.
- Preserve public task IDs and HTTP endpoints unless the spec requires an
  operator-facing workflow change.
- Do not modify vendor SDK files, generated logs, calibration backups, or product
  result artifacts unless that is the explicit purpose of the work.
- Use `ST_NONINTERACTIVE=1` for automated test runs that could otherwise prompt.

## Governance

This constitution is the project-level source of development constraints for
Spec Kit. Feature specs may add stricter requirements, but they may not weaken
hardware safety, reuse, traceability, or testability requirements without an
explicit constitution update.
