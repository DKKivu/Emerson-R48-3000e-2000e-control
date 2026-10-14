# Emerson / Vertiv R48 Controller

Windows GUI for Emerson/Vertiv R48 rectifiers via a Waveshare USB-CAN-A adapter.

Protocol references:
- https://github.com/PurpleAlien/R48_Rectifier
- https://github.com/anikrooz/Emerson-Vertiv-R48

## Features
- Live telemetry: voltage, current, power, current limit, temperature, input voltage.
- Set voltage / current limit online (temporary) or permanent.
- Online setpoints re-sent every 10 s while **Hold** is ticked.
- Fan Auto / Full speed, locate-LED flash.
- Multi-PSU support via target address substitution in byte 1 of every CAN ID.
- Property scan and raw CAN frame sender for diagnostics.

## Install
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run
```bash
python run.py
```

## Build

# 1. Install dependencies (including PyInstaller)
``` bash
python -m pip install -r requirements-dev.

```

# 2. Build the one-file windowed EXE
``` bash
python build_exe.py --clean
```
# Output:
#   dist/R48Controller.exe