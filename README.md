# Emerson / Vertiv R48 Controller

Windows GUI for Emerson/Vertiv R48 rectifiers via a Waveshare USB-CAN-A adapter.

Protocol references:
- https://github.com/PurpleAlien/R48_Rectifier
- https://github.com/anikrooz/Emerson-Vertiv-R48

## Features
- Live telemetry: voltage, current, power, current limit, temperature, input voltage.
- Set voltage / current setpoints:
  - Online (temporary): takes effect immediately but is not written to non-volatile memory.
  - Permanent (offline / written to device memory): stores the value in the rectifier memory.
  - Important: when configuring a permanent/offline value, set the online value first, verify the result, and then write the permanent value. The permanent value is written to device memory.
- Online setpoints are re-sent every 10 s while Hold is ticked.
- Fan control: discrete modes only — Auto or Full speed.
- Locate LED flash.
- Multi-PSU support via target-address substitution (byte 1 of the CAN ID).
- Property scan and raw CAN frame sender for diagnostics.

## Quick start

1. Create a virtual environment and install runtime dependencies:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix/macOS
# source .venv/bin/activate
python -m pip install -r requirements.txt
```

2. Run the GUI:
```bash
python run.py
```

## Build (Windows one-file EXE)

1. Install dev requirements (including PyInstaller):
```bash
python -m pip install -r requirements-dev.txt
```

2. Build the one-file windowed EXE:
```bash
python build_exe.py --clean
```

Output:
```text
dist/R48Controller.exe
```

## Configuration defaults
- Default serial port: configured in `r48/config.yaml` (leave empty to auto-select the first detected adapter)
- Serial baud: 2,000,000 (default)
- CAN bitrate: 125,000

These defaults are defined in `r48/config.yaml` and loaded by `r48/config.py`. Edit `r48/config.yaml` to change defaults.

## Programmatic usage

Example using the transport and controller classes:
```python
from r48.transport import WaveshareSerialCAN
from r48.controller import R48Controller
from r48.models import CANFrame

transport = WaveshareSerialCAN(port="COM3", baud=2_000_000, bitrate=125_000)
ctrl = R48Controller(transport)

ctrl.connect()
ctrl.set_target_address(0x01)
ctrl.request_telemetry()

# Online (temporary) voltage
ctrl.set_voltage(48.5, permanent=False)

# Permanent value: recommended to set online first, then write to memory
ctrl.set_voltage(48.0, permanent=True)

# Current
ctrl.set_current(10.0, permanent=False)

# Fan control: Auto = False, Full = True
ctrl.send_control(fan_full=True, flash_led=False)

# Raw CAN frame example
frame = CANFrame(arbitration_id=0x0607FF83, data=bytes.fromhex("03 F0 00 21 00 00 00 00"))
ctrl.send_raw(frame)

ctrl.disconnect()
```

## Operational notes

- When setting a permanent/offline value, first set the online value, then set the offline value. The offline write stores the setting in device memory.
- Fan control is discrete: Auto or Full. There is no continuous fan-speed control in this implementation.
- The protocol supports multiple PSU addressing by substituting the target address into the CAN ID.
- Use the exact CAN bitrate and adapter port that match the hardware on the bench.

## Troubleshooting

- Adapter not detected:
  - Click the "Refresh" button next to the COM port selector in the UI.
  - On Linux/macOS common device names are `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/tty.usbserial-*`, etc.
  - Ensure the Waveshare adapter is connected and OS drivers for the USB serial bridge are installed.

- Wrong CAN bitrate / no data:
  - Ensure the CAN bitrate in the UI matches the adapter and the CAN bus (common values: 125000, 250000, 500000). Mismatched bitrates prevent frame decoding.

- Missing PySerial or PyYAML:
  - Install dependencies: `python -m pip install -r requirements.txt`
  - If pyserial is missing the app will raise a `TransportError` when trying to connect. PyYAML is required for config persistence.

- Permanent writes seem to have no effect:
  - Set the online value first and verify, then use the "permanent" option to write to device memory.
  - Test on a single unit before applying permanent writes widely — some rectifier firmware requires specific sequences.

## Project structure
```
README.md
requirements.txt
run.py
build_exe.py
r48/
  __init__.py
  config.py
  config.yaml
  settings.py
  controller.py
  exceptions.py
  models.py
  protocol.py
  transport.py
  ui/
    __init__.py
    dialogs.py
    main_window.py
```

## Internals

- `r48/controller.py` — application facade. This is the main API for the rest of the app.
- `r48/protocol.py` — CAN protocol encoding/decoding for the R48 and the Waveshare adapter framing.
- `r48/transport.py` — serial transport layer that communicates with the USB-CAN adapter and emits events for the UI.
- `r48/models.py` — shared immutable data classes (`CANFrame`, `TelemetryValue`).
- `r48/config.py` & `r48/config.yaml` — app settings and defaults.
- `r48/settings.py` — persistent user settings (last used port/target).
- `r48/ui/main_window.py` and `r48/ui/dialogs.py` — Tkinter GUI implementation.

## License
This project is open-sourced under the MIT License. See `LICENSE` for the full text.

## References and attribution
This implementation was developed with reference to the following public projects and resources. Please check those repositories for their own licenses and attribution requirements before copying or redistributing code from them directly.

- PurpleAlien/R48_Rectifier — https://github.com/PurpleAlien/R48_Rectifier
- anikrooz/Emerson-Vertiv-R48 — https://github.com/anikrooz/Emerson-Vertiv-R48
