"""Gun Designer entry point.  Run with:  python main.py"""
from __future__ import annotations

import os
import sys

# Make package imports work no matter where the script is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.game import Game  # noqa: E402


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
