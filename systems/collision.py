"""Collision detection and resolution between entities and the arena."""
from __future__ import annotations

from typing import Callable

import pygame

from entities.bullet import Bullet
from entities.enemy import Enemy
from entities.pickup import Pickup
from entities.player import Player


def resolve_circle_rect(pos: pygame.Vector2, radius: float, rect: pygame.Rect) -> bool:
    """Push a circle out of a rect. Mutates `pos`. Returns True on contact."""
    cx = max(rect.left, min(pos.x, rect.right))
    cy = max(rect.top, min(pos.y, rect.bottom))
    dx, dy = pos.x - cx, pos.y - cy
    dist_sq = dx * dx + dy * dy
    if dist_sq >= radius * radius:
        return False
    if dist_sq > 1e-9:
        dist = dist_sq ** 0.5
        push = radius - dist
        pos.x += dx / dist * push
        pos.y += dy / dist * push
    else:  # center inside rect: push out along smallest axis
        left, right = pos.x - rect.left, rect.right - pos.x
        top, bottom = pos.y - rect.top, rect.bottom - pos.y
        m = min(left, right, top, bottom)
        if m == left:
            pos.x = rect.left - radius
        elif m == right:
            pos.x = rect.right + radius
        elif m == top:
            pos.y = rect.top - radius
        else:
            pos.y = rect.bottom + radius
    return True


def resolve_walls(pos: pygame.Vector2, radius: float, walls: list[pygame.Rect]) -> None:
    for wall in walls:
        resolve_circle_rect(pos, radius, wall)


def circles_overlap(a: pygame.Vector2, ar: float, b: pygame.Vector2, br: float) -> bool:
    r = ar + br
    return (a - b).length_squared() <= r * r


def segment_hits_circle(p0: pygame.Vector2, p1: pygame.Vector2, center: pygame.Vector2, radius: float) -> bool:
    """Swept test so fast bullets cannot tunnel through small enemies."""
    seg = p1 - p0
    length_sq = seg.length_squared()
    if length_sq < 1e-9:
        return (center - p1).length_squared() <= radius * radius
    t = max(0.0, min(1.0, (center - p0).dot(seg) / length_sq))
    closest = p0 + seg * t
    return (center - closest).length_squared() <= radius * radius


def line_of_sight(a: pygame.Vector2, b: pygame.Vector2, walls: list[pygame.Rect]) -> bool:
    """True if the segment a-b crosses no wall."""
    for wall in walls:
        if wall.clipline(a.x, a.y, b.x, b.y):
            return False
    return True


def bullet_wall_hit(bullet: Bullet, walls: list[pygame.Rect]) -> pygame.Rect | None:
    for wall in walls:
        if wall.collidepoint(bullet.pos.x, bullet.pos.y):
            return wall
    return None


def reflect_bullet(bullet: Bullet, wall: pygame.Rect) -> None:
    """Bounce a bullet off the side of `wall` it entered from."""
    prev = bullet.prev_pos
    if prev.x < wall.left or prev.x > wall.right:
        bullet.velocity.x *= -1
    if prev.y < wall.top or prev.y > wall.bottom:
        bullet.velocity.y *= -1
    if wall.left <= prev.x <= wall.right and wall.top <= prev.y <= wall.bottom:
        bullet.velocity *= -1
    bullet.pos.update(prev)


def separate_enemies(enemies: list[Enemy]) -> None:
    """Cheap pairwise separation so enemies don't stack into one blob."""
    n = len(enemies)
    for i in range(n):
        a = enemies[i]
        for j in range(i + 1, n):
            b = enemies[j]
            d = a.pos - b.pos
            r = a.radius + b.radius
            dsq = d.length_squared()
            if 0 < dsq < r * r:
                dist = dsq ** 0.5
                push = d / dist * (r - dist) * 0.5
                wa = 0.2 if a.is_boss else 1.0
                wb = 0.2 if b.is_boss else 1.0
                a.pos += push * wa
                b.pos -= push * wb


class CollisionSystem:
    """Runs every collision pair each frame; delegates consequences to callbacks."""

    def __init__(
        self,
        on_bullet_hit_enemy: Callable[[Bullet, Enemy], None],
        on_bullet_hit_wall: Callable[[Bullet, pygame.Rect], None],
        on_player_hit: Callable[[float, pygame.Vector2], None],
        on_pickup: Callable[[Pickup], None],
    ) -> None:
        self.on_bullet_hit_enemy = on_bullet_hit_enemy
        self.on_bullet_hit_wall = on_bullet_hit_wall
        self.on_player_hit = on_player_hit
        self.on_pickup = on_pickup

    def update(self, player: Player, enemies: list[Enemy], bullets: list[Bullet],
               enemy_bullets: list[Bullet], pickups: list[Pickup], walls: list[pygame.Rect]) -> None:
        # Player <-> Wall, Enemy <-> Wall
        resolve_walls(player.pos, player.radius, walls)
        separate_enemies(enemies)
        for e in enemies:
            resolve_walls(e.pos, e.radius, walls)

        # Bullet <-> Wall, Bullet <-> Enemy
        for b in bullets:
            if not b.alive:
                continue
            wall = bullet_wall_hit(b, walls)
            if wall is not None:
                self.on_bullet_hit_wall(b, wall)
                continue
            for e in enemies:
                if not e.alive or e.uid in b.hit_ids:
                    continue
                if segment_hits_circle(b.prev_pos, b.pos, e.pos, b.radius + e.radius):
                    b.hit_ids.add(e.uid)
                    self.on_bullet_hit_enemy(b, e)
                    if not b.alive:
                        break

        # Enemy bullet <-> Wall / Player
        for b in enemy_bullets:
            if not b.alive:
                continue
            if bullet_wall_hit(b, walls) is not None:
                b.alive = False
                continue
            if circles_overlap(b.pos, b.radius, player.pos, player.radius * 0.8):
                b.alive = False
                self.on_player_hit(b.damage, b.pos)

        # Enemy <-> Player (contact damage)
        for e in enemies:
            if e.alive and e.contact_timer <= 0 and circles_overlap(e.pos, e.radius, player.pos, player.radius):
                e.contact_timer = e.data.attack_cooldown
                self.on_player_hit(e.damage, e.pos)

        # Player <-> Pickup
        for p in pickups:
            if p.alive and circles_overlap(p.pos, p.radius, player.pos, player.radius):
                p.alive = False
                self.on_pickup(p)
