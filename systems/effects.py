"""Visual feedback: particles, damage numbers, explosions, lightning arcs."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from ui.fonts import get_font

Color = tuple[int, int, int]


@dataclass
class Particle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    life: float
    max_life: float
    color: Color
    size: float
    drag: float = 4.0


@dataclass
class DamageNumber:
    pos: pygame.Vector2
    text: str
    color: Color
    life: float
    size: int


@dataclass
class Ring:
    pos: pygame.Vector2
    radius: float
    life: float
    max_life: float
    color: Color


@dataclass
class Arc:
    points: list[pygame.Vector2]
    life: float


class EffectsManager:
    MAX_PARTICLES: int = 900

    def __init__(self) -> None:
        self.particles: list[Particle] = []
        self.numbers: list[DamageNumber] = []
        self.rings: list[Ring] = []
        self.arcs: list[Arc] = []
        self.show_numbers: bool = True

    def clear(self) -> None:
        self.particles.clear()
        self.numbers.clear()
        self.rings.clear()
        self.arcs.clear()

    # --------------------------------------------------------------- spawners
    def burst(self, pos: pygame.Vector2, color: Color, count: int = 8, speed: float = 180.0,
              life: float = 0.4, size: float = 3.0, direction: pygame.Vector2 | None = None,
              cone: float = math.pi) -> None:
        if len(self.particles) > self.MAX_PARTICLES:
            return
        base = math.atan2(direction.y, direction.x) if direction is not None and direction.length_squared() > 0 else 0.0
        spread = cone if direction is not None else math.pi
        for _ in range(count):
            a = base + random.uniform(-spread, spread)
            s = speed * random.uniform(0.3, 1.0)
            lf = life * random.uniform(0.6, 1.0)
            self.particles.append(Particle(pygame.Vector2(pos), pygame.Vector2(math.cos(a), math.sin(a)) * s,
                                           lf, lf, color, size * random.uniform(0.6, 1.2)))

    def damage_number(self, pos: pygame.Vector2, amount: float, crit: bool = False) -> None:
        if not self.show_numbers or amount < 0.5:
            return
        jitter = pygame.Vector2(random.uniform(-8, 8), random.uniform(-6, 2))
        text = f"{int(round(amount))}{'!' if crit else ''}"
        color = (255, 220, 60) if crit else (255, 255, 255)
        self.numbers.append(DamageNumber(pos + jitter, text, color, 0.7, 20 if crit else 15))

    def float_text(self, pos: pygame.Vector2, text: str, color: Color, size: int = 16) -> None:
        self.numbers.append(DamageNumber(pygame.Vector2(pos), text, color, 1.0, size))

    def explosion(self, pos: pygame.Vector2, radius: float) -> None:
        self.rings.append(Ring(pygame.Vector2(pos), radius, 0.3, 0.3, (255, 160, 60)))
        self.burst(pos, (255, 180, 70), 18, radius * 4, 0.45, 4)
        self.burst(pos, (255, 90, 40), 10, radius * 2.5, 0.6, 5)

    def arc(self, start: pygame.Vector2, end: pygame.Vector2) -> None:
        pts = [pygame.Vector2(start)]
        seg = 6
        d = end - start
        normal = pygame.Vector2(-d.y, d.x)
        if normal.length_squared() > 0:
            normal.scale_to_length(1)
        for i in range(1, seg):
            pts.append(start + d * (i / seg) + normal * random.uniform(-12, 12))
        pts.append(pygame.Vector2(end))
        self.arcs.append(Arc(pts, 0.15))

    # ----------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        for p in self.particles:
            p.pos += p.vel * dt
            p.vel *= max(0.0, 1.0 - p.drag * dt)
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for n in self.numbers:
            n.pos.y -= 40 * dt
            n.life -= dt
        self.numbers = [n for n in self.numbers if n.life > 0]
        for r in self.rings:
            r.life -= dt
        self.rings = [r for r in self.rings if r.life > 0]
        for a in self.arcs:
            a.life -= dt
        self.arcs = [a for a in self.arcs if a.life > 0]

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        for r in self.rings:
            t = 1.0 - r.life / r.max_life
            pygame.draw.circle(surface, r.color, r.pos - offset, max(2, r.radius * (0.4 + 0.6 * t)),
                               max(1, int(6 * (1 - t)) + 1))
        for p in self.particles:
            size = max(1.0, p.size * (p.life / p.max_life))
            pygame.draw.circle(surface, p.color, p.pos - offset, size)
        for a in self.arcs:
            pts = [p - offset for p in a.points]
            pygame.draw.lines(surface, (160, 190, 255), False, pts, 3)
            pygame.draw.lines(surface, (255, 255, 255), False, pts, 1)

    def draw_numbers(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        for n in self.numbers:
            img = get_font(n.size, bold=True).render(n.text, True, n.color)
            if n.life < 0.3:
                img.set_alpha(int(255 * n.life / 0.3))
            surface.blit(img, img.get_rect(center=(int(n.pos.x - offset.x), int(n.pos.y - offset.y))))
