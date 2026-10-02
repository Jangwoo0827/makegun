"""Turns a queue of enemy types into Enemy objects at safe positions over time."""
from __future__ import annotations

import random

import pygame

import settings
from entities.enemy import Enemy, EnemyData, WaveScaling
from entities.enemy_types import create_enemy
from systems.affixes import roll_affix
from systems.collision import resolve_walls

MIN_SPAWN_DIST: float = 420.0


class SpawnManager:
    def __init__(self, enemy_db: dict[str, EnemyData], walls: list[pygame.Rect]) -> None:
        self.enemy_db = enemy_db
        self.walls = walls
        self.queue: list[str] = []
        self.scaling: WaveScaling = WaveScaling()
        self.timer: float = 0.0
        self.interval: float = settings.SPAWN_INTERVAL
        self.reward_mult: float = 1.0
        self.affix_chance: float = 0.0

    def start(self, queue: list[str], scaling: WaveScaling, interval: float) -> None:
        self.queue = list(queue)
        self.scaling = scaling
        self.interval = interval
        self.timer = 0.0

    @property
    def pending(self) -> int:
        return len(self.queue)

    def random_spawn_point(self, player_pos: pygame.Vector2, radius: float) -> pygame.Vector2:
        margin = settings.WALL_THICKNESS + radius + 10
        pos = pygame.Vector2()
        for _ in range(30):
            pos = pygame.Vector2(random.uniform(margin, settings.ARENA_WIDTH - margin),
                                 random.uniform(margin, settings.ARENA_HEIGHT - margin))
            if (pos - player_pos).length() < MIN_SPAWN_DIST:
                continue
            if any(w.inflate(radius * 2, radius * 2).collidepoint(pos.x, pos.y) for w in self.walls):
                continue
            return pos
        resolve_walls(pos, radius, self.walls)
        return pos

    def spawn_now(self, enemy_type: str, player_pos: pygame.Vector2, near: pygame.Vector2 | None = None) -> Enemy:
        data = self.enemy_db[enemy_type]
        if near is not None:
            pos = near + pygame.Vector2(random.uniform(-60, 60), random.uniform(-60, 60))
            resolve_walls(pos, data.radius, self.walls)
        else:
            pos = self.random_spawn_point(player_pos, data.radius)
        enemy = create_enemy(enemy_type, self.enemy_db, pos, self.scaling)
        enemy.reward = max(1, int(enemy.reward * self.reward_mult))
        if near is None:  # summons never roll affixes
            roll_affix(enemy, self.affix_chance)
        return enemy

    def update(self, dt: float, player_pos: pygame.Vector2, alive_count: int) -> list[Enemy]:
        spawned: list[Enemy] = []
        if not self.queue:
            return spawned
        self.timer -= dt
        if self.timer <= 0 and alive_count < settings.MAX_ALIVE_ENEMIES:
            self.timer = self.interval
            # Bosses always spawn even if the arena is busy.
            spawned.append(self.spawn_now(self.queue.pop(0), player_pos))
        return spawned
