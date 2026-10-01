"""Generate labeled placeholder PNGs for every image the game can use.

    python tools/make_placeholders.py

Writes templates to assets/placeholders/<category>/<name>.png at the size the game draws them.
The game does NOT load these. To add real art, copy a template into
assets/images/<category>/ (same file name), then paint over it.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import settings  # noqa: E402
from entities.pickup import PickupKind  # noqa: E402
from systems.assets import enemy_sprite_size  # noqa: E402
from weapons.gun_renderer import GUN_IMAGE_SCALE, RECEIVER_IMAGE_HEIGHT  # noqa: E402

OUT_DIR = os.path.join(settings.ASSETS_DIR, "placeholders")
IMAGES_DIR = os.path.join(settings.ASSETS_DIR, "images")

Color = tuple[int, int, int]


def make(path: str, size: tuple[int, int], label: str, color: Color, facing_arrow: bool = False) -> None:
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cell = max(4, min(w, h) // 6)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            dark = (x // cell + y // cell) % 2 == 0
            c = tuple(int(v * (0.55 if dark else 0.8)) for v in color)
            pygame.draw.rect(surf, (*c, 255), (x, y, cell, cell))
    pygame.draw.rect(surf, (255, 0, 255, 255), surf.get_rect(), max(1, min(w, h) // 24))
    if facing_arrow:  # sprite should face right (+x); the game rotates it to aim
        cy = h // 2
        pygame.draw.line(surf, (255, 255, 255, 255), (w // 2, cy), (w - 4, cy), 2)
        pygame.draw.polygon(surf, (255, 255, 255, 255), [(w - 3, cy), (w - 9, cy - 4), (w - 9, cy + 4)])
    font = pygame.font.SysFont("consolas,dejavusansmono,monospace", max(8, min(14, w // max(1, len(label)) + 4)),
                               bold=True)
    for i, line in enumerate(label.split("\n")):
        img = font.render(line, True, (255, 255, 255))
        rect = img.get_rect(center=(w // 2, h // 2 + (i - 0.5) * img.get_height() if "\n" in label else h // 2))
        bg = rect.inflate(4, 2)
        pygame.draw.rect(surf, (0, 0, 0, 170), bg)
        surf.blit(img, rect)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(surf, path)


def main() -> None:
    pygame.init()
    count = 0
    manifest: dict[str, dict[str, list[int]]] = {}

    def add(category: str, name: str, size: tuple[int, int], label: str, color: Color, arrow: bool = False) -> None:
        nonlocal count
        make(os.path.join(OUT_DIR, category, f"{name}.png"), size, label, color, arrow)
        manifest.setdefault(category, {})[name] = [size[0], size[1]]
        count += 1

    with open(os.path.join(settings.DATA_DIR, "enemies.json"), encoding="utf-8") as f:
        enemies = json.load(f)
    for key, d in enemies.items():
        add("enemies", key, enemy_sprite_size(float(d["radius"])), key, tuple(d["color"]), True)  # type: ignore[arg-type]

    add("player", "player", (int(settings.PLAYER_RADIUS * 2.5),) * 2, "you", settings.PLAYER_COLOR, True)  # type: ignore[arg-type]

    with open(os.path.join(settings.DATA_DIR, "weapons.json"), encoding="utf-8") as f:
        parts = json.load(f)
    for category, entries in parts.items():
        for pid, d in entries.items():
            add("parts", pid, (96, 48), f"{category}\n{d['name']}", settings.RARITY_COLORS[d["rarity"]])

    # In-game gun pieces (side view, muzzle to the right), authored at 8x slot size.
    S = GUN_IMAGE_SCALE
    for category in ("receiver", "barrel", "magazine"):
        for pid, d in parts[category].items():
            v = d["visual"]
            if category == "receiver":
                size = (int(v["length"] * S), round(v["height"] * RECEIVER_IMAGE_HEIGHT * S))
            elif category == "barrel":
                size = (int((v["length"] + 2) * S), int(v["width"] * S))
            else:
                size = (int(v["w"] * S), int(v["h"] * S))
            add("gun", pid, size, d["name"], settings.RARITY_COLORS[d["rarity"]], category != "magazine")

    for kind in PickupKind:
        add("pickups", kind.value, (32, 32), kind.value[:4], (200, 200, 200))

    add("tiles", "floor", (settings.GRID_SIZE, settings.GRID_SIZE), "floor", settings.GRID_COLOR)
    add("tiles", "wall", (settings.WALL_THICKNESS, settings.WALL_THICKNESS), "wall", settings.WALL_COLOR)

    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    for category in manifest:  # empty real-art folders, ready to fill
        os.makedirs(os.path.join(IMAGES_DIR, category), exist_ok=True)
        keep = os.path.join(IMAGES_DIR, category, ".gitkeep")
        if not os.path.exists(keep):
            open(keep, "w").close()
    print(f"wrote {count} placeholders to {OUT_DIR}")


if __name__ == "__main__":
    main()
