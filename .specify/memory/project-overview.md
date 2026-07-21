# StCalibration-Linux Project Overview

## Purpose

StCalibration-Linux is a Linux-based manufacturing and calibration application
for Mobotic steering products. It coordinates product-code scanning, product
specification lookup, CANopen controller communication, relay and measurement
control through Arduino hardware, iC-Haus MU encoder configuration/calibration,
visual angle detection, steering zero write, calibration quality checks,
traction-calibration delegation, and EOL execution.

The application is production-facing. Its behavior is tied to real devices and
result artifacts, so new specs must build on the existing ownership boundaries
instead of creating parallel implementations.

## Primary Runtime

The main operator workflow is served by `main/CalibrationGUI.py` with the HTML
template in `main/CalibrationGUI.html`.

At startup, `main()` creates a `ThreadingHTTPServer` bound to `127.0.0.1` on an
ephemeral port, prints the URL, and attempts to open a browser. The browser UI
polls `/status` and invokes POST endpoints to scan products, check CAN, control
relays, run manual motor commands, start calibration tasks, clear logs, and
download EOL reports.

The central in-memory runtime object is `AppState` in `main/CalibrationGUI.py`.
It owns GUI-visible status, log text, active worker thread state, cached product
context, current report workbook, manual CAN controller handle, relay snapshots,
controller enabled/error state, and power-cycle coordination.

## Main Operator Tasks

Task IDs are defined in `TASKS` in `main/CalibrationGUI.py`:

- `run_all`: full steering workflow. It loads configuration, writes physical
  zero, runs encoder calibration, returns to current zero, then launches EOL.
- `run_eol`: runs the external EOL-case flow for SO-1000 product barcodes.
- `traction_calibration`: delegates traction motor calibration to the separate
  `TrCalibration-Linux` project and records results in
  `/home/mobotic/Manufacturing/Calibration.xlsx`.
- `load_script_config`: loads the product steering script and configuration and
  records Configuration status.
- `load_script`: loads the product steering script only.
- `load_config`: loads the MU encoder config only.
- `start_calibration`: runs steering encoder calibration without an additional
  post-calibration zero write.
- `test_calibration`: imports and runs `tests/TestCalibration.py`, then waits
  for a power cycle and restores controller SSI state.
- `show_current_zero`: reads the current visual/controller zero state.
- `start_zeroing`: writes physical steering zero and verifies persistence.

## HTTP Surface

`CalibrationRequestHandler` exposes:

- `GET /`: operator UI.
- `GET /logo.png`: Mobotic logo asset.
- `GET /status`: JSON snapshot of `AppState`.
- `GET /eol-report`: current product EOL done workbook when available.
- `POST /clear-log`: clear GUI log.
- `POST /kill-all`: reset task/runtime state.
- `POST /confirm-power-cycle`: release flows waiting for operator confirmation.
- `POST /scan-option`: choose QR camera, QR scanner, barcode scanner, or manual
  scan source.
- `POST /scan-product`: resolve product code and preflight CAN asynchronously.
- `POST /disconnect-can`: detach current manual CAN controller.
- `POST /check-can`: test standard/product CAN nodes and bitrates.
- `POST /controller-enable`: enable or disable the connected controller.
- `POST /clear-controller-errors`: clear MiControl errors.
- `POST /power-supply-output`: set controller relay power path on or off.
- `POST /relays`: read or set relay masks.
- `POST /manual-spin`: send manual RPM commands.
- `POST /start?task=...`: start one of the task IDs above.

New operator features should usually extend this surface instead of adding a
second server or control channel.

## Product Data Flow

Product context starts from a scanned or manually entered product code:

1. `resolve_product_scan_text()` receives the code.
2. `io_helpers/find_product_folder.py` resolves a matching product folder using
   `resources/config.yaml` and fallback search roots.
3. `find_product_spec_path()` locates `ProductSpecifications_V2.xlsx`.
4. `read_product_spec_parameters()` reads workbook parameters directly from the
   XLSX ZIP/XML structure.
5. Required steering values are extracted:
   - `Steering Controller Type`
   - `Steering Node ID`
   - `CAN Baudrate`
   - `Zero angle`
6. A `ProductContext` is cached in `AppState` with QR code, product directory,
   CAN bitrate, steering node ID, zero angle, and `SteeringScript.py` path.

If steering information is missing, the GUI disables steering-specific behavior
for that product instead of guessing defaults.

## Result Artifacts

The project writes simple XLSX workbooks by constructing ZIP/XML content in
`main/CalibrationGUI.py`; it does not depend on openpyxl for those reports.

Important result files:

- `<product>/04_Results/<barcode>_status.xlsx`: Configuration, Write Zero, and
  Calibration status rows.
- `<product>/04_Results/<barcode>_done.xlsx`: EOL completion marker/report.
- `MU/calib_logs/enc_1` and `MU/calib_logs/enc_2`: encoder calibration reports,
  raw data, and preserved temporary configs.
- `MU/config_backups`: before/after/zero-input encoder configuration backups and
  visual zero motion scale cache.
