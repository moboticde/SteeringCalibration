# utils.py
import itertools
import os
import select
import sys
import time
import threading

if os.name == "nt":
    import msvcrt
else:
    msvcrt = None

_active_spinner = None

class UserExit(SystemExit):
    """Raised when the operator chooses to abort the test."""


def flush_input_buffer(repeat=3):
    """Flush the keyboard buffer to remove unwanted inputs like from barcode scanners."""
    for _ in range(repeat):
        while _keyboard_hit():
            _read_key()
        time.sleep(0.01)  # slight delay to catch trailing input

def error_prompt(message):
    """Display an error and wait for [e] to exit, ignoring buffer overflow from barcode scanner."""
    global _active_spinner

    # --- NEW: stop any active spinner so the prompt is visible ---
    if _active_spinner is not None:
        try:
            _active_spinner.stop()
        except Exception:
            pass
        _active_spinner = None
    # -------------------------------------------------------------

    print(f"\n\n  Error: {message}")
    if os.getenv("ST_NONINTERACTIVE"):
        raise RuntimeError(str(message))

    flush_input_buffer()

    print("\n\nPress [e] to exit: ", end="", flush=True)

    while True:
        if not sys.stdin.isatty():
            raise UserExit("Program closed after error in non-interactive mode.")
        if _keyboard_hit():
            key = _read_key().lower()
            if key == 'e':
                print("exit")
                raise UserExit("Program closed by user.")
        time.sleep(0.05)


def _keyboard_hit() -> bool:
    if msvcrt is not None:
        return bool(msvcrt.kbhit())
    if not sys.stdin.isatty():
        return False
    readable, _writable, _error = select.select([sys.stdin], [], [], 0)
    return bool(readable)


def _read_key() -> str:
    if msvcrt is not None:
        return msvcrt.getch().decode("utf-8", errors="ignore")
    return sys.stdin.read(1)

def safe_execute(func, *args, spinner_text=None, **kwargs):
    global _active_spinner
    spinner = None
    if spinner_text:
        spinner = Spinner(spinner_text)
        _active_spinner = spinner          # remember it as active
        spinner.start()
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        print("\n")  # Ensure error starts on clean line
        if os.getenv("ST_NONINTERACTIVE"):
            raise
        error_prompt(str(e))
        return None
    finally:
        if spinner:
            try:
                spinner.stop()
            finally:
                # clear global if this was the active spinner
                if _active_spinner is spinner:
                    _active_spinner = None




class Spinner:
    def __init__(self, text="Loading...", quiet_when_captured=True):
        self.spinner = itertools.cycle(['|', '/', '-', '\\'])
        self.running = False
        self.thread = None
        self.text = text
        self.quiet_when_captured = quiet_when_captured
        self._animated = False

    def start(self):
        if self.quiet_when_captured and not sys.stdout.isatty():
            print(f"[STATUS] {self.text}")
            return
        self.running = True
        self._animated = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def _spin(self):
        while self.running:
            print(f"\r{self.text} {next(self.spinner)}", end="", flush=True)
            time.sleep(0.1)

    def stop(self):
        if not self._animated:
            return
        self.running = False
        if self.thread:
            self.thread.join()
        print("\r" + " " * (len(self.text) + 4) + "\r", end="", flush=True)
