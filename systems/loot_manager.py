"""Decides what enemies drop."""
from __future__ import annotations

import random

import pygame

from entities.enemy import Enemy
from entities.pickup import Pickup, PickupKind
from weapons.weapon_data import PartLibrary

HEALTH_CHANCE: float = 0.05
AMMO_CHANCE: float = 0.06
BUFF_CHANCE: float = 0.025
PART_CHANCE: dict[str, float] = {"normal": 0.008, "fast": 0.01, "tank": 0.03, "shooter": 0.015,
                                 "elite": 0.5, "boss": 1.0}
BUFF_TYPES: tuple[str, ...] = ("damage", "fire_rate", "speed")


class LootManager:
    def __init__(self, library: PartLibrary) -> None:
        self.library = library

    def roll_drops(self, enemy: Enemy, luck: float, owned: set[str], wave: int) -> list[Pickup]:
        drops: list[Pickup] = []
        luck_mult = 1.0 + max(0.0, luck)
        pos = enemy.pos

        def jitter() -> pygame.Vector2:
            return pos + pygame.Vector2(random.uniform(-14, 14), random.uniform(-14, 14))

        money = int(round(enemy.reward * luck_mult))
        coins = 1 if money < 40 else min(8, money // 25)
        for i in range(coins):
            share = money // coins + (money % coins if i == 0 else 0)
            drops.append(Pickup(PickupKind.MONEY, jitter(), value=share))

        if random.random() < HEALTH_CHANCE * luck_mult:
            drops.append(Pickup(PickupKind.HEALTH, jitter(), value=20))
        if random.random() < AMMO_CHANCE * luck_mult:
            drops.append(Pickup(PickupKind.AMMO, jitter(), value=0.5))
        if random.random() < BUFF_CHANCE * luck_mult:
            drops.append(Pickup(PickupKind.BUFF, jitter(), buff=random.choice(BUFF_TYPES)))
        if random.random() < PART_CHANCE.get(enemy.enemy_type, 0.01) * luck_mult:
            bonus = 1.0 if enemy.is_boss else (0.5 if enemy.enemy_type == "elite" else 0.0)
            part = self.library.random_part(owned, wave, bonus)
            if part is not None:
                drops.append(Pickup(PickupKind.PART, jitter(), part_id=part.part_id))
            else:
                drops.append(Pickup(PickupKind.MONEY, jitter(), value=100))
        if enemy.is_boss:
            drops.append(Pickup(PickupKind.HEALTH, jitter(), value=50))
        return drops