- `/home/mobotic/Manufacturing/Calibration.xlsx`: traction-calibration status
  workbook updated from this app when traction calibration is delegated.

EOL gating requires Configuration, Write Zero, and Calibration to be OK in order.
This logic exists in both GUI helpers and `managers/test_manager.py` for the
external EOL path.

## Directory Ownership

### `main/`

Owns the browser UI and runtime orchestration. `CalibrationGUI.py` is large and
contains product scanning, status workbook helpers, task dispatch, CAN preflight,
report management, relay orchestration, controller readiness checks, manual spin,
EOL integration, and HTTP request handling. `CalibrationGUI.html` owns the
operator layout and client-side polling/actions.

Specs that change operator workflow, task availability, status wording, HTTP
endpoints, report downloads, or cross-task orchestration usually start here.

### `logic/`

Owns production calibration and hardware workflows:

- `FullCalibration.py`: iC-Haus MU 3SL calibration using `ctypes`, raw data
  acquisition, analog/nonius analysis, protected zero parameter capture/restore,
  EEPROM storage, controller return-to-zero, quality callback events, and CLI
  entry point.
- `FlashConfigZero.py`: load MU configuration, write zero preset, visually guide
  zero moves, persist controller-side SSI absolute zero, verify EEPROM after
  power cycle, preserve stable config parameters, and read camera angle.
- `FlashSteeringScript.py`: resolve/import product-specific `SteeringScript.py`,
  load config functions, parse DSA node and new node ID, and apply scripts over
  CAN.
- `FlashConfig.py` and `FlashMPUFile.py`: legacy/config flashing paths around
  product folder lookup, CAN, DSA compatibility, and pymc script execution.
- `calibration_quality.py`: pure calibration quality dataclasses, report parsing,
  threshold evaluation, and report text generation.
- `traction.py`, `TractionHC.py`, `brake.py`, `steering_app.py`: test feedback
  routines used by `managers/test_manager.py`.

Specs that alter encoder calibration, zero write, EEPROM behavior, quality
criteria, or controller restore behavior should extend these modules, not create
new scripts beside them.

### `drivers/`

Owns physical device integrations:

- `driver_can.py`: CANopen network setup, SocketCAN bitrate enforcement,
  reconnect/reset, and generic node error clearing.
- `driver_miControlF35.py`: MiControl F35 node creation and SDO operations for
  errors, SSI encoder mode/status, direct position, store parameters, velocity
  and position control, serial number, and steering state.
- `driver_arduino.py`: Arduino serial discovery, binary frame protocol,
  relay mask commands, measurements, pause/resume, and INA measurement helpers.
- `driver_cam_st.py`: OpenCV steering marker and angle detection.
- `driver_QRreader.py`: QR camera configuration, decode fallbacks, ROI handling,
  preview behavior, camera fallback candidates, and CLI entry.
- `driver_owon.py`: optional OWON SPE6053 power supply backend over serial,
  USBTMC, or VISA.
- `driver_multimeter.py`: pyvisa multimeter access.
- `driver_mc.py`: compatibility wrapper around DSA/CAN SDO access.
- `driver_barcode.py`: Windows-oriented keyboard/barcode helper; likely legacy
  in the Linux deployment.

New specs should not duplicate VID/PID discovery, CAN setup, QR/camera probing,
or relay framing. Add capabilities to these drivers or wrap them from logic.

### `io_helpers/`

Owns filesystem/product lookup and requirements-document access:

- `find_product_folder.py`: maps product/unit IDs to product folders using
  `resources/config.yaml`.
- `find_device.py`: serial/VISA device discovery helpers.
- `requirements_doc.py`: product requirement workbook access through pandas and
  openpyxl.

### `managers/`

Contains orchestration helpers for test execution:

- `test_manager.py`: `TestRunner`, configuration completion verification,
  camera angle checks, motor zero moves, and test feedback calls.
- `MCU_manager.py`: dynamic import helper for MCU-specific modules.

### `processing/`

Owns test data processing and plotting:

- `data_processing.py`: pandas/numpy transformations for collected data.
- `plot_generator.py`: Plotly report generation.
- `classifier.py`, `thresholds.py`, `calib_progress.py`,
  `calib_prog_interactiv.py`, `clean_empty.py`: analysis, thresholds, progress,
  and cleanup utilities.

### `tests/`

Contains a mix of automated tests, hardware/manual scripts, and analysis tools.
Automated tests already protect:

- EOL startup safety and non-interactive error behavior.
- CAN interface failure/user messages.
- product family folder resolution.
- EOL configuration status sequencing.
- MiControl zero-save behavior.
- full calibration protected-parameter behavior with fake hardware.
- visual zero math and persistence helpers with fake MU/controller state.

Some files under `tests/` are not pure unit tests and may require camera,
hardware, data files, or manual execution.

### `resources/`

Contains configuration and hardware/vendor resources:

- `config.yaml`: Arduino, multimeter, CAN, power supply, and product base paths.
- `mcDSA-Exx.eds` and `CANedsGoldV005_0.eds`: CANopen EDS files.
- iC-MU encoder configuration files used as defaults, calibrated examples, and
  zero-write inputs.
