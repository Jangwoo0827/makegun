"""The player character."""
from __future__ import annotations

import math

import pygame

import settings
from entities.player_stats import PlayerStats
from systems.assets import ASSETS
from weapons.gun_renderer import draw_gun, muzzle_distance
from weapons.weapon import Weapon

BUFF_DEFS: dict[str, tuple[str, float]] = {
    # name: (label, multiplier)
    "damage": ("DAMAGE x1.5", 1.5),
    "fire_rate": ("FIRE RATE x1.4", 1.4),
    "speed": ("SPEED x1.3", 1.3),
}
BUFF_DURATION: float = 10.0


class Player:
    def __init__(self, pos: pygame.Vector2, stats: PlayerStats, weapons: list[Weapon]) -> None:
        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.radius: float = settings.PLAYER_RADIUS
        self.stats: PlayerStats = stats
        self.hp: float = stats.max_hp
        self.weapons: list[Weapon] = weapons
        self.current: int = 0
        self.angle: float = 0.0
        self.invuln: float = 0.0
        self.buffs: dict[str, float] = {}
        self.muzzle_flash: float = 0.0
        self.hurt_flash: float = 0.0
        self.alive: bool = True
        # active skills
        self.dash_cooldown: float = 0.0
        self.dash_time: float = 0.0
        self.dash_dir: pygame.Vector2 = pygame.Vector2(1, 0)
        self.grenade_cooldown: float = 0.0
        self._effective: PlayerStats = stats.copy()
        self.refresh_weapons()

    # ------------------------------------------------------------- properties
    @property
    def weapon(self) -> Weapon:
        return self.weapons[self.current]

    @property
    def max_hp(self) -> float:
        return self.stats.max_hp

    @property
    def move_speed(self) -> float:
        speed = self.stats.move_speed * self._effective.move_speed_multiplier
        return speed * self.weapon.stats.move_speed_mult

    @property
    def effective_stats(self) -> PlayerStats:
        return self._effective

    def _compute_effective(self) -> PlayerStats:
        eff = self.stats.copy()
        if "damage" in self.buffs:
            eff.damage_multiplier *= BUFF_DEFS["damage"][1]
        if "fire_rate" in self.buffs:
            eff.fire_rate_multiplier *= BUFF_DEFS["fire_rate"][1]
        if "speed" in self.buffs:
            eff.move_speed_multiplier *= BUFF_DEFS["speed"][1]
        return eff

    def refresh_weapons(self) -> None:
        """Recompute derived stats; call after upgrades, buffs or part changes."""
        self._effective = self._compute_effective()
        for w in self.weapons:
            w.refresh(self._effective)
        self.hp = min(self.hp, self.max_hp)

    # --------------------------------------------------------------- actions
    def switch_weapon(self, index: int) -> bool:
        if 0 <= index < len(self.weapons) and index != self.current:
            self.weapon.cancel_actions()
            self.current = index
            return True
        return False

    def add_buff(self, name: str) -> None:
        if name in BUFF_DEFS:
            self.buffs[name] = BUFF_DURATION
            self.refresh_weapons()

    @property
    def dash_cooldown_max(self) -> float:
        return settings.DASH_COOLDOWN * self.stats.dash_cooldown_multiplier

    @property
    def grenade_cooldown_max(self) -> float:
        return settings.GRENADE_COOLDOWN * self.stats.grenade_cooldown_multiplier

    def try_dash(self, move: pygame.Vector2) -> bool:
        """Dash toward the movement direction (or the aim if standing still). Invulnerable while dashing."""
        if self.dash_cooldown > 0 or self.dash_time > 0 or not self.alive:
            return False
        self.dash_dir = move.normalize() if move.length_squared() > 0 else self.aim_dir
        self.dash_time = settings.DASH_TIME
        self.dash_cooldown = self.dash_cooldown_max
        return True

    def try_grenade(self) -> bool:
        if self.grenade_cooldown > 0 or not self.alive:
            return False
        self.grenade_cooldown = self.grenade_cooldown_max
        return True

    def take_damage(self, amount: float) -> bool:
        if self.invuln > 0 or self.dash_time > 0 or not self.alive:
            return False
        self.hp -= amount * (1.0 - self.stats.damage_reduction)
        self.invuln = settings.PLAYER_INVULN_TIME + self.stats.invuln_bonus
        self.hurt_flash = 0.2
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return True

    def heal(self, amount: float) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def aim_at(self, world_target: pygame.Vector2) -> None:
        d = world_target - self.pos
        if d.length_squared() > 1:
            self.angle = math.atan2(d.y, d.x)

    @property
    def aim_dir(self) -> pygame.Vector2:
        return pygame.Vector2(math.cos(self.angle), math.sin(self.angle))

    def muzzle_pos(self) -> pygame.Vector2:
        return self.pos + self.aim_dir * (self.radius * 0.6 + muzzle_distance(self.weapon.parts))

    # ---------------------------------------------------------------- update
    def update(self, dt: float, move: pygame.Vector2) -> None:
        if move.length_squared() > 0:
            move = move.normalize()
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        self.grenade_cooldown = max(0.0, self.grenade_cooldown - dt)
        if self.dash_time > 0:
            self.dash_time -= dt
            self.pos += self.dash_dir * self.move_speed * settings.DASH_SPEED_MULT * dt
        else:
            self.pos += move * self.move_speed * dt
        self.invuln = max(0.0, self.invuln - dt)
        self.muzzle_flash = max(0.0, self.muzzle_flash - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        if self.stats.regen > 0:
            self.heal(self.stats.regen * dt)
        expired = [k for k, t in self.buffs.items() if t - dt <= 0]
        for k in list(self.buffs):
            self.buffs[k] -= dt
        for k in expired:
            del self.buffs[k]
        if expired:
            self.refresh_weapons()

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.pos - offset
        if self.dash_time > 0:  # afterimages
            for i in range(1, 4):
                ghost = p - self.dash_dir * i * 14
                pygame.draw.circle(surface, (90, 180, 230), ghost, self.radius * (1 - i * 0.2), 2)
        if self.invuln > 0 and int(self.invuln * 20) % 2 == 0:
            return
        pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(3, 4), self.radius)
        size = int(self.radius * 2.5)
        if not ASSETS.blit_centered(surface, "player", "player", p, (size, size), -math.degrees(self.angle)):
            body = (255, 120, 120) if self.hurt_flash > 0 else settings.PLAYER_COLOR
            pygame.draw.circle(surface, body, p, self.radius)
            pygame.draw.circle(surface, settings.PLAYER_OUTLINE, p, self.radius, 2)
        elif self.hurt_flash > 0:
            pygame.draw.circle(surface, (255, 90, 90), p, self.radius, 3)
        gun_origin = p + self.aim_dir * (self.radius * 0.6)
        muzzle = draw_gun(surface, self.weapon.parts, gun_origin, self.angle, 1.0)
        if self.muzzle_flash > 0:
            r = 6 + 40 * self.muzzle_flash
            pygame.draw.circle(surface, (255, 240, 170), muzzle, r)
            pygame.draw.circle(surface, (255, 180, 60), muzzle, r * 0.6)
        if self.weapon.stats.fire_mode == "charge" and self.weapon.charge > 0:
            ratio = self.weapon.charge_ratio
            color = (255, 255, 255) if ratio >= 1.0 else (200, 120, 255)
            pygame.draw.circle(surface, color, muzzle, 3 + ratio * 8, 2)
