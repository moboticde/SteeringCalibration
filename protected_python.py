from __future__ import annotations

import runpy
import sys
from pathlib import Path

from interrupt_guard import install_deferred_keyboard_interrupt


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: python3 -S protected_python.py SCRIPT.py [args...]")
        return 2

    script_path = Path(args[0]).resolve()
    script_args = args[1:]
    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_path}")
        return 2

    restore_sigint = install_deferred_keyboard_interrupt(label=script_path.name)
    try:
        import site  # noqa: F401

        sys.argv = [str(script_path), *script_args]
        sys.path.insert(0, str(script_path.parent))
        runpy.run_path(str(script_path), run_name="__main__")
        return 0
    finally:
        restore_sigint()


if __name__ == "__main__":
    raise SystemExit(main())
