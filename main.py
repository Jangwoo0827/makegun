"""Gun Designer entry point.  Run with:  python main.py

The main loop is async so the same file also runs in the browser via pygbag (itch.io web build).
"""
from __future__ import annotations

import asyncio
import os
import sys

import pygame  # noqa: F401  # pygbag scans main.py imports to decide which wasm packages to load

# Make package imports work no matter where the script is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.game import Game  # noqa: E402


async def main() -> None:
    await Game().run()


if __name__ == "__main__":
    asyncio.run(main())
