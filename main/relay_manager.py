from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


RELAY_MODE_AUTOMATIC = "automatic"
RELAY_MODE_MANUAL = "manual"
RELAY_MODES = {RELAY_MODE_AUTOMATIC, RELAY_MODE_MANUAL}
TASK_IDS_WITH_OPERATION_RELAYS = frozenset(
    {
        "run_all",
        "traction_calibration",
        "load_script_config",
        "load_script",
        "load_config",
        "start_calibration",
        "test_calibration",
        "start_zeroing",
    }
)


def parse_relay_mode(raw_value: object) -> str:
    value = str(raw_value or "").strip().lower()
    if value in RELAY_MODES:
        return value
    raise ValueError("Relay mode must be automatic or manual.")


def task_uses_operation_relays(task_id: str) -> bool:
    return task_id in TASK_IDS_WITH_OPERATION_RELAYS


def effective_relay_mode(task_id: str, configured_mode: str) -> str | None:
    if not task_uses_operation_relays(task_id):
        return None
    return parse_relay_mode(configured_mode)


@dataclass
class TaskRelayLifecycle:
    task_id: str
    task_label: str
    relay_mode: str
    activate_automatic: Callable[[str], object]
    deactivate_automatic: Callable[[str], None]
    wait_for_manual_step: Callable[[str, str], None]
    automatic_active: bool = False
    manual_started: bool = False

    def before_task(self) -> None:
        mode = effective_relay_mode(self.task_id, self.relay_mode)
        if mode is None:
            return
        if mode == RELAY_MODE_AUTOMATIC:
            self.activate_automatic(self.task_label)
            self.automatic_active = True
            return

        self.wait_for_manual_step("activate", self.task_label)
        self.manual_started = True

    def after_task(self) -> None:
        mode = effective_relay_mode(self.task_id, self.relay_mode)
        if mode is None:
            return
        if mode == RELAY_MODE_AUTOMATIC:
            if self.automatic_active:
                self.deactivate_automatic(self.task_label)
            return

        if self.manual_started:
            self.wait_for_manual_step("deactivate", self.task_label)
