"""Stage bosses added with the stage system: THE TITAN and THE WARDEN."""
from __future__ import annotations

import math
import random

import pygame

from entities.enemy import Boss, EnemyActions, EnemyData, WaveScaling

Color = tuple[int, int, int]


class Titan(Boss):
    """Charges across the arena, ending each charge in a shockwave. Stomps rings of slow shells."""

    WINDUP: float = 0.8
    CHARGE_TIME: float = 0.75
    CHARGE_SPEED: float = 5.0

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.windup: float = -1.0
        self.charging: float = 0.0
        self.charge_dir: pygame.Vector2 = pygame.Vector2(1, 0)
        self.combo: int = 0
        self.stomp_timer: float = 4.0

    def _ring(self, actions: EnemyActions, n: int, speed: float, dmg: float, radius: float, color: Color) -> None:
        off = random.uniform(0, math.tau)
        for i in range(n):
            self._shoot(actions, off + i * math.tau / n, speed, dmg, radius, color)

    def _update_boss(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
        enraged = self.phase == 2
        if self.charging > 0:
            self.charging -= dt
            self.pos += self.charge_dir * self.speed * self.CHARGE_SPEED * dt
            if self.charging <= 0:
                self._ring(actions, 32 if enraged else 22, 0.9, 0.8, 6, (255, 170, 80))
                if enraged and self.combo < 1:  # phase 2: immediate second charge
                    self.combo += 1
                    self.windup = 0.35
                    self.charge_dir = pygame.Vector2(direction)
                else:
                    self.combo = 0
            return
        if self.windup >= 0:
            self.windup -= dt
            if self.windup < 0:
                self.charging = self.CHARGE_TIME
            return
        self.pos += direction * self.speed * dt
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown * (0.7 if enraged else 1.0)
            self.windup = self.WINDUP * (0.7 if enraged else 1.0)
            self.charge_dir = pygame.Vector2(direction)
        self.stomp_timer -= dt
        if self.stomp_timer <= 0:
            self.stomp_timer = 3.5 if enraged else 5.0
            self._ring(actions, 16, 0.55, 1.0, 10, (200, 120, 60))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self.windup >= 0:
            pygame.draw.line(surface, (255, 120, 40), p, p + self.charge_dir * 700, 3)
        if self._draw_sprite(surface, p):
            return
        r = self.radius
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(5, 7), r)
        rect = pygame.Rect(0, 0, int(r * 1.9), int(r * 1.9))
        rect.center = (int(p.x), int(p.y))
        pygame.draw.rect(surface, self._body_color(), rect, border_radius=14)
        pygame.draw.rect(surface, (255, 220, 180), rect, 4, border_radius=14)
        for k in (-1, 1):  # shoulder plates
            plate = pygame.Rect(0, 0, int(r * 0.7), int(r * 0.5))
            plate.center = (int(p.x + k * r * 0.55), int(p.y - r * 0.55))
            pygame.draw.rect(surface, (120, 70, 40), plate, border_radius=6)
        eye = p + pygame.Vector2(math.cos(self.facing), math.sin(self.facing)) * r * 0.5
        pygame.draw.circle(surface, (255, 60, 30) if self.phase == 2 else (255, 200, 80), eye, 9)


class Warden(Boss):
    """Spins bullet streams, fires telegraphed lance volleys, and hides behind shield drones."""

    LANCE_AIM: float = 0.8

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.lance_aim: float = -1.0
        self.lance_angle: float = 0.0
        self.drone_timer: float = 1.0
        #: set by the world each frame: number of shield drones alive
        self.drones_alive: int = 0

    def _update_boss(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
        enraged = self.phase == 2
        self.damage_taken_mult = 0.2 if self.drones_alive > 0 else 1.0
        desired = self.data.attack_range * 0.6
        if dist > desired:
            self.pos += direction * self.speed * dt
        else:
            perp = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            self.pos += perp * self.speed * 0.5 * dt

        # rotating streams
        self.spiral_timer -= dt
        if self.spiral_timer <= 0:
            self.spiral_timer = 0.11 if enraged else 0.15
            self.spiral_angle += 0.16 if enraged else 0.12
            arms = 6 if enraged else 4
            for k in range(arms):
                self._shoot(actions, self.spiral_angle + k * math.tau / arms, 0.7, 0.6, 5, (140, 180, 255))

        # lance volley: aim, then a tight line of fast bullets
        if self.lance_aim >= 0:
            self.lance_aim -= dt
            if self.lance_aim < 0:
                for i in range(14):
                    self._shoot(actions, self.lance_angle, 1.6 + i * 0.08, 0.9, 5, (255, 255, 255))
        else:
            self.attack_timer -= dt
            if self.attack_timer <= 0:
                self.attack_timer = self.data.attack_cooldown * (0.6 if enraged else 1.0)
                self.lance_aim = self.LANCE_AIM
                self.lance_angle = self.facing

        # shield drones
        self.drone_timer -= dt
        if self.drone_timer <= 0:
            self.drone_timer = 10.0 if enraged else 14.0
            if self.drones_alive < 2:
                actions.summons.extend(["drone"] * (4 if enraged else 3))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self.lance_aim >= 0:
            end = p + pygame.Vector2(math.cos(self.lance_angle), math.sin(self.lance_angle)) * 1400
            pygame.draw.line(surface, (255, 255, 255), p, end, 1 if self.lance_aim > 0.3 else 4)
        if self.drones_alive > 0:  # protected bubble
            t = pygame.time.get_ticks() / 1000
            pygame.draw.circle(surface, (120, 170, 255), p, self.radius + 14 + math.sin(t * 5) * 3, 3)
        if self._draw_sprite(surface, p):
            return
        r = self.radius
        t = pygame.time.get_ticks() / 1000.0
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(4, 6), r)
        pts = [p + pygame.Vector2(math.cos(-t * 0.6 + i * math.tau / 6), math.sin(-t * 0.6 + i * math.tau / 6)) * r
               for i in range(6)]
        pygame.draw.polygon(surface, self._body_color(), pts)
        pygame.draw.polygon(surface, (220, 235, 255), pts, 4)
        pygame.draw.circle(surface, (20, 30, 60), p, r * 0.5)
        pygame.draw.circle(surface, (255, 80, 80) if self.phase == 2 else (160, 220, 255), p, r * 0.3)
