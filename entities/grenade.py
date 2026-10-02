"""Thrown grenade (active skill). Flies to a target point, then explodes."""
from __future__ import annotations

import math

import pygame

import settings


class Grenade:
    def __init__(self, start: pygame.Vector2, target: pygame.Vector2, damage: float, radius: float) -> None:
        self.start: pygame.Vector2 = pygame.Vector2(start)
        offset = target - start
        if offset.length() > settings.GRENADE_RANGE:
            offset.scale_to_length(settings.GRENADE_RANGE)
        self.target: pygame.Vector2 = start + offset
        self.pos: pygame.Vector2 = pygame.Vector2(start)
        self.damage: float = damage
        self.radius: float = radius
        self.fuse: float = settings.GRENADE_FUSE
        self.age: float = 0.0
        self.exploded: bool = False

    @property
    def progress(self) -> float:
        return min(1.0, self.age / self.fuse)

    def update(self, dt: float) -> None:
        self.age += dt
        self.pos = self.start.lerp(self.target, self.progress)
        if self.age >= self.fuse:
            self.exploded = True

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        t = self.progress
        lift = math.sin(t * math.pi) * 40  # fake arc height
        p = self.pos - offset
        pygame.draw.circle(surface, (255, 80, 60), self.target - offset, self.radius * (0.4 + 0.6 * t), 1)
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(2, 3), 6)
        body = p - pygame.Vector2(0, lift)
        pygame.draw.circle(surface, (90, 110, 70), body, 7)
        pygame.draw.circle(surface, (255, 220, 120) if int(self.age * 12) % 2 else (255, 80, 60), body, 3)
