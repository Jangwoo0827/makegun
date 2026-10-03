"""Build a standalone Windows executable with PyInstaller.

    pip install pyinstaller
    python tools/build_exe.py

Output: dist/GunDesigner.exe  (single file; saves/profile are written next to it).
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if os.name == "nt" else ":"

# Only ship what the game reads at runtime (placeholders / source art stay out).
DATA_DIRS = ["data", os.path.join("assets", "images"), os.path.join("assets", "sounds"),
             os.path.join("assets", "music")]


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run:  pip install pyinstaller")
        return 1
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "GunDesigner"]
    for d in DATA_DIRS:
        if os.path.isdir(os.path.join(ROOT, d)):
            args += ["--add-data", f"{d}{SEP}{d}"]
    args.append("main.py")
    print(" ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode == 0:
        print("\nBuilt:", os.path.join(ROOT, "dist", "GunDesigner.exe"))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
