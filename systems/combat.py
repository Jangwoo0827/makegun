"""Resolves what happens when a player bullet hits: crits, ammo effects, modifiers."""
from __future__ import annotations

import math
import random
from typing import Callable

import pygame

from entities.bullet import Bullet
from entities.enemy import Enemy
from game.world import World
from systems.collision import reflect_bullet
from systems.sound import SoundManager
from weapons.weapon import ShotEvent, WeaponStats

CHAIN_RANGE: float = 170.0
CHAIN_DAMAGE: float = 0.5
EXPLOSION_DAMAGE: float = 0.7
SPLIT_DAMAGE: float = 0.4
BURN_DURATION: float = 3.0
SEEK_RANGE: float = 400.0
SLOW_DURATION: float = 2.0
HOMING_RANGE: float = 450.0


class CombatSystem:
    def __init__(self, world: World, sound: SoundManager, shake: Callable[[float], None]) -> None:
        self.world = world
        self.sound = sound
        self.shake = shake

    # ------------------------------------------------------------- spawning
    def fire(self, origin: pygame.Vector2, angle: float, stats: WeaponStats, shot: ShotEvent,
             color: tuple[int, int, int], sweep_from: pygame.Vector2 | None = None) -> None:
        """Spawn bullets at `origin`; `sweep_from` lets the first frame hit point-blank enemies."""
        count = stats.bullet_count
        spread = math.radians(stats.spread)
        lifetime = stats.range / stats.bullet_speed
        radius = 3.5 + min(4.0, stats.damage * shot.damage_mult / 25.0)
        for i in range(count):
            if count > 1:
                a = angle + (i / (count - 1) - 0.5) * spread + random.uniform(-0.15, 0.15) * spread / count
            else:
                a = angle + random.uniform(-0.5, 0.5) * spread
            speed = stats.bullet_speed * random.uniform(0.95, 1.05)
            vel = pygame.Vector2(math.cos(a), math.sin(a)) * speed
            self.world.bullets.append(Bullet(
                origin, vel, stats.damage * shot.damage_mult, lifetime,
                pierce=stats.pierce + shot.extra_pierce, explosion_radius=stats.explosion_radius,
                ammo_type=stats.ammo_type, radius=radius, color=color,
                crit_chance=stats.crit_chance, crit_damage=stats.crit_damage,
                knockback=stats.knockback, burn=stats.burn, split=stats.split,
                ricochet=stats.ricochet, chain=stats.chain, lifesteal=stats.lifesteal,
                slow=stats.slow, homing=stats.homing,
            ))
            if sweep_from is not None:
                self.world.bullets[-1].prev_pos.update(sweep_from)
        direction = pygame.Vector2(math.cos(angle), math.sin(angle))
        self.world.effects.burst(origin, (255, 220, 140), 4, 220, 0.12, 2.5, direction, 0.4)
        self.shake(min(8.0, 1.0 + stats.damage * shot.damage_mult * count / 40.0))
        self.sound.play("shoot", 40)

    def update_homing(self, dt: float) -> None:
        """Rotate homing bullets toward the nearest enemy they haven't hit yet."""
        for b in self.world.bullets:
            if b.homing <= 0 or not b.alive:
                continue
            target = self._nearest_enemy(b.pos, HOMING_RANGE, b.hit_ids)
            if target is None:
                continue
            speed = b.velocity.length()
            desired = target.pos - b.pos
            if desired.length_squared() < 1 or speed <= 0:
                continue
            desired.scale_to_length(speed)
            b.velocity += (desired - b.velocity) * min(1.0, b.homing * dt)
            if b.velocity.length_squared() > 0:
                b.velocity.scale_to_length(speed)

    # ------------------------------------------------------------------ hits
    def deal_damage(self, enemy: Enemy, amount: float, crit: bool, ignore_armor: bool,
                    lifesteal: float) -> float:
        dealt = enemy.take_damage(amount, ignore_armor)
        self.world.effects.damage_number(enemy.pos - pygame.Vector2(0, enemy.radius), dealt, crit)
        if lifesteal > 0 and dealt > 0:
            self.world.player.heal(dealt * lifesteal)
        return dealt

    def on_bullet_hit_enemy(self, b: Bullet, enemy: Enemy) -> None:
        crit = random.random() < b.crit_chance
        dmg = b.damage * (b.crit_damage if crit else 1.0)
        ignore_armor = b.ammo_type == "armor_piercing"
        self.deal_damage(enemy, dmg, crit, ignore_armor, b.lifesteal)
        enemy.push(b.velocity, b.knockback)
        self.world.effects.burst(b.pos, enemy.data.color, 5, 160, 0.25, 2.5, b.velocity, 0.7)
        self.sound.play("hit", 45)

        if b.slow > 0:
            enemy.apply_slow(b.slow, SLOW_DURATION)
        if b.burn > 0:
            enemy.apply_burn(dmg * b.burn, BURN_DURATION)
        if b.chain > 0:
            self._chain(enemy, dmg * CHAIN_DAMAGE, b.chain, b.lifesteal)
        if b.explosion_radius > 0:
            self.explode(b.pos, b.explosion_radius, dmg * EXPLOSION_DAMAGE, b.lifesteal, exclude=enemy)
        if b.split > 0 and not b.is_fragment:
            self._split(b, dmg)

        if b.pierce > 0:
            b.pierce -= 1
            b.damage *= 0.85
        elif b.ricochet > 0:
            b.ricochet -= 1
            self._seek(b, enemy)
        else:
            b.alive = False

    def on_bullet_hit_wall(self, b: Bullet, wall: pygame.Rect) -> None:
        if b.ricochet > 0:
            b.ricochet -= 1
            reflect_bullet(b, wall)
            self.world.effects.burst(b.pos, b.color, 4, 120, 0.2, 2)
            return
        if b.explosion_radius > 0:
            self.explode(b.prev_pos, b.explosion_radius, b.damage * EXPLOSION_DAMAGE, b.lifesteal)
        self.world.effects.burst(b.prev_pos, (180, 180, 190), 4, 120, 0.2, 2)
        b.alive = False

    def explode(self, pos: pygame.Vector2, radius: float, damage: float, lifesteal: float,
                exclude: Enemy | None = None) -> None:
        self.world.effects.explosion(pos, radius)
        self.shake(min(12.0, 3 + radius / 15))
        self.sound.play("explosion", 70)
        for e in self.world.enemies:
            if e is exclude or not e.alive:
                continue
            d = e.pos - pos
            if d.length() <= radius + e.radius:
                self.deal_damage(e, damage, False, False, lifesteal)
                e.push(d if d.length_squared() > 0 else pygame.Vector2(1, 0), 160)

    def _chain(self, source: Enemy, damage: float, jumps: int, lifesteal: float) -> None:
        current = source
        hit: set[int] = {source.uid}
        for _ in range(jumps):
            nearest = self._nearest_enemy(current.pos, CHAIN_RANGE, hit)
            if nearest is None:
                break
            hit.add(nearest.uid)
            self.world.effects.arc(current.pos, nearest.pos)
            self.deal_damage(nearest, damage, False, True, lifesteal)
            current = nearest

    def _split(self, b: Bullet, damage: float) -> None:
        base = math.atan2(b.velocity.y, b.velocity.x)
        speed = b.velocity.length() * 0.8
        for i in range(b.split):
            a = base + (i - (b.split - 1) / 2) * 0.5
            vel = pygame.Vector2(math.cos(a), math.sin(a)) * speed
            frag = Bullet(b.pos, vel, damage * SPLIT_DAMAGE, 0.35, radius=2.5, color=b.color,
                          crit_chance=b.crit_chance, crit_damage=b.crit_damage, knockback=b.knockback * 0.3,
                          lifesteal=b.lifesteal, is_fragment=True)
            frag.hit_ids = set(b.hit_ids)
            self.world.bullets.append(frag)

    def _seek(self, b: Bullet, hit_enemy: Enemy) -> None:
        target = self._nearest_enemy(b.pos, SEEK_RANGE, b.hit_ids | {hit_enemy.uid})
        speed = b.velocity.length()
        if target is not None:
            d = target.pos - b.pos
            if d.length_squared() > 0:
                b.velocity = d.normalize() * speed
        b.lifetime = max(b.lifetime, 0.4)

    def _nearest_enemy(self, pos: pygame.Vector2, max_range: float, exclude: set[int]) -> Enemy | None:
        best: Enemy | None = None
        best_d = max_range * max_range
        for e in self.world.enemies:
            if not e.alive or e.uid in exclude:
                continue
            d = (e.pos - pos).length_squared()
            if d < best_d:
                best, best_d = e, d
        return best
