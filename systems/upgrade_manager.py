"""Roguelite upgrades loaded from data/upgrades.json."""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass

import settings
from entities.player_stats import PlayerStats
from weapons.weapon_data import rarity_weight
from weapons.weapon_parts import Rarity


@dataclass(frozen=True)
class Upgrade:
    upgrade_id: str
    name: str
    description: str
    rarity: Rarity
    effects: dict[str, float]


class UpgradeManager:
    def __init__(self, path: str | None = None) -> None:
        path = path or os.path.join(settings.DATA_DIR, "upgrades.json")
        with open(path, "r", encoding="utf-8") as f:
            raw: dict[str, dict] = json.load(f)
        valid = set(PlayerStats.__dataclass_fields__)
        self.upgrades: list[Upgrade] = []
        for uid, d in raw.items():
            effects = {k: float(v) for k, v in d["effects"].items()}
            bad = set(effects) - valid
            if bad:
                raise KeyError(f"Upgrade '{uid}' has unknown effect keys: {bad}")
            self.upgrades.append(Upgrade(uid, d["name"], d["description"], Rarity(d["rarity"]), effects))

    def roll_choices(self, wave: int, count: int = 3, luck: float = 0.0) -> list[Upgrade]:
        pool = list(self.upgrades)
        choices: list[Upgrade] = []
        for _ in range(min(count, len(pool))):
            weights = [rarity_weight(u.rarity, wave, luck * 0.5) for u in pool]
            pick = random.choices(pool, weights=weights, k=1)[0]
            pool.remove(pick)
            choices.append(pick)
        return choices

    @staticmethod
    def apply(upgrade: Upgrade, stats: PlayerStats) -> None:
        stats.apply_effects(upgrade.effects)
