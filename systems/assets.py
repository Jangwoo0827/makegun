"""Optional image assets.

The game draws everything with shapes. If a PNG exists at
    assets/images/<category>/<name>.png
it is used instead. Template files with the right names and sizes live in
assets/placeholders/ (regenerate with `python tools/make_placeholders.py`):
copy one into assets/images/ and paint over it.
"""
from __future__ import annotations

import os

import pygame

import settings

IMAGES_DIR: str = os.path.join(settings.ASSETS_DIR, "images")

# category -> default draw size used when a caller doesn't pass one
CATEGORIES: dict[str, tuple[int, int]] = {
    "enemies": (48, 48),
    "player": (40, 40),
    "parts": (96, 48),
    "gun": (64, 32),
    "pickups": (32, 32),
    "tiles": (80, 80),
}


class AssetManager:
    def __init__(self, root: str = IMAGES_DIR) -> None:
        self.root = root
        self._raw: dict[tuple[str, str], pygame.Surface | None] = {}
        self._scaled: dict[tuple[str, str, int, int], pygame.Surface] = {}

    def path_for(self, category: str, name: str) -> str:
        return os.path.join(self.root, category, f"{name}.png")

    def _load(self, category: str, name: str) -> pygame.Surface | None:
        key = (category, name)
        if key not in self._raw:
            surf: pygame.Surface | None = None
            path = self.path_for(category, name)
            if os.path.exists(path):
                try:
                    surf = pygame.image.load(path)
                    if pygame.display.get_surface() is not None:
                        surf = surf.convert_alpha()
                except pygame.error:
                    surf = None
            self._raw[key] = surf
        return self._raw[key]

    def has(self, category: str, name: str) -> bool:
        return self._load(category, name) is not None

    def get(self, category: str, name: str, size: tuple[int, int] | None = None) -> pygame.Surface | None:
        """The image scaled to `size`, or None if the file doesn't exist."""
        raw = self._load(category, name)
        if raw is None:
            return None
        w, h = size or CATEGORIES.get(category, raw.get_size())
        key = (category, name, int(w), int(h))
        if key not in self._scaled:
            self._scaled[key] = pygame.transform.smoothscale(raw, (max(1, int(w)), max(1, int(h))))
        return self._scaled[key]

    def blit_centered(self, surface: pygame.Surface, category: str, name: str, center: tuple[float, float],
                      size: tuple[int, int] | None = None, angle_deg: float = 0.0) -> bool:
        """Draw the image centered (optionally rotated). Returns False if there is no image."""
        img = self.get(category, name, size)
        if img is None:
            return False
        if angle_deg:
            img = pygame.transform.rotate(img, angle_deg)
        surface.blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))
        return True

    def blit_part_icon(self, surface: pygame.Surface, part_id: str, center: tuple[float, float],
                       box: tuple[int, int] = (96, 48)) -> bool:
        """Part icon for menus: parts/<id>.png, else the in-game gun/<id>.png fitted into `box`."""
        if self.blit_centered(surface, "parts", part_id, center, box):
            return True
        raw = self._load("gun", part_id)
        if raw is None:
            return False
        rw, rh = raw.get_size()
        k = min(box[0] / rw, box[1] / rh)
        return self.blit_centered(surface, "gun", part_id, center, (int(rw * k), int(rh * k)))

    def clear_cache(self) -> None:
        self._raw.clear()
        self._scaled.clear()


#: shared instance; images are a pure presentation concern so entities may draw through it
ASSETS = AssetManager()


def enemy_sprite_size(radius: float) -> tuple[int, int]:
    s = int(radius * 2.4)
    return (s, s)
