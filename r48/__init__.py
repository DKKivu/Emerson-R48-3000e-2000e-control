"""Emerson / Vertiv R48 rectifier controller."""

__version__ = "2.0.0"

# Diagnostic helpers to assist when pyserial/import issues occur at runtime.
# The GUI can call r48._debug_import_info() to show which interpreter and
# sys.path the app is running under and whether pyserial was importable.

import sys
import os
import warnings

_HAS_PYSERIAL = None
_PYSERIAL_IMPORT_ERROR = None
try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
    _HAS_PYSERIAL = True
except Exception as _exc:  # pragma: no cover - defensive runtime diagnostics
    _HAS_PYSERIAL = False
    _PYSERIAL_IMPORT_ERROR = repr(_exc)
    # Emit a warning so it's visible when running from a console.
    warnings.warn(f"r48: pyserial import failed: {_PYSERIAL_IMPORT_ERROR}")


def _debug_import_info() -> dict:
    """Return a small dict with environment/import diagnostics.

    Useful to paste into issue reports or to display in a diagnostics
    dialog in the GUI. Keep the output concise so it is safe to call at
    application start.
    """
    return {
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "sys_path_first_entries": sys.path[:8],
        "has_pyserial": _HAS_PYSERIAL,
        "pyserial_import_error": _PYSERIAL_IMPORT_ERROR,
    }
