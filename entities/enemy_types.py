"""Specialised enemy types and the enemy factory.

Each class overrides `_update_<behavior>` (see Enemy.update) and/or `on_death`.
"""
from __future__ import annotations

import math
import random

import pygame

from entities.boss_types import Titan, Warden
from entities.enemy import Boss, Enemy, EnemyActions, EnemyData, WaveScaling


class Splitter(Enemy):
    """Bursts into smaller enemies when killed."""

    SPLIT_INTO: tuple[str, ...] = ("mini", "mini", "mini")

    def on_death(self) -> EnemyActions:
        return EnemyActions(summons=list(self.SPLIT_INTO))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        super().draw(surface, offset)
        p = self.pos - offset
        for i in range(3):
            a = i * math.tau / 3 + pygame.time.get_ticks() / 400
            pygame.draw.circle(surface, (255, 255, 255), p + pygame.Vector2(math.cos(a), math.sin(a)) * self.radius * 0.45, 3)


class Bomber(Enemy):
    """Rushes the player, lights a fuse and explodes. Also explodes when killed."""

    FUSE_TIME: float = 0.7
    TRIGGER_RANGE: float = 70.0
    BLAST_RADIUS: float = 95.0

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.fuse: float = -1.0
        self.exploded: bool = False

    def _update_bomber(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.fuse >= 0:
            self.fuse -= dt
            if self.fuse <= 0:
                self.alive = False  # death handler emits the blast via on_death
            return
        self.pos += direction * self.speed * dt
        if dist < self.TRIGGER_RANGE:
            self.fuse = self.FUSE_TIME

    def on_death(self) -> EnemyActions:
        if self.exploded:
            return EnemyActions()
        self.exploded = True
        return EnemyActions(explosions=[(pygame.Vector2(self.pos), self.BLAST_RADIUS, self.damage)])

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        super().draw(surface, offset)
        p = self.pos - offset
        if self.fuse >= 0:
            blink = int(self.fuse * 20) % 2 == 0
            pygame.draw.circle(surface, (255, 60, 30), p, self.BLAST_RADIUS, 2 if blink else 1)
            if blink:
                pygame.draw.circle(surface, (255, 255, 255), p, self.radius)
        pygame.draw.line(surface, (255, 220, 120), p + pygame.Vector2(0, -self.radius),
                         p + pygame.Vector2(5, -self.radius - 8), 3)


class Sniper(Enemy):
    """Keeps far away, telegraphs with a laser, then fires a very fast shot."""

    AIM_TIME: float = 1.1

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.aiming: float = -1.0
        self.aim_angle: float = 0.0

    def _update_sniper(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        rng = self.data.attack_range
        if self.aiming >= 0:
            # Track slowly while aiming so the player can sidestep.
            diff = (self.facing - self.aim_angle + math.pi) % math.tau - math.pi
            self.aim_angle += max(-0.6 * dt, min(0.6 * dt, diff))
            self.aiming -= dt
            if self.aiming <= 0:
                self.aiming = -1.0
                self.attack_timer = self.data.attack_cooldown
                self._shoot(actions, self.aim_angle, 1.0, 1.0, 4, (255, 255, 160))
            return
        if dist > rng or not self.has_los:
            self.pos += direction * self.speed * dt
        elif dist < rng * 0.6:
            self.pos -= direction * self.speed * dt
        self.attack_timer -= dt
        if self.attack_timer <= 0 and dist <= rng * 1.1 and self.has_los:
            self.aiming = self.AIM_TIME
            self.aim_angle = self.facing

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        if self.aiming >= 0:
            p = self.pos - offset
            end = p + pygame.Vector2(math.cos(self.aim_angle), math.sin(self.aim_angle)) * 1400
            width = 1 if self.aiming > 0.35 else 3
            pygame.draw.line(surface, (255, 60, 60), p, end, width)
        super().draw(surface, offset)


class Healer(Enemy):
    """Hangs back and periodically heals nearby enemies."""

    HEAL_RADIUS: float = 170.0
    HEAL_FRACTION: float = 0.2

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.pulse: float = 0.0

    def _update_healer(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        rng = self.data.attack_range
        if dist > rng or not self.has_los:
            self.pos += direction * self.speed * dt
        elif dist < rng * 0.7:
            self.pos -= direction * self.speed * dt
        self.pulse = max(0.0, self.pulse - dt)
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown
            self.pulse = 0.4
            actions.heals.append((pygame.Vector2(self.pos), self.HEAL_RADIUS, self.HEAL_FRACTION))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        super().draw(surface, offset)
        p = self.pos - offset
        if self.pulse > 0:
            pygame.draw.circle(surface, (120, 255, 140), p, self.HEAL_RADIUS * (1 - self.pulse / 0.4), 2)
        r = self.radius * 0.55
        pygame.draw.rect(surface, (255, 255, 255), (p.x - r, p.y - r * 0.3, r * 2, r * 0.6))
        pygame.draw.rect(surface, (255, 255, 255), (p.x - r * 0.3, p.y - r, r * 0.6, r * 2))


class Charger(Enemy):
    """Winds up, then charges in a straight line at high speed."""

    WINDUP: float = 0.55
    CHARGE_TIME: float = 0.65
    CHARGE_SPEED: float = 3.6

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.windup: float = -1.0
        self.charging: float = 0.0
        self.charge_dir: pygame.Vector2 = pygame.Vector2()

    def _update_charger(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.charging > 0:
            self.charging -= dt
            self.pos += self.charge_dir * self.speed * self.CHARGE_SPEED * dt
            return
        if self.windup >= 0:
            self.windup -= dt
            if self.windup < 0:
                self.charging = self.CHARGE_TIME
            return
        self.pos += direction * self.speed * dt
        self.attack_timer -= dt
        if self.attack_timer <= 0 and dist < self.data.attack_range:
            self.attack_timer = self.data.attack_cooldown
            self.windup = self.WINDUP
            self.charge_dir = pygame.Vector2(direction)

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        if self.windup >= 0:
            p = self.pos - offset
            end = p + self.charge_dir * 260
            pygame.draw.line(surface, (255, 180, 60), p, end, 2)
        super().draw(surface, offset)


class Summoner(Enemy):
    """Keeps its distance and conjures minions."""

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.casting: float = 0.0

    def _update_summoner(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        rng = self.data.attack_range
        if dist > rng or not self.has_los:
            self.pos += direction * self.speed * dt
        elif dist < rng * 0.7:
            self.pos -= direction * self.speed * dt
        else:
            perp = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            self.pos += perp * self.speed * 0.4 * dt
        self.casting = max(0.0, self.casting - dt)
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown
            self.casting = 0.5
            actions.summons.extend(["mini", "mini"])

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        t = pygame.time.get_ticks() / 1000
        for i in range(4):
            a = t * 2 + i * math.tau / 4
            pygame.draw.circle(surface, (190, 120, 255), p + pygame.Vector2(math.cos(a), math.sin(a)) * (self.radius + 8), 3)
        if self.casting > 0:
            pygame.draw.circle(surface, (220, 160, 255), p, self.radius + 16 * (1 - self.casting / 0.5), 2)
        super().draw(surface, offset)


class Broodmother(Boss):
    """Second boss: spawns broods, sprays acid, and goes frantic below 50% HP."""

    def _update_boss(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
        enraged = self.phase == 2
        desired = self.data.attack_range * 0.7
        if dist > desired:
            self.pos += direction * self.speed * dt
        else:
            perp = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            self.pos += perp * self.speed * 0.5 * dt

        # Acid spray: wide fan of slow globs
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown * (0.7 if enraged else 1.0)
            n = 9 if enraged else 7
            for i in range(n):
                a = self.facing + (i - (n - 1) / 2) * 0.13 + random.uniform(-0.04, 0.04)
                self._shoot(actions, a, random.uniform(0.6, 0.9), 0.8, 8, (140, 255, 80))

        # Broods
        self.summon_timer -= dt
        if self.summon_timer <= 0:
            self.summon_timer = 4.5 if enraged else 6.5
            brood = ["mini"] * (5 if enraged else 3)
            if enraged:
                brood += ["charger"]
            actions.summons.extend(brood)

        # Phase 2: double spiral
        if enraged:
            self.spiral_timer -= dt
            if self.spiral_timer <= 0:
                self.spiral_timer = 0.12
                self.spiral_angle += 0.27
                for k in (0, math.pi):
                    self._shoot(actions, self.spiral_angle + k, 0.7, 0.6, 6, (200, 255, 120))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self._draw_sprite(surface, p):
            return
        r = self.radius
        t = pygame.time.get_ticks() / 1000.0
        for i in range(8):  # legs
            a = i * math.tau / 8 + math.sin(t * 4 + i) * 0.15
            pygame.draw.line(surface, (60, 90, 40), p, p + pygame.Vector2(math.cos(a), math.sin(a)) * (r + 22), 6)
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(4, 6), r)
        pygame.draw.circle(surface, self._body_color(), p, r)
        pygame.draw.circle(surface, (220, 255, 180), p, r, 3)
        for k in (-1, 1):
            eye = p + pygame.Vector2(math.cos(self.facing + k * 0.4), math.sin(self.facing + k * 0.4)) * r * 0.55
            pygame.draw.circle(surface, (255, 60, 60) if self.phase == 2 else (255, 230, 80), eye, 6)


ENEMY_CLASSES: dict[str, type[Enemy]] = {
    "boss": Boss,
    "broodmother": Broodmother,
    "splitter": Splitter,
    "bomber": Bomber,
    "sniper": Sniper,
    "healer": Healer,
    "charger": Charger,
    "summoner": Summoner,
    "titan": Titan,
    "warden": Warden,
}


def create_enemy(enemy_type: str, db: dict[str, EnemyData], pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> Enemy:
    """Build the right Enemy subclass for an enemy type id from enemies.json."""
    data = db[enemy_type]
    cls = ENEMY_CLASSES.get(enemy_type, Enemy)
    return cls(enemy_type, data, pos, scaling)
