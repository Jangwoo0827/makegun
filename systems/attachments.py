"""Weapon attachments (the ATTACHMENT part slot): automatic secondary attacks.

Each proc deals `weapon DPS x attach_power x attach_cooldown`, so an attachment adds roughly
`attach_power` x the weapon's DPS while it is working, and scales with every weapon upgrade.
"""
from __future__ import annotations

import math
from typing import Callable

import pygame

from entities.bullet import Bullet
from entities.enemy import Enemy
from entities.grenade import Grenade
from entities.player import Player
from game.world import World
from systems.combat import CombatSystem
from systems.sound import SoundManager


class AttachmentSystem:
    def __init__(self, world: World, combat: CombatSystem, sound: SoundManager,
                 add_grenade: Callable[[Grenade], None]) -> None:
        self.world = world
        self.combat = combat
        self.sound = sound
        self.add_grenade = add_grenade
        self.timer: float = 0.0
        self.drone_angle: float = 0.0
        self.slash_time: float = 0.0       # katana swing animation
        self.slash_angle: float = 0.0

    # ----------------------------------------------------------------- helpers
    def _proc_damage(self, player: Player) -> float:
        s = player.weapon.stats
        return max(1.0, s.dps * s.attach_power * max(s.attach_cooldown, 0.05))

    def _enemies_in(self, center: pygame.Vector2, radius: float) -> list[Enemy]:
        return [e for e in self.world.enemies
                if e.alive and (e.pos - center).length_squared() <= (radius + e.radius) ** 2]

    def _in_arc(self, origin: pygame.Vector2, facing: float, half_arc: float, point: pygame.Vector2) -> bool:
        d = point - origin
        if d.length_squared() < 1:
            return True
        diff = (math.atan2(d.y, d.x) - facing + math.pi) % math.tau - math.pi
        return abs(diff) <= half_arc

    def drone_pos(self, player: Player) -> pygame.Vector2:
        return player.pos + pygame.Vector2(math.cos(self.drone_angle), math.sin(self.drone_angle)) * 46

    # ------------------------------------------------------------------ update
    def update(self, dt: float, player: Player, firing: bool) -> None:
        s = player.weapon.stats
        kind = s.attachment
        self.slash_time = max(0.0, self.slash_time - dt)
        self.drone_angle += dt * 2.4
        if kind == "none" or not player.alive:
            return
        self.timer -= dt
        if self.timer > 0:
            return
        handler = getattr(self, f"_{kind}", None)
        if handler is not None and handler(player, firing):
            self.timer = s.attach_cooldown

    def _bayonet(self, player: Player, firing: bool) -> bool:
        s = player.weapon.stats
        targets = [e for e in self._enemies_in(player.pos, s.attach_range)]
        if not targets:
            return False
        target = min(targets, key=lambda e: (e.pos - player.pos).length_squared())
        self.combat.deal_damage(target, self._proc_damage(player), False, False, s.lifesteal)
        target.push(target.pos - player.pos, 120)
        self.world.effects.burst(target.pos, (220, 225, 235), 6, 160, 0.2, 2)
        return True

    def _katana(self, player: Player, firing: bool) -> bool:
        s = player.weapon.stats
        half = math.radians(s.attach_arc) / 2
        facing = player.angle
        targets = [e for e in self._enemies_in(player.pos, s.attach_range)
                   if self._in_arc(player.pos, facing, half, e.pos)]
        if not targets:
            return False
        dmg = self._proc_damage(player)
        for e in targets:
            self.combat.deal_damage(e, dmg, False, False, s.lifesteal)
            e.push(e.pos - player.pos, 220)
        # the blade also cuts enemy bullets out of the air
        for b in self.world.enemy_bullets:
            if (b.pos - player.pos).length() <= s.attach_range and self._in_arc(player.pos, facing, half, b.pos):
                b.alive = False
        self.slash_time = 0.18
        self.slash_angle = facing
        self.sound.play("hit", 30)
        return True

    def _launcher(self, player: Player, firing: bool) -> bool:
        if not firing:
            return False
        s = player.weapon.stats
        # lob at the nearest enemy in front (within ~45 degrees), else at max range
        ahead = [e for e in self._enemies_in(player.pos, s.attach_range)
                 if self._in_arc(player.pos, player.angle, math.radians(45), e.pos)]
        if ahead:
            target = min(ahead, key=lambda e: (e.pos - player.pos).length_squared()).pos
        else:
            target = player.pos + player.aim_dir * s.attach_range
        self.add_grenade(Grenade(player.muzzle_pos(), target, self._proc_damage(player), 95.0))
        return True

    def _flamer(self, player: Player, firing: bool) -> bool:
        if not firing:
            return False
        s = player.weapon.stats
        half = math.radians(s.attach_arc) / 2
        origin = player.muzzle_pos()
        dmg = self._proc_damage(player)
        for e in self._enemies_in(origin, s.attach_range):
            if self._in_arc(origin, player.angle, half, e.pos):
                self.combat.deal_damage(e, dmg, False, False, s.lifesteal)
                e.apply_burn(dmg * 2.0, 2.0)
        self.world.effects.burst(origin, (255, 140, 40), 5, s.attach_range * 2.4, 0.35, 4, player.aim_dir, half)
        return True

    def _drone(self, player: Player, firing: bool) -> bool:
        s = player.weapon.stats
        pos = self.drone_pos(player)
        targets = self._enemies_in(pos, s.attach_range)
        targets = [e for e in targets if e.has_los]
        if not targets:
            return False
        target = min(targets, key=lambda e: (e.pos - pos).length_squared())
        d = target.pos - pos
        vel = d.normalize() * 900 if d.length_squared() > 0 else pygame.Vector2(900, 0)
        self.world.bullets.append(Bullet(pos, vel, self._proc_damage(player), s.attach_range / 900 + 0.1,
                                         radius=3.0, color=(255, 220, 90), crit_chance=s.crit_chance,
                                         crit_damage=s.crit_damage, knockback=40))
        return True

    def _tesla(self, player: Player, firing: bool) -> bool:
        s = player.weapon.stats
        targets = sorted(self._enemies_in(player.pos, s.attach_range),
                         key=lambda e: (e.pos - player.pos).length_squared())[:4]
        if not targets:
            return False
        dmg = self._proc_damage(player)
        for e in targets:
            self.world.effects.arc(player.pos, e.pos)
            self.combat.deal_damage(e, dmg, False, True, s.lifesteal)
        return True

    # -------------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface, offset: pygame.Vector2, player: Player) -> None:
        s = player.weapon.stats
        if s.attachment == "drone":
            p = self.drone_pos(player) - offset
            pygame.draw.circle(surface, (0, 0, 0), p + pygame.Vector2(2, 3), 8)
            pygame.draw.circle(surface, (255, 220, 90), p, 8)
            pygame.draw.circle(surface, (60, 50, 20), p, 8, 2)
            pygame.draw.circle(surface, (255, 255, 255), p, 3)
        if self.slash_time > 0:
            r = s.attach_range
            p = player.pos - offset
            rect = pygame.Rect(0, 0, r * 2, r * 2)
            rect.center = (int(p.x), int(p.y))
            half = math.radians(max(30.0, s.attach_arc)) / 2
            a = -self.slash_angle  # pygame arcs use counter-clockwise screen angles
            for k, width in ((1.0, 6), (0.85, 3)):
                rr = rect.inflate(-r * (1 - k) * 2, -r * (1 - k) * 2)
                pygame.draw.arc(surface, (235, 240, 255), rr, a - half, a + half, width)
