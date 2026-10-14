# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the R48 Controller.

Build with:
    pyinstaller --clean --noconfirm build.spec

Produces:
    dist/R48Controller.exe        (one-file, windowed)
    build/                        (intermediate, safe to delete)
"""

from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).resolve()

# ---- Analysis ---------------------------------------------------------
a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    # pyserial ships a small data tree (serial.tools.list_ports_windows etc.)
    # PyInstaller usually picks this up, but we make it explicit.
    datas=[
        (str(project_root / "README.md"), "."),
    ],
    hiddenimports=[
        "serial",
        "serial.tools",
        "serial.tools.list_ports",
        "serial.tools.list_ports_windows",
        "serial.tools.list_ports_linux",
        "serial.tools.list_ports_common",
        "r48",
        "r48.ui",
        "r48.ui.main_window",
        "r48.ui.dialogs",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim well-known unused bloat from the frozen image.
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "pytest",
        "setuptools",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---- Drop test suites and __pycache__ that may have been picked up ----
a.datas = [d for d in a.datas if "__pycache__" not in d[0]]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- One-file executable ----------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="R48Controller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # set to False if UPX is not installed
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # True for a debugging console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                   # e.g. str(project_root / "icon.ico")
)