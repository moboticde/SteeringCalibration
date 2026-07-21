# Agent Instructions

Before changing this repository, read:

- `.specify/memory/constitution.md`
- `.specify/memory/project-overview.md`

This is a production hardware-calibration project. Keep changes scoped to the
module that already owns the behavior. Do not add parallel implementations of
CAN, MiControl SDO access, Arduino relay protocol, MU SDK access, camera angle
detection, QR scanning, product lookup, status workbook IO, or EOL sequence
checking.

Treat these areas as generated, vendor, or production data unless the task
explicitly targets them:

- `MU/MU_3SL_interface_3.4.1/`
- `MU/config_backups/`
- `MU/calib_logs/`
- `S-1000-200/*/04_Results/`
- `.venv/`, `.cache/`, `.pytest_cache/`, `__pycache__/`

For tests, prefer hardware-free coverage with stubs/fakes and run noninteractive
paths with:

```bash
ST_NONINTERACTIVE=1 .venv/bin/python -m pytest
```

If a change can move hardware, write EEPROM/controller parameters, switch relays,
or alter EOL eligibility, document the failure mode and manual validation steps in
the spec or plan.
