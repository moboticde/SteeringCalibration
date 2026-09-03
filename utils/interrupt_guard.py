from __future__ import annotations

import signal
import sys
import time
from types import FrameType
from typing import Callable


InterruptCallback = Callable[[int, FrameType | None], None]


def install_deferred_keyboard_interrupt(
    *,
    required_presses: int = 3,
    window_s: float = 3.0,
    on_interrupt: InterruptCallback | None = None,
    label: str = "program",
) -> Callable[[], None]:
    """
    Ignore accidental Ctrl+C presses until the user repeats them quickly.

    Returns a restore function that puts the previous SIGINT handler back.
    """
    if required_presses < 2:
        raise ValueError("required_presses must be at least 2")

    current_handler = signal.getsignal(signal.SIGINT)
    previous_handler = getattr(
        current_handler,
        "_deferred_keyboard_interrupt_previous",
        current_handler,
    )
    press_times: list[float] = []

    def restore() -> None:
        signal.signal(signal.SIGINT, previous_handler)

    def handle_sigint(signum: int, frame: FrameType | None) -> None:
        now = time.monotonic()
        press_times[:] = [t for t in press_times if now - t <= window_s]
        press_times.append(now)
        remaining = required_presses - len(press_times)

        if remaining > 0:
            noun = "time" if remaining == 1 else "times"
            print(
                f"\n[WARN] Ctrl+C ignored for {label}. "
                f"Press Ctrl+C {remaining} more {noun} within {window_s:.0f} seconds to interrupt.",
                flush=True,
            )
            return

        restore()
        print(f"\n[WARN] Ctrl+C confirmed. Interrupting {label}.", flush=True)
        if on_interrupt is not None:
            on_interrupt(signum, frame)
            return

        if callable(previous_handler):
            previous_handler(signum, frame)
        elif previous_handler == signal.SIG_IGN:
            return
        else:
            signal.default_int_handler(signum, frame)

    handle_sigint._deferred_keyboard_interrupt = True
    handle_sigint._deferred_keyboard_interrupt_previous = previous_handler

    if sys.platform != "win32" or signal.SIGINT is not None:
        signal.signal(signal.SIGINT, handle_sigint)

    return restore
