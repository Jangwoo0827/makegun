"""Enemies and their AI. Stats come from data/enemies.json."""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field

import pygame

import settings
from entities.bullet import Bullet
from systems.assets import ASSETS, enemy_sprite_size

Color = tuple[int, int, int]


@dataclass(frozen=True)
class EnemyData:
    enemy_type: str
    name: str
    behavior: str
    hp: float
    speed: float
    damage: float
    radius: float
    color: Color
    reward: int
    armor: float
    attack_range: float
    attack_cooldown: float
    projectile_speed: float
    shape: str


def load_enemy_data(path: str | None = None) -> dict[str, EnemyData]:
    path = path or os.path.join(settings.DATA_DIR, "enemies.json")
    with open(path, "r", encoding="utf-8") as f:
        raw: dict[str, dict] = json.load(f)
    db: dict[str, EnemyData] = {}
    for key, d in raw.items():
        db[key] = EnemyData(
            enemy_type=key, name=d["name"], behavior=d["behavior"], hp=float(d["hp"]),
            speed=float(d["speed"]), damage=float(d["damage"]), radius=float(d["radius"]),
            color=tuple(d["color"]), reward=int(d["reward"]), armor=float(d.get("armor", 0.0)),  # type: ignore[arg-type]
            attack_range=float(d.get("attack_range", 0)), attack_cooldown=float(d.get("attack_cooldown", 1.0)),
            projectile_speed=float(d.get("projectile_speed", 0)), shape=str(d.get("shape", "circle")),
        )
    return db


@dataclass
class WaveScaling:
    hp: float = 1.0
    damage: float = 1.0
    speed: float = 1.0


@dataclass
class EnemyActions:
    """Things an enemy wants the world to do this frame."""
    bullets: list[Bullet] = field(default_factory=list)
    summons: list[str] = field(default_factory=list)
    #: (position, radius, damage) blasts that hurt the player
    explosions: list[tuple[pygame.Vector2, float, float]] = field(default_factory=list)
    #: (position, radius, amount) heals applied to nearby enemies
    heals: list[tuple[pygame.Vector2, float, float]] = field(default_factory=list)


_next_id: int = 0


def _new_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


class Enemy:
    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        scaling = scaling or WaveScaling()
        self.uid: int = _new_id()
        self.enemy_type: str = enemy_type
        self.data: EnemyData = data
        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.radius: float = data.radius
        self.max_hp: float = data.hp * scaling.hp
        self.hp: float = self.max_hp
        self.base_speed: float = data.speed * scaling.speed
        self.speed: float = self.base_speed
        self.slow_time: float = 0.0
        self.slow_amount: float = 0.0
        self.damage: float = data.damage * scaling.damage
        self.armor: float = data.armor
        self.reward: int = data.reward
        self.knockback: pygame.Vector2 = pygame.Vector2()
        self.attack_timer: float = random.uniform(0.3, 1.0) * data.attack_cooldown
        self.contact_timer: float = 0.0
        self.burn_time: float = 0.0
        self.burn_dps: float = 0.0
        self.flash: float = 0.0
        self.alive: bool = True
        self.facing: float = 0.0
        self.strafe_dir: int = random.choice((-1, 1))
        # elite dash state
        self.dash_timer: float = 2.5
        self.dash_time: float = 0.0
        self.dash_dir: pygame.Vector2 = pygame.Vector2()
        # obstacle avoidance: detect being pinned against a wall and slide around it
        self.last_pos: pygame.Vector2 = pygame.Vector2(pos)
        self.stuck_time: float = 0.0
        self.detour_time: float = 0.0
        #: set by the world each frame; ranged enemies approach when they can't see the player
        self.has_los: bool = True

    @property
    def is_boss(self) -> bool:
        return self.data.behavior == "boss"

    # --------------------------------------------------------------- damage
    def take_damage(self, amount: float, ignore_armor: bool = False) -> float:
        if not self.alive:
            return 0.0
        dealt = amount if ignore_armor else amount * (1.0 - self.armor)
        self.hp -= dealt
        self.flash = 0.08
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dealt

    def apply_burn(self, dps: float, duration: float = 3.0) -> None:
        self.burn_dps = max(self.burn_dps, dps)
        self.burn_time = duration

    def apply_slow(self, amount: float, duration: float) -> None:
        resist = 0.4 if self.is_boss else 1.0
        self.slow_amount = max(self.slow_amount, amount * resist)
        self.slow_time = duration

    def push(self, direction: pygame.Vector2, force: float) -> None:
        resist = 0.15 if self.is_boss else (0.4 if self.enemy_type in ("tank", "elite") else 1.0)
        if direction.length_squared() > 0:
            self.knockback += direction.normalize() * force * resist

    def on_death(self) -> EnemyActions:
        """Hook for death effects (splitting, exploding...). Default: nothing."""
        return EnemyActions()

    # --------------------------------------------------------------- update
    def update(self, dt: float, player_pos: pygame.Vector2) -> EnemyActions:
        actions = EnemyActions()
        self.flash = max(0.0, self.flash - dt)
        self.contact_timer = max(0.0, self.contact_timer - dt)
        if self.slow_time > 0:
            self.slow_time -= dt
            if self.slow_time <= 0:
                self.slow_amount = 0.0
        self.speed = self.base_speed * (1.0 - self.slow_amount)
        if self.burn_time > 0:
            self.burn_time -= dt
            self.take_damage(self.burn_dps * dt, ignore_armor=True)
            if self.burn_time <= 0:
                self.burn_dps = 0.0

        to_player = player_pos - self.pos
        dist = to_player.length()
        direction = to_player / dist if dist > 0 else pygame.Vector2()
        self.facing = math.atan2(direction.y, direction.x)
        direction = self._steer(dt, direction)

        # Behavior "xyz" maps to method _update_xyz; unknown behaviors walk at the player.
        handler = getattr(self, f"_update_{self.data.behavior}", None)
        if handler is not None:
            handler(dt, dist, direction, actions)
        else:
            self.pos += direction * self.speed * dt

        self.pos += self.knockback * dt
        self.knockback *= max(0.0, 1.0 - 8.0 * dt)
        return actions

    def _steer(self, dt: float, direction: pygame.Vector2) -> pygame.Vector2:
        """If walls kept us from moving last frames, walk sideways for a while."""
        moved = (self.pos - self.last_pos).length()
        self.last_pos.update(self.pos)
        expected = self.speed * dt
        if self.detour_time > 0:
            self.detour_time -= dt
            side = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            return (side * 0.85 + direction * 0.15).normalize() if side.length_squared() > 0 else direction
        if expected > 0 and moved < expected * 0.25 and self.knockback.length_squared() < 100:
            self.stuck_time += dt
            if self.stuck_time > 0.3:
                self.stuck_time = 0.0
                self.detour_time = random.uniform(0.6, 1.2)
                self.strafe_dir = random.choice((-1, 1))
        else:
            self.stuck_time = 0.0
        return direction

    def _shoot(self, actions: EnemyActions, angle: float, speed_mult: float = 1.0,
               damage_mult: float = 1.0, radius: float = 5.0, color: Color | None = None) -> None:
        vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * self.data.projectile_speed * speed_mult
        start = self.pos + vel.normalize() * (self.radius + 4)
        actions.bullets.append(Bullet(start, vel, self.damage * damage_mult, 4.0, from_player=False,
                                      radius=radius, color=color or settings.ENEMY_BULLET_COLOR))

    def _update_ranged(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        desired = self.data.attack_range * 0.8
        if dist > self.data.attack_range or not self.has_los:
            self.pos += direction * self.speed * dt
        elif dist < desired * 0.6:
            self.pos -= direction * self.speed * dt
        else:
            perp = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            self.pos += perp * self.speed * 0.5 * dt
        self.attack_timer -= dt
        if self.attack_timer <= 0 and dist <= self.data.attack_range * 1.1 and self.has_los:
            self.attack_timer = self.data.attack_cooldown
            self._shoot(actions, self.facing)

    def _update_elite(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        # Special ability 1: telegraphed dash. Ability 2: radial bullet nova.
        if self.dash_time > 0:
            self.dash_time -= dt
            self.pos += self.dash_dir * self.speed * 4.0 * dt
        else:
            self.pos += direction * self.speed * dt
            self.dash_timer -= dt
            if self.dash_timer <= 0 and dist < 450:
                self.dash_timer = random.uniform(2.5, 4.0)
                self.dash_time = 0.35
                self.dash_dir = pygame.Vector2(direction)
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown
            offset = random.uniform(0, math.tau)
            for i in range(12):
                self._shoot(actions, offset + i * math.tau / 12, 0.9, 0.7, color=(255, 80, 220))

    def _update_boss(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        pass  # implemented by Boss

    # ----------------------------------------------------------------- draw
    def _body_color(self) -> Color:
        if self.flash > 0:
            return (255, 255, 255)
        if self.burn_time > 0:
            c = self.data.color
            return (min(255, c[0] + 30), min(255, c[1] + 60), c[2] // 2)
        if self.slow_time > 0:
            c = self.data.color
            return (c[0] // 2 + 60, c[1] // 2 + 90, min(255, c[2] // 2 + 128))
        return self.data.color

    def _draw_sprite(self, surface: pygame.Surface, p: pygame.Vector2) -> bool:
        """Use assets/images/enemies/<type>.png if it exists (drawn facing right)."""
        if not ASSETS.has("enemies", self.enemy_type):
            return False
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(3, 4), self.radius)
        ASSETS.blit_centered(surface, "enemies", self.enemy_type, p, enemy_sprite_size(self.radius),
                             -math.degrees(self.facing))
        if self.flash > 0:
            pygame.draw.circle(surface, (255, 255, 255), p, self.radius, 3)
        return True

    def _draw_hp_bar(self, surface: pygame.Surface, p: pygame.Vector2) -> None:
        if not self.is_boss and self.hp < self.max_hp:
            r = self.radius
            w = r * 2
            pygame.draw.rect(surface, (40, 10, 10), (p.x - w / 2, p.y - r - 9, w, 4))
            pygame.draw.rect(surface, (255, 70, 70), (p.x - w / 2, p.y - r - 9, w * self.hp / self.max_hp, 4))

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self._draw_sprite(surface, p):
            self._draw_hp_bar(surface, p)
            return
        r = self.radius
        color = self._body_color()
        edge = tuple(max(0, c - 90) for c in self.data.color)
        shape = self.data.shape
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(3, 4), r)
        if shape == "triangle":
            pts = [p + pygame.Vector2(math.cos(self.facing + a), math.sin(self.facing + a)) * r
                   for a in (0, 2.4, -2.4)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, edge, pts, 2)
        elif shape == "square":
            rect = pygame.Rect(0, 0, r * 1.8, r * 1.8)
            rect.center = (int(p.x), int(p.y))
            pygame.draw.rect(surface, color, rect, border_radius=5)
            pygame.draw.rect(surface, edge, rect, 3, border_radius=5)
        elif shape == "diamond":
            pts = [p + pygame.Vector2(0, -r), p + pygame.Vector2(r, 0), p + pygame.Vector2(0, r), p + pygame.Vector2(-r, 0)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, edge, pts, 2)
            tip = p + pygame.Vector2(math.cos(self.facing), math.sin(self.facing)) * (r + 8)
            pygame.draw.line(surface, (80, 30, 60), p, tip, 4)
        elif shape == "hexagon":
            pts = [p + pygame.Vector2(math.cos(i * math.pi / 3), math.sin(i * math.pi / 3)) * r for i in range(6)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, (255, 220, 255), pts, 3)
            if self.dash_timer < 0.5 and self.dash_time <= 0:
                pygame.draw.circle(surface, (255, 255, 255), p, r + 6, 2)
        else:
            pygame.draw.circle(surface, color, p, r)
            pygame.draw.circle(surface, edge, p, r, 2)
        if self.data.behavior == "melee" and shape == "circle":
            eye = p + pygame.Vector2(math.cos(self.facing), math.sin(self.facing)) * r * 0.5
            pygame.draw.circle(surface, (255, 230, 200), eye, 3)
        self._draw_hp_bar(surface, p)


class Boss(Enemy):
    """THE GUNNER: aimed volleys, ring barrages and a phase-two spiral storm."""

    def __init__(self, enemy_type: str, data: EnemyData, pos: pygame.Vector2,
                 scaling: WaveScaling | None = None) -> None:
        super().__init__(enemy_type, data, pos, scaling)
        self.ring_timer: float = 3.5
        self.spiral_angle: float = 0.0
        self.spiral_timer: float = 0.0
        self.summon_timer: float = 8.0
        self.phase: int = 1
        self.phase_announced: bool = False

    def _update_boss(self, dt: float, dist: float, direction: pygame.Vector2, actions: EnemyActions) -> None:
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
        enraged = self.phase == 2
        speed = self.speed * (1.35 if enraged else 1.0)
        desired = self.data.attack_range * 0.6
        if dist > desired:
            self.pos += direction * speed * dt
        else:
            perp = pygame.Vector2(-direction.y, direction.x) * self.strafe_dir
            self.pos += perp * speed * 0.6 * dt
            if random.random() < dt * 0.3:
                self.strafe_dir *= -1

        self.attack_timer -= dt
        if self.attack_timer <= 0:
            self.attack_timer = self.data.attack_cooldown * (0.65 if enraged else 1.0)
            count = 5 if enraged else 3
            for i in range(count):
                self._shoot(actions, self.facing + (i - (count - 1) / 2) * 0.16, 1.4, 1.0, 6)

        self.ring_timer -= dt
        if self.ring_timer <= 0:
            self.ring_timer = 3.0 if enraged else 4.5
            n = 28 if enraged else 20
            off = random.uniform(0, math.tau)
            for i in range(n):
                self._shoot(actions, off + i * math.tau / n, 0.85, 0.8, 6, (255, 140, 60))

        if enraged:
            self.spiral_timer -= dt
            if self.spiral_timer <= 0:
                self.spiral_timer = 0.09
                self.spiral_angle += 0.33
                for k in range(3):
                    self._shoot(actions, self.spiral_angle + k * math.tau / 3, 0.75, 0.6, 5, (255, 220, 80))
            self.summon_timer -= dt
            if self.summon_timer <= 0:
                self.summon_timer = 9.0
                actions.summons.extend(["fast", "fast", "normal"])

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self._draw_sprite(surface, p):
            return
        r = self.radius
        t = pygame.time.get_ticks() / 1000.0
        aura = (255, 60, 60) if self.phase == 1 else (255, 160, 40)
        pygame.draw.circle(surface, aura, p, r + 8 + math.sin(t * 6) * 3, 3)
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(4, 6), r)
        pts = [p + pygame.Vector2(math.cos(t * 0.8 + i * math.tau / 8), math.sin(t * 0.8 + i * math.tau / 8)) * r
               for i in range(8)]
        pygame.draw.polygon(surface, self._body_color(), pts)
        pygame.draw.polygon(surface, (255, 220, 220), pts, 3)
        for k in (-1, 1):
            base = p + pygame.Vector2(math.cos(self.facing + k * 0.5), math.sin(self.facing + k * 0.5)) * r * 0.6
            tip = base + pygame.Vector2(math.cos(self.facing), math.sin(self.facing)) * (r * 0.9)
            pygame.draw.line(surface, (60, 60, 70), base, tip, 10)
        pygame.draw.circle(surface, (255, 240, 120) if self.phase == 2 else (40, 0, 0), p, r * 0.35)

