"""Generate seamless floor + wall tiles for every stage/mode (original, procedural).

    python tools/make_tiles.py

Writes assets/images/tiles/<stage_id>_floor.png (160x160) and <stage_id>_wall.png (80x80), using each
stage's colors from data/stages.json + data/modes.json. Everything is drawn with wrap-around so tiles repeat
without seams. Replace any file with your own art of the same name.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

OUT = os.path.join(ROOT, "assets", "images", "tiles")
FS = 160  # floor tile size
WS = 80   # wall tile size
Color = tuple[int, int, int]

THEMES: dict[str, str] = {
    "outskirts": "asphalt", "foundry": "plates", "hive": "cells", "fortress": "bricks", "core": "circuit",
    "wasteland": "sand", "spire": "techgrid", "omega": "hexes", "endless": "stripes", "bossrush": "checker",
}


def shade(c: Color, k: float) -> Color:
    return tuple(max(0, min(255, int(v * k))) for v in c)  # type: ignore[return-value]


def lerp(a: Color, b: Color, t: float) -> Color:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


class Wrap:
    """Drawing helpers that wrap around the tile edges (seamless tiling)."""

    def __init__(self, surf: pygame.Surface) -> None:
        self.s = surf
        self.n = surf.get_width()

    def _offsets(self):
        for dx in (-self.n, 0, self.n):
            for dy in (-self.n, 0, self.n):
                yield dx, dy

    def line(self, color, a, b, width=1):
        for dx, dy in self._offsets():
            pygame.draw.line(self.s, color, (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), width)

    def circle(self, color, c, r, width=0):
        for dx, dy in self._offsets():
            pygame.draw.circle(self.s, color, (c[0] + dx, c[1] + dy), r, width)

    def rect(self, color, r, width=0, radius=0):
        for dx, dy in self._offsets():
            pygame.draw.rect(self.s, color, pygame.Rect(r).move(dx, dy), width, border_radius=radius)

    def poly(self, color, pts, width=0):
        for dx, dy in self._offsets():
            pygame.draw.polygon(self.s, color, [(x + dx, y + dy) for x, y in pts], width)


def speckle(w: Wrap, base: Color, rnd: random.Random, count: int, spread: float = 0.12, size: int = 1) -> None:
    for _ in range(count):
        k = 1.0 + rnd.uniform(-spread, spread)
        w.circle(shade(base, k), (rnd.uniform(0, w.n), rnd.uniform(0, w.n)), rnd.randint(1, size))


def hexagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(math.pi / 6 + i * math.pi / 3), cy + r * math.sin(math.pi / 6 + i * math.pi / 3))
            for i in range(6)]


def floor_tile(theme: str, floor: Color, grid: Color, accent: Color, seed: int) -> pygame.Surface:
    rnd = random.Random(seed)
    s = pygame.Surface((FS, FS))
    s.fill(floor)
    w = Wrap(s)
    if theme == "asphalt":
        speckle(w, floor, rnd, 900, 0.18)
        for _ in range(3):  # cracks
            x, y = rnd.uniform(0, FS), rnd.uniform(0, FS)
            a = rnd.uniform(0, math.tau)
            for _ in range(6):
                nx, ny = x + math.cos(a) * 12, y + math.sin(a) * 12
                w.line(shade(floor, 0.6), (x, y), (nx, ny), 1)
                x, y, a = nx, ny, a + rnd.uniform(-0.7, 0.7)
        w.line(grid, (0, 0), (FS, 0)); w.line(grid, (0, 0), (0, FS))
        w.line(shade(grid, 0.85), (FS / 2, 0), (FS / 2, FS)); w.line(shade(grid, 0.85), (0, FS / 2), (FS, FS / 2))
    elif theme == "plates":
        for px in (0, 80):
            for py in (0, 80):
                plate = pygame.Rect(px + 2, py + 2, 76, 76)
                w.rect(shade(floor, 1.0 + rnd.uniform(-0.06, 0.06)), plate)
                w.line(shade(floor, 1.35), plate.topleft, plate.topright, 2)
                w.line(shade(floor, 1.35), plate.topleft, plate.bottomleft, 2)
                w.line(shade(floor, 0.6), plate.bottomleft, plate.bottomright, 2)
                w.line(shade(floor, 0.6), plate.topright, plate.bottomright, 2)
                for cx, cy in ((plate.left + 7, plate.top + 7), (plate.right - 7, plate.top + 7),
                               (plate.left + 7, plate.bottom - 7), (plate.right - 7, plate.bottom - 7)):
                    w.circle(shade(floor, 1.5), (cx, cy), 2)
        for _ in range(5):  # rust
            w.circle(lerp(floor, accent, 0.35), (rnd.uniform(0, FS), rnd.uniform(0, FS)), rnd.randint(3, 8))
    elif theme == "cells":
        speckle(w, floor, rnd, 300, 0.1)
        r = 20
        hstep, vstep = r * math.sqrt(3), r * 1.5
        rows = round(FS / vstep)
        vstep = FS / rows
        cols = round(FS / hstep)
        hstep = FS / cols
        for row in range(rows):
            for col in range(cols):
                cx = col * hstep + (hstep / 2 if row % 2 else 0)
                cy = row * vstep
                w.poly(shade(floor, 1.0 + rnd.uniform(-0.05, 0.12)), hexagon(cx, cy, r - 2))
                w.poly(grid, hexagon(cx, cy, r - 2), 2)
        for _ in range(4):
            w.circle(lerp(floor, accent, 0.25), (rnd.uniform(0, FS), rnd.uniform(0, FS)), rnd.randint(4, 7))
    elif theme == "bricks":
        bh = 40
        for row in range(FS // bh):
            off = 40 if row % 2 else 0
            for col in range(-1, FS // 80 + 1):
                br = pygame.Rect(col * 80 + off + 2, row * bh + 2, 76, bh - 4)
                w.rect(shade(floor, 1.0 + rnd.uniform(-0.08, 0.1)), br, radius=3)
                w.line(shade(floor, 1.25), br.topleft, br.topright, 1)
        speckle(w, floor, rnd, 250, 0.15)
    elif theme == "circuit":
        speckle(w, floor, rnd, 150, 0.08)
        for _ in range(9):
            x, y = rnd.randrange(0, FS, 10), rnd.randrange(0, FS, 10)
            col = lerp(floor, lerp(grid, accent, 0.25), rnd.uniform(0.45, 0.7))  # keep traces subtle
            for _ in range(rnd.randint(2, 4)):
                if rnd.random() < 0.5:
                    nx, ny = x + rnd.choice((-1, 1)) * rnd.randrange(20, 60, 10), y
                else:
                    nx, ny = x, y + rnd.choice((-1, 1)) * rnd.randrange(20, 60, 10)
                w.line(col, (x, y), (nx, ny), 2)
                x, y = nx, ny
            w.circle(col, (x, y), 4); w.circle(floor, (x, y), 2)
    elif theme == "sand":
        speckle(w, floor, rnd, 1400, 0.14)
        for k in range(4):  # dune ripples
            y0 = k * 40 + rnd.uniform(0, 10)
            pts = [(x, y0 + math.sin(x / FS * math.tau * 2 + k) * 6) for x in range(0, FS + 1, 8)]
            for a, b in zip(pts, pts[1:]):
                w.line(shade(floor, 1.18), a, b, 2)
        for _ in range(8):
            w.circle(shade(floor, 0.7), (rnd.uniform(0, FS), rnd.uniform(0, FS)), rnd.randint(2, 4))
    elif theme == "techgrid":
        for i in range(0, FS, 20):
            w.line(shade(grid, 0.8), (i, 0), (i, FS)); w.line(shade(grid, 0.8), (0, i), (FS, i))
        for i in range(0, FS, 80):
            w.line(grid, (i, 0), (i, FS), 2); w.line(grid, (0, i), (FS, i), 2)
        for _ in range(6):
            x, y = rnd.randrange(0, FS, 20), rnd.randrange(0, FS, 20)
            w.circle(lerp(grid, accent, 0.7), (x, y), 2)
    elif theme == "hexes":
        r = 26
        hstep = FS / round(FS / (r * math.sqrt(3)))
        vstep = FS / round(FS / (r * 1.5))
        for row in range(round(FS / vstep)):
            for col in range(round(FS / hstep)):
                cx = col * hstep + (hstep / 2 if row % 2 else 0)
                cy = row * vstep
                w.poly(shade(floor, 1.0 + rnd.uniform(-0.04, 0.1)), hexagon(cx, cy, r - 1))
                w.poly(lerp(floor, grid, 0.7), hexagon(cx, cy, r - 1), 2)
        speckle(w, floor, rnd, 200, 0.1)
    elif theme == "stripes":
        for k in range(-FS, FS * 2, 32):
            w.line(shade(floor, 1.12), (k, 0), (k + FS, FS), 10)
        w.line(grid, (0, 0), (FS, 0)); w.line(grid, (0, 0), (0, FS))
    else:  # checker
        for px in (0, 80):
            for py in (0, 80):
                k = 1.08 if (px + py) % 160 == 0 else 0.92
                w.rect(shade(floor, k), (px, py, 80, 80))
        w.line(grid, (0, 0), (FS, 0)); w.line(grid, (0, 0), (0, FS))
        speckle(w, floor, rnd, 200, 0.08)
    return s


def wall_tile(theme: str, wall: Color, edge: Color, seed: int) -> pygame.Surface:
    rnd = random.Random(seed)
    s = pygame.Surface((WS, WS))
    s.fill(wall)
    w = Wrap(s)
    if theme in ("bricks", "asphalt", "sand"):
        for row in range(4):
            off = 20 if row % 2 else 0
            for col in range(-1, 3):
                br = pygame.Rect(col * 40 + off + 1, row * 20 + 1, 38, 18)
                w.rect(shade(wall, 1.0 + rnd.uniform(-0.1, 0.12)), br, radius=2)
                w.line(shade(wall, 1.3), br.topleft, br.topright)
    elif theme in ("plates", "checker", "stripes"):
        for px in (0, 40):
            for py in (0, 40):
                pr = pygame.Rect(px + 1, py + 1, 38, 38)
                w.rect(shade(wall, 1.0 + rnd.uniform(-0.05, 0.08)), pr)
                w.line(shade(wall, 1.4), pr.topleft, pr.topright, 2)
                w.line(shade(wall, 0.6), pr.bottomleft, pr.bottomright, 2)
                w.circle(shade(edge, 1.1), (pr.centerx, pr.centery), 2)
    else:  # cells / circuit / techgrid / hexes: tech panels
        for i in range(0, WS, 20):
            w.line(shade(wall, 0.8), (i, 0), (i, WS)); w.line(shade(wall, 0.8), (0, i), (WS, i))
        for _ in range(4):
            x, y = rnd.randrange(0, WS, 20), rnd.randrange(0, WS, 20)
            w.rect(shade(edge, 0.9), (x + 4, y + 4, 12, 12), radius=2)
    speckle(w, wall, rnd, 120, 0.1)
    return s


def main() -> int:
    pygame.init()
    os.makedirs(OUT, exist_ok=True)
    entries: list[dict] = []
    for name in ("stages.json", "modes.json"):
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
            entries += json.load(f)
    for i, st in enumerate(entries):
        sid = st["id"]
        theme = THEMES.get(sid, "checker")
        floor, grid = tuple(st["floor"]), tuple(st["grid"])
        wall, edge = tuple(st["wall"]), tuple(st["wall_edge"])
        pygame.image.save(floor_tile(theme, floor, grid, edge, 100 + i), os.path.join(OUT, f"{sid}_floor.png"))
        pygame.image.save(wall_tile(theme, wall, edge, 200 + i), os.path.join(OUT, f"{sid}_wall.png"))
        print(f"{sid:10} {theme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
