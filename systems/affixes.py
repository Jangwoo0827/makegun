"""Elite affixes: random modifiers rolled onto regular enemies on later stages/waves."""
from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

import settings
from entities.enemy import Enemy, EnemyActions
from ui.fonts import get_font

Color = tuple[int, int, int]


@dataclass(frozen=True)
class AffixDef:
    affix_id: str
    label: str
    color: Color


AFFIXES: dict[str, AffixDef] = {
    "swift": AffixDef("swift", "SWIFT", (120, 255, 255)),
    "armored": AffixDef("armored", "ARMORED", (190, 190, 210)),
    "shielded": AffixDef("shielded", "SHIELDED", (100, 160, 255)),
    "giant": AffixDef("giant", "GIANT", (255, 140, 60)),
    "volatile": AffixDef("volatile", "VOLATILE", (255, 220, 60)),
    "splitting": AffixDef("splitting", "SPLITTING", (200, 90, 255)),
}
# Summons / bosses never get affixes.
NO_AFFIX_TYPES: frozenset[str] = frozenset({"mini", "drone"})


def roll_affix(enemy: Enemy, chance: float) -> None:
    if enemy.is_boss or enemy.enemy_type in NO_AFFIX_TYPES or random.random() >= chance:
        return
    apply_affix(enemy, random.choice(list(AFFIXES)))


def apply_affix(enemy: Enemy, affix_id: str) -> None:
    enemy.affix = affix_id
    enemy.reward = int(enemy.reward * settings.AFFIX_REWARD_MULT)
    if affix_id == "swift":
        enemy.base_speed *= 1.5
    elif affix_id == "armored":
        enemy.armor = min(0.6, enemy.armor + 0.35)
    elif affix_id == "shielded":
        enemy.shield_max = enemy.max_hp * 0.6
        enemy.shield = enemy.shield_max
    elif affix_id == "giant":
        enemy.max_hp *= 2.5
        enemy.radius *= 1.4
        enemy.damage *= 1.4
        enemy.base_speed *= 0.85
    elif affix_id == "volatile":
        enemy.max_hp *= 1.2
    elif affix_id == "splitting":
        enemy.max_hp *= 1.2
    enemy.hp = enemy.max_hp
    enemy.speed = enemy.base_speed


def affix_death_actions(enemy: Enemy) -> EnemyActions:
    actions = EnemyActions()
    if enemy.affix == "volatile":
        actions.explosions.append((pygame.Vector2(enemy.pos), 90.0 + enemy.radius, enemy.damage * 1.5))
    elif enemy.affix == "splitting":
        actions.summons.extend(["mini", "mini"])
    return actions


def draw_affix(enemy: Enemy, surface: pygame.Surface, offset: pygame.Vector2) -> None:
    if enemy.affix is None:
        return
    d = AFFIXES[enemy.affix]
    p = enemy.pos - offset
    pygame.draw.circle(surface, d.color, p, enemy.radius + 5, 2)
    if enemy.shield > 0:
        pygame.draw.circle(surface, (120, 180, 255), p, enemy.radius + 9,
                           max(1, int(4 * enemy.shield / max(1.0, enemy.shield_max))))
    img = get_font(11, bold=True).render(d.label, True, d.color)
    surface.blit(img, img.get_rect(center=(int(p.x), int(p.y - enemy.radius - 18))))
