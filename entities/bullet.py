"""Projectiles fired by the player and enemies."""
from __future__ import annotations

import pygame

Color = tuple[int, int, int]


class Bullet:
    def __init__(
        self,
        pos: pygame.Vector2,
        velocity: pygame.Vector2,
        damage: float,
        lifetime: float,
        *,
        from_player: bool = True,
        pierce: int = 0,
        explosion_radius: float = 0.0,
        ammo_type: str = "normal",
        radius: float = 4.0,
        color: Color = (255, 230, 120),
        crit_chance: float = 0.0,
        crit_damage: float = 1.5,
        knockback: float = 0.0,
        burn: float = 0.0,
        split: int = 0,
        ricochet: int = 0,
        chain: int = 0,
        lifesteal: float = 0.0,
        is_fragment: bool = False,
        slow: float = 0.0,
        homing: float = 0.0,
    ) -> None:
        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.prev_pos: pygame.Vector2 = pygame.Vector2(pos)
        self.velocity: pygame.Vector2 = pygame.Vector2(velocity)
        self.damage: float = damage
        self.lifetime: float = lifetime
        self.from_player: bool = from_player
        self.pierce: int = pierce
        self.explosion_radius: float = explosion_radius
        self.ammo_type: str = ammo_type
        self.radius: float = radius
        self.color: Color = color
        self.crit_chance: float = crit_chance
        self.crit_damage: float = crit_damage
        self.knockback: float = knockback
        self.burn: float = burn
        self.split: int = split
        self.ricochet: int = ricochet
        self.chain: int = chain
        self.lifesteal: float = lifesteal
        self.is_fragment: bool = is_fragment
        self.slow: float = slow
        self.homing: float = homing
        self.hit_ids: set[int] = set()
        self.alive: bool = True
        self._first_frame: bool = True

    @property
    def x(self) -> float:
        return self.pos.x

    @property
    def y(self) -> float:
        return self.pos.y

    def update(self, dt: float) -> None:
        if not self._first_frame:
            self.prev_pos.update(self.pos)
        self._first_frame = False
        self.pos += self.velocity * dt
        self.lifetime -= dt
        if self.lifetime <= 0.0:
            self.alive = False

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        tail = self.prev_pos - offset
        if self.velocity.length_squared() > 0:
            tail = p - self.velocity.normalize() * max(6.0, self.radius * 3)
        pygame.draw.line(surface, self.color, tail, p, max(2, int(self.radius)))
        pygame.draw.circle(surface, (255, 255, 255) if self.from_player else self.color, p, self.radius * 0.8)
