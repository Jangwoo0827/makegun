"""Build the browser (WebAssembly) version with pygbag.

    pip install pygbag
    python tools/build_web.py

Output: dist/gundesigner_web.zip (the same files CI publishes to GitHub Pages,
https://jangwoo0827.github.io/makegun/). Works on desktop and mobile browsers.
Use `python tools/build_web.py --serve` to also test it locally at http://localhost:8000
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "build", "web_stage", "gundesigner")
OUT_ZIP = os.path.join(ROOT, "dist", "gundesigner_web")

# Only what the game loads at runtime (no exe, placeholders, source art, tests).
INCLUDE_FILES = ["main.py", "settings.py"]
INCLUDE_DIRS = ["game", "entities", "weapons", "systems", "ui", "data",
                os.path.join("assets", "images"), os.path.join("assets", "sounds"),
                os.path.join("assets", "music")]


def stage_files() -> None:
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    for f in INCLUDE_FILES:
        shutil.copy2(os.path.join(ROOT, f), STAGE)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".gitkeep")
    for d in INCLUDE_DIRS:
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(STAGE, d), ignore=ignore)


def main() -> int:
    serve = "--serve" in sys.argv
    try:
        import pygbag  # noqa: F401
    except ImportError:
        print("pygbag is not installed. Run:  pip install pygbag")
        return 1
    stage_files()
    args = [sys.executable, "-m", "pygbag", "--title", "Gun Designer"]
    if not serve:
        args.append("--build")
    args.append(STAGE)
    print(" ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode
    web_dir = os.path.join(STAGE, "build", "web")
    os.makedirs(os.path.dirname(OUT_ZIP), exist_ok=True)
    archive = shutil.make_archive(OUT_ZIP, "zip", web_dir)
    print("\nBuilt:", archive, "\nPushing to main publishes it to GitHub Pages automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
