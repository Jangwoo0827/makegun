"""Cached font access."""
from __future__ import annotations

import pygame

_cache: dict[tuple[int, bool], pygame.font.Font] = {}
_FONT_NAMES: str = "consolas,dejavusansmono,couriernew,monospace"


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    font = _cache.get(key)
    if font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            font = pygame.font.SysFont(_FONT_NAMES, size, bold=bold)
        except Exception:
            font = pygame.font.Font(None, int(size * 1.3))
        _cache[key] = font
    return font


def draw_text(surface: pygame.Surface, text: str, pos: tuple[float, float], size: int = 18,
              color: tuple[int, int, int] = (225, 230, 240), bold: bool = False,
              anchor: str = "topleft") -> pygame.Rect:
    img = get_font(size, bold).render(text, True, color)
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(img, rect)
    return rect
