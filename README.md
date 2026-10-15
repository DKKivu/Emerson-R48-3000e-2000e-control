# Emerson R48 Controller — GUI

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)
[![Build Status](https://img.shields.io/badge/build-manual-yellowgreen)](#) <!-- Replace with CI badge if added -->

Emerson / Vertiv R48 controller GUI — talk to rectifiers over a Waveshare USB-CAN-A USB↔CAN adapter.

This repo contains:
- r48/ — package implementing protocol, controller, GUI and transport
- run.py — application entry point
- build_exe.py, build.spec — PyInstaller helpers for Windows builds
- requirements.txt — runtime & dev dependencies

Quick links
- Usage: run locally or build a Windows executable
- Troubleshooting: pyserial / COM detection guidance
- Development: how to run, test and build

## Quickstart (development)

1. Create & activate a virtual environment (Windows example)
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Run the GUI from source (console mode recommended while developing)
```bash
.venv\Scripts\python run.py
```

If you prefer double-clicking, build a single-file Windows exe (see "Building a Windows exe").

## Quickstart (end user — Windows)
- If you have a packaged exe, run it. If the GUI shows no COM ports, open the Diagnostic log (Diagnostic log tab) and follow the Troubleshooting steps below.

## Configuration
Configuration is YAML-backed. Default application values are defined in `r48/config.py` and can be overridden by `r48/config.yaml`.

- `r48/config.yaml` (example)
```yaml
title: "Emerson / Vertiv R48 Controller"
width: 1120
height: 940

# Leave serial_port empty to auto-detect:
serial_port: ""         # "" == auto-detect; set "COM3" to force a default
serial_baud: 2000000
can_bitrate: 125000

poll_interval_ms: 1000
keepalive_ms: 10000
age_refresh_ms: 500
stale_after_s: 5.0
gui_interval_ms: 50
max_events_per_cycle: 200
max_log_lines: 1200
scan_spacing_ms: 90
```

Important: `serial_port: ""` means the app will auto-detect ports at runtime. If you want a default port shown at startup, set e.g. `serial_port: "COM3"`.

## How the app detects COM ports
- The GUI uses `pyserial`'s `serial.tools.list_ports.comports()` to enumerate ports.
- If `pyserial` is missing in the interpreter running the GUI, enumeration will fail and the COM combobox may be empty.
- The project includes a runtime diagnostics helper `r48._debug_import_info()` which prints:
  - `executable`, `cwd`, first sys.path entries, `has_pyserial`, and `pyserial_import_error` (if any).

Run this diagnostics from the same interpreter used to start the GUI:
```bash
.venv\Scripts\python -c "import json, r48; print(json.dumps(r48._debug_import_info(), indent=2))"
```

## Troubleshooting

1. pyserial missing (ModuleNotFoundError: No module named 'serial')
- Symptom: GUI shows blank COM combobox; r48 warns `pyserial import failed`.
- Fix:
  - Ensure you run the GUI with the same interpreter you installed pyserial into:
    ```bash
    .venv\Scripts\python -m pip install pyserial
    .venv\Scripts\python run.py
    ```
  - Or run the diagnostics command above to confirm `sys.executable`.

2. Interpreter / venv mismatch
- Symptom: `pip show pyserial` reports installed, but GUI still reports missing.
- Fix:
  - Confirm the Python used to start the GUI: `r48._debug_import_info()` output shows `executable`.
  - Start the GUI explicitly with that interpreter: `.venv\Scripts\python run.py`

3. Shadowing (a local `serial.py`)
- Symptom: `import serial` finds a local module instead of the installed package.
- Fix:
  - Check for files named `serial.py` or a top-level `serial/` directory in your project root and rename/remove them.
  - Confirm: `.venv\Scripts\python -c "import importlib.util; print(importlib.util.find_spec('serial'))"`

4. PyInstaller packaging problems
- Symptom: Frozen exe doesn't list ports.
- Fix:
  - Build the exe using the provided spec or ensure `hiddenimports` include:
    ```
    serial
    serial.tools
    serial.tools.list_ports
    serial.tools.list_ports_windows
    serial.tools.list_ports_linux
    serial.tools.list_ports_common
    ```
  - Build from a venv that has `pyserial` installed.

5. OS-level COM not shown by list_ports
- On some systems (rare) OS may register ports that list_ports doesn't return. As a workaround you can:
  - Set `serial_port` in `r48/config.yaml` to a specific COM name (e.g., `"COM1"`) to preselect it, or
  - Use the GUI Refresh button to re-enumerate after plugging the adapter, or
  - Use the diagnostic output to confirm `list_ports.comports()` results:
    ```bash
    .venv\Scripts\python -c "from serial.tools import list_ports; print([p.device for p in list_ports.comports()])"
    ```

## Building a Windows executable

1. Build (one-file, windowed)
```bash
python build_exe.py
# or for debugging with a console:
python build_exe.py --console
```

2. If PyInstaller misses serial bits on target machines, rebuild with explicit hidden imports:
```bash
.venv\Scripts\python -m PyInstaller --clean --noconfirm build.spec
```

The included `build.spec` already lists common serial hidden imports. Test the exe on a clean Windows environment prior to distribution.

## Development & testing

- Linting / formatting (recommend):
  - ruff or flake8, black
- Type checking:
  - mypy (optional)
- Unit tests:
  - Add pytest tests for `r48/config.py` and for `r48.transport.list_serial_ports` (mock `serial.tools.list_ports`).

Proposed dev commands (example)
```bash
# run tests (once added)
.venv\Scripts\pytest -q

# run linter (if added)
.venv\Scripts\ruff check r48
```

## Project structure
```
.
├── build.spec
├── build_exe.py
├── README.md
├── requirements.txt
├── run.py
└── r48
    ├── __init__.py          # package + runtime diagnostics helper
    ├── config.py            # YAML-backed AppConfig, CONFIG instance
    ├── config.yaml          # optional overrides (example)
    ├── controller.py
    ├── exceptions.py
    ├── models.py
    ├── protocol.py
    ├── settings.py          # per-user settings (last port/target)
    ├── transport.py         # serial transport + list_serial_ports()
    └── ui
        ├── __init__.py
        ├── dialogs.py
        └── main_window.py   # Tkinter GUI
```

## Contributing
- Please open issues for bugs or feature requests.
- For code changes:
  - Use a topic branch, add tests, run linting, and create a PR with a clear description.
  - If history cleanliness is desired, prefer squashing on merge instead of a forced rewrite of `main`.

## Changelog
- Keep an up-to-date `CHANGELOG.md` (Unreleased section) for notable fixes and breaking changes.

## License
- MIT (or whatever license you actually have). Include a `LICENSE` file.  

---
