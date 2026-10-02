"""World container: the arena and every live entity in it."""
from __future__ import annotations

import pygame

import settings
from entities.bullet import Bullet
from entities.enemy import Enemy
from entities.pickup import Pickup
from entities.player import Player
from systems.assets import ASSETS
from game.stages import StageData
from systems.affixes import draw_affix
from systems.effects import EffectsManager


DEFAULT_OBSTACLES: tuple[tuple[int, int, int, int], ...] = (
    (-620, -380, 140, 140), (480, -380, 140, 140), (-620, 240, 140, 140), (480, 240, 140, 140),
    (-120, -560, 240, 60), (-120, 500, 240, 60), (-960, -40, 60, 200), (900, -100, 60, 200))


def build_arena_walls(obstacles: tuple[tuple[int, int, int, int], ...] = DEFAULT_OBSTACLES) -> list[pygame.Rect]:
    """Outer boundary plus a symmetric set of cover obstacles."""
    w, h, t = settings.ARENA_WIDTH, settings.ARENA_HEIGHT, settings.WALL_THICKNESS
    walls = [
        pygame.Rect(0, 0, w, t),
        pygame.Rect(0, h - t, w, t),
        pygame.Rect(0, 0, t, h),
        pygame.Rect(w - t, 0, t, h),
    ]
    cx, cy = w // 2, h // 2
    # (x offset, y offset, width, height) relative to arena center
    for ox, oy, bw, bh in obstacles:
        walls.append(pygame.Rect(cx + ox, cy + oy, bw, bh))
    return walls


class World:
    def __init__(self, player: Player, stage: StageData | None = None) -> None:
        self.player: Player = player
        self.stage = stage
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.enemy_bullets: list[Bullet] = []
        self.pickups: list[Pickup] = []
        self.walls: list[pygame.Rect] = build_arena_walls(stage.obstacles if stage else DEFAULT_OBSTACLES)
        self.inner_walls: list[pygame.Rect] = self.walls[4:]  # obstacles only (skip boundary)
        self.effects: EffectsManager = EffectsManager()
        self._floor: pygame.Surface = self._render_floor()

    def center(self) -> pygame.Vector2:
        return pygame.Vector2(settings.ARENA_WIDTH / 2, settings.ARENA_HEIGHT / 2)

    def clear_combat(self) -> None:
        self.enemies.clear()
        self.bullets.clear()
        self.enemy_bullets.clear()

    def boss(self) -> Enemy | None:
        for e in self.enemies:
            if e.is_boss:
                return e
        return None

    def _render_floor(self) -> pygame.Surface:
        surf = pygame.Surface((settings.ARENA_WIDTH, settings.ARENA_HEIGHT))
        g = settings.GRID_SIZE
        floor_tile = ASSETS.get("tiles", "floor", (g, g))
        if floor_tile is not None:
            for x in range(0, settings.ARENA_WIDTH, g):
                for y in range(0, settings.ARENA_HEIGHT, g):
                    surf.blit(floor_tile, (x, y))
        else:
            surf.fill(self.stage.floor if self.stage else settings.BG_COLOR)
            grid = self.stage.grid if self.stage else settings.GRID_COLOR
            for x in range(0, settings.ARENA_WIDTH, g):
                pygame.draw.line(surf, grid, (x, 0), (x, settings.ARENA_HEIGHT))
            for y in range(0, settings.ARENA_HEIGHT, g):
                pygame.draw.line(surf, grid, (0, y), (settings.ARENA_WIDTH, y))
        wall_tile = ASSETS.get("tiles", "wall", (settings.WALL_THICKNESS, settings.WALL_THICKNESS))
        for wall in self.walls:
            if wall_tile is not None:
                surf.set_clip(wall)
                for x in range(wall.left, wall.right, wall_tile.get_width()):
                    for y in range(wall.top, wall.bottom, wall_tile.get_height()):
                        surf.blit(wall_tile, (x, y))
                surf.set_clip(None)
            else:
                pygame.draw.rect(surf, self.stage.wall if self.stage else settings.WALL_COLOR, wall)
            pygame.draw.rect(surf, self.stage.wall_edge if self.stage else settings.WALL_EDGE_COLOR, wall, 3)
        return surf

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        surface.blit(self._floor, (-offset.x, -offset.y))
        for p in self.pickups:
            p.draw(surface, offset)
        for e in self.enemies:
            e.draw(surface, offset)
            draw_affix(e, surface, offset)
        self.player.draw(surface, offset)
        for b in self.bullets:
            b.draw(surface, offset)
        for b in self.enemy_bullets:
            b.draw(surface, offset)
        self.effects.draw(surface, offset)
        self.effects.draw_numbers(surface, offset)
