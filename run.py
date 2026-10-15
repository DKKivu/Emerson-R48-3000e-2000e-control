#!/usr/bin/env python3
"""Entry point for the R48 controller GUI.

This script performs a best-effort check for the pyserial dependency and
attempts to install it into the current interpreter if missing. This helps
users who double-click the app or run it with the wrong Python to get a
clearer experience. Installation is performed with `sys.executable -m pip`
and therefore affects only the interpreter being used to launch the app.

If installation fails the program still starts — the GUI has diagnostics
and will show a clear message. This behaviour is intended to be helpful
when the user runs the GUI from a different interpreter than the one used
when developing or installing requirements.
"""
from __future__ import annotations

import subprocess
import sys
import traceback


def _ensure_pyserial() -> None:
    """Ensure pyserial is importable in the current interpreter.

    If it is not, attempt to install it using pip. This is a best-effort
    convenience for users running the GUI directly from an environment
    that doesn't yet have pyserial installed.
    """
    try:
        import serial  # type: ignore
        return
    except Exception:
        print("pyserial not importable; attempting to install pyserial into:", sys.executable)

    try:
        cmd = [sys.executable, "-m", "pip", "install", "pyserial"]
        print(
            "Running:", " ".join(cmd),
            "(this may take a moment; install is best-effort)",
        )
        subprocess.run(cmd, check=True)
    except Exception:
        print("Automatic install failed:")
        traceback.print_exc()
        print("You can manually install pyserial for this interpreter with:")
        print(f"  {sys.executable} -m pip install pyserial")


# Try to make pyserial importable — we continue either way and let the
# GUI show diagnostics / error messages if it is still missing.
_ensure_pyserial()

# Now import and run the GUI
from r48.ui import R48Application  # noqa: E402 - import after attempt to install


def main() -> None:
    R48Application().mainloop()


if __name__ == "__main__":
    main()
