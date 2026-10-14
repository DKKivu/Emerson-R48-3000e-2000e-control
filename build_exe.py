#!/usr/bin/env python3
"""Build a Windows executable for the R48 Controller.

Usage:
    python build_exe.py                # one-file windowed build
    python build_exe.py --onedir       # folder build
    python build_exe.py --console      # keep console window (for debugging)
    python build_exe.py --clean        # wipe build/ and dist/ first
    python build_exe.py --icon app.ico # embed an icon

The script installs PyInstaller if it is missing, then invokes it with
the correct flags. It is safe to run repeatedly.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "build.spec"
ENTRY = PROJECT_ROOT / "run.py"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found; installing…")
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.6"])


def wipe_outputs() -> None:
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            print(f"Removing {path}")
            shutil.rmtree(path)


def write_minimal_spec(onedir: bool, console: bool, icon: str | None) -> None:
    """Write a spec if the user did not provide one."""
    if SPEC_FILE.exists():
        return
    print(f"{SPEC_FILE.name} not found — writing a minimal one.")
    one_file = not onedir
    icon_line = f'icon={icon!r},' if icon else 'icon=None,'
    console_line = f'console={console},'
    spec = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
project_root = Path(SPECPATH).resolve()

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "README.md"), ".")] if (project_root / "README.md").exists() else [],
    hiddenimports=[
        "serial", "serial.tools", "serial.tools.list_ports",
        "serial.tools.list_ports_windows", "serial.tools.list_ports_linux",
        "serial.tools.list_ports_common",
        "r48", "r48.ui", "r48.ui.main_window", "r48.ui.dialogs",
    ],
    excludes=["numpy", "pandas", "matplotlib", "scipy",
              "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts,
    {"" if one_file else "[] ,"}
    {"" if one_file else ""}
    a.binaries if {one_file} else [],
    a.zipfiles if {one_file} else [],
    a.datas if {one_file} else [],
    [],
    name="R48Controller",
    debug=False,
    strip=False,
    upx=True,
    {console_line}
    {icon_line}
    {'exclude_binaries=False,' if one_file else 'exclude_binaries=True,'}
)

{'coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="R48Controller")' if onedir else ''}
'''
    SPEC_FILE.write_text(spec, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the R48 Controller EXE.")
    parser.add_argument("--onedir", action="store_true",
                        help="Build a folder instead of a single .exe")
    parser.add_argument("--console", action="store_true",
                        help="Keep a console window (useful for debugging)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove build/ and dist/ before building")
    parser.add_argument("--icon", default=None,
                        help="Path to a .ico file to embed")
    args = parser.parse_args()

    if not ENTRY.exists():
        sys.exit(f"Cannot find {ENTRY}. Run this script from the project root.")

    ensure_pyinstaller()

    if args.clean:
        wipe_outputs()

    write_minimal_spec(onedir=args.onedir, console=args.console, icon=args.icon)

    # If the user provided a spec, honour --console/--icon only when the spec
    # was auto-generated. Otherwise let the spec drive.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        str(SPEC_FILE),
    ]
    run(cmd)

    if args.onedir:
        out = DIST_DIR / "R48Controller" / "R48Controller.exe"
    else:
        out = DIST_DIR / "R48Controller.exe"

    print()
    if out.exists():
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"Build succeeded: {out}  ({size_mb:.1f} MB)")
    else:
        print(f"Build finished but {out} was not found — check the PyInstaller log.")


if __name__ == "__main__":
    main()