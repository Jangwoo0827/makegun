"""Items dropped by enemies."""
from __future__ import annotations

import math
from enum import Enum

import pygame

from systems.assets import ASSETS
from ui.fonts import get_font

PICKUP_LIFETIME: float = 20.0
MAGNET_SPEED: float = 520.0


class PickupKind(str, Enum):
    MONEY = "money"
    HEALTH = "health"
    AMMO = "ammo"
    BUFF = "buff"
    PART = "part"


PICKUP_COLORS: dict[PickupKind, tuple[int, int, int]] = {
    PickupKind.MONEY: (255, 214, 90),
    PickupKind.HEALTH: (90, 240, 120),
    PickupKind.AMMO: (120, 200, 255),
    PickupKind.BUFF: (255, 120, 255),
    PickupKind.PART: (255, 170, 40),
}


class Pickup:
    def __init__(self, kind: PickupKind, pos: pygame.Vector2, value: float = 0.0,
                 part_id: str | None = None, buff: str | None = None) -> None:
        self.kind: PickupKind = kind
        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.value: float = value
        self.part_id: str | None = part_id
        self.buff: str | None = buff
        self.radius: float = 7.0 if kind == PickupKind.MONEY else 10.0
        self.lifetime: float = PICKUP_LIFETIME * (3 if kind == PickupKind.PART else 1)
        self.age: float = 0.0
        self.alive: bool = True

    def update(self, dt: float, player_pos: pygame.Vector2, magnet_radius: float) -> None:
        self.age += dt
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return
        to_player = player_pos - self.pos
        dist = to_player.length()
        if 0 < dist < magnet_radius:
            speed = MAGNET_SPEED * (1.2 - dist / magnet_radius)
            self.pos += to_player / dist * speed * dt

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        if self.lifetime < 3.0 and int(self.lifetime * 8) % 2 == 0:
            return
        p = self.pos - offset
        p.y += math.sin(self.age * 5) * 2
        color = PICKUP_COLORS[self.kind]
        if ASSETS.blit_centered(surface, "pickups", self.kind.value, p, (32, 32)):
            return
        if self.kind == PickupKind.MONEY:
            pygame.draw.circle(surface, color, p, self.radius)
            pygame.draw.circle(surface, (150, 110, 20), p, self.radius, 2)
        elif self.kind == PickupKind.HEALTH:
            r = self.radius
            pygame.draw.rect(surface, color, (p.x - r, p.y - r * 0.35, r * 2, r * 0.7))
            pygame.draw.rect(surface, color, (p.x - r * 0.35, p.y - r, r * 0.7, r * 2))
        elif self.kind == PickupKind.AMMO:
            rect = pygame.Rect(0, 0, 16, 12)
            rect.center = (int(p.x), int(p.y))
            pygame.draw.rect(surface, color, rect, border_radius=2)
            pygame.draw.rect(surface, (40, 80, 120), rect, 2, border_radius=2)
        elif self.kind == PickupKind.BUFF:
            pts = [(p.x, p.y - 11), (p.x + 9, p.y), (p.x, p.y + 11), (p.x - 9, p.y)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, (255, 255, 255), pts, 2)
        else:
            glow = 14 + math.sin(self.age * 6) * 3
            pygame.draw.circle(surface, (80, 50, 10), p, glow, 2)
            rect = pygame.Rect(0, 0, 18, 18)
            rect.center = (int(p.x), int(p.y))
            pygame.draw.rect(surface, color, rect, border_radius=3)
            label = get_font(12, bold=True).render("P", True, (40, 20, 0))
            surface.blit(label, label.get_rect(center=rect.center))
