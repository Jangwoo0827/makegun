"""Camera that follows a target inside the arena, with screen shake."""
from __future__ import annotations

import random

import pygame

import settings


class Camera:
    def __init__(self, view_w: int = settings.SCREEN_WIDTH, view_h: int = settings.SCREEN_HEIGHT) -> None:
        self.view_w: int = view_w
        self.view_h: int = view_h
        self.pos: pygame.Vector2 = pygame.Vector2()
        self.shake_strength: float = 0.0
        self.shake_enabled: bool = True
        self._shake_offset: pygame.Vector2 = pygame.Vector2()

    @property
    def offset(self) -> pygame.Vector2:
        return self.pos + self._shake_offset

    def shake(self, amount: float) -> None:
        if self.shake_enabled:
            self.shake_strength = min(24.0, max(self.shake_strength, amount))

    def snap_to(self, target: pygame.Vector2) -> None:
        self.pos = self._clamped(target)

    def _clamped(self, target: pygame.Vector2) -> pygame.Vector2:
        x = max(0.0, min(settings.ARENA_WIDTH - self.view_w, target.x - self.view_w / 2))
        y = max(0.0, min(settings.ARENA_HEIGHT - self.view_h, target.y - self.view_h / 2))
        return pygame.Vector2(x, y)

    def update(self, dt: float, target: pygame.Vector2, look: pygame.Vector2 | None = None) -> None:
        aim = target + (look * 0.18 if look is not None else pygame.Vector2())
        desired = self._clamped(aim)
        self.pos += (desired - self.pos) * min(1.0, 10.0 * dt)
        if self.shake_strength > 0.1:
            s = self.shake_strength
            self._shake_offset.update(random.uniform(-s, s), random.uniform(-s, s))
            self.shake_strength *= max(0.0, 1.0 - 9.0 * dt)
        else:
            self.shake_strength = 0.0
            self._shake_offset.update(0, 0)

    def screen_to_world(self, screen_pos: tuple[int, int]) -> pygame.Vector2:
        return pygame.Vector2(screen_pos) + self.offset