- `mobotic-logo.png`: GUI logo asset.

### `systemd/`

Owns Linux SocketCAN bridge startup:

- `start_can0.py`: finds the configured serial CAN adapter by VID/PID and execs
  `slcand`.
- `st-can0.service`: systemd unit that loads `slcan`, starts the bridge, and
  brings `can0` up.

### `MU/`

Contains iC-Haus MU 3SL SDK files, the Linux shared library used by `ctypes`,
vendor examples/docs, calibration logs, and config backups. Treat SDK contents as
vendor-owned. Application code should use `logic/FullCalibration.py` or
`logic/FlashConfigZero.py` instead of directly editing vendor examples.

### `S-1000-200/`

Example/current product folder with:

- `ProductSpecifications_V2.xlsx`
- `01_SwConfiguration/SteeringScript.py`
- firmware/configuration files
- EOL recipes
- result artifacts

This is production/product data, not generic application code.

### `mc/`

Small local pymc compatibility shim used by MPU/config flashing. There is also a
larger copied `mc` tree inside product software configuration data.

## Entry Points

- GUI: `.venv/bin/python main/CalibrationGUI.py`
- Protected runner: `./run_protected.sh <python-script> [args...]`
- Full calibration CLI: `./run_full_calibration.sh [args...]`
- Direct full calibration: `.venv/bin/python logic/FullCalibration.py --node 50 --can-bitrate 125`
- SocketCAN bridge dry run: `.venv/bin/python systemd/start_can0.py --dry-run`
- Tests: `ST_NONINTERACTIVE=1 .venv/bin/python -m pytest`

## External Dependencies And Devices

Python packages used by code include `canopen`, `python-can`, `pyserial`,
`PyYAML`, `opencv-python`/`cv2`, `numpy`, `pandas`, `openpyxl`, `plotly`,
`matplotlib`, `pyvisa`, and `pytest`.

External hardware and services include:

- MiControl F35 controller over CANopen/SocketCAN.
- CAN serial adapter bridged with `slcand` to `can0`.
- Arduino Due or compatible relay/measurement board using the binary protocol in
  `driver_arduino.py`.
- iC-Haus MB5U/MU 3SL adapter and `libMU_3SL_interface.so.3.4.1`.
- Camera for QR reading and steering visual angle detection.
- Optional OWON SPE6053 power supply.
- External EOL-case project at
  `/home/mobotic/Internal Projects/EOL-case/02_EOL_files`.
- External traction-calibration project at
  `/home/mobotic/Internal Projects/TrCalibration-Linux`.

## Reuse Map To Avoid Repetition

Before adding a new implementation, reuse or extend:

- Product lookup: `resolve_product_scan_text()`,
  `find_product_family_folder_from_roots()`, `io_helpers/find_product_folder.py`.
- Status workbook IO: `read_conf_xlsx_rows()`, `write_conf_xlsx_rows()`,
  `normalize_conf_report_rows()`, `RunAllReport`.
- EOL gating: `eol_sequence_status_from_rows()` and
  `TestRunner.verify_configuration_processes_done()`.
- CAN setup and checks: `DriverCan`, `check_standard_then_product_can_connection()`,
  `_check_gui_can_with_st_can0_retry()`.
- MiControl SDO/controller behavior: `MicontrolF35_CAN`.
- Relay behavior: `DriverArduino`, `run_relay_action()`,
  `set_controller_power_relays()`, `restart_controller_with_relays()`.
- QR reading: `drivers/driver_QRreader.py`.
- Visual angle detection: `AngleDetection` in `drivers/driver_cam_st.py`.
- MU calibration: `logic/FullCalibration.py`.
- Zero write and EEPROM verification: `logic/FlashConfigZero.py`.
- Calibration quality rules and report text:
  `logic/calibration_quality.py`.
- Traction-calibration delegation: `choose_traction_calibration_program()`,
  `run_traction_calibration()`, `append_traction_calibration_log()`.

## Testing Strategy

Preferred automated tests isolate hardware:

- Stub `ctypes.CDLL` for MU library behavior.
- Replace driver modules in `sys.modules` when importing hardware-heavy modules.
- Use temporary files for workbooks, status reports, and visual scale cache.
- Test pure parsing/state helpers directly.
- Set `ST_NONINTERACTIVE=1` so error paths raise instead of waiting for input.

Hardware validation is still required for changes that touch actual CAN motion,
relay switching, encoder EEPROM writes, camera detection, power cycling, or EOL
equipment behavior. Specs should record those manual validation steps separately
from unit tests.

## Known Design Constraints

- Some hardware modules load config or vendor shared libraries at import time.
  Tests work around this with stubs; new code should avoid expanding import-time
  side effects.
- `main/CalibrationGUI.py` is intentionally central today. Small pure helpers
  may be extracted, but feature work should avoid unrelated restructuring.
- Product result folders and MU logs contain generated production artifacts.
  Specs should distinguish application code changes from generated data changes.
- Paths are currently local-machine oriented under `/home/mobotic`. New specs
  that change portability must explicitly preserve current production defaults.
