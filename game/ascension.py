"""Ascension (data/ascension.json): cumulative difficulty levels unlocked by clearing the final stage."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

import settings

MAX_ASCENSION: int = 10
CORE_BONUS_PER_LEVEL: float = 0.15


@dataclass(frozen=True)
class AscensionLevel:
    level: int
    name: str
    description: str
    effects: dict[str, float]


@dataclass
class AscensionMods:
    """Combined effect of every ascension level up to the chosen one."""
    level: int = 0
    enemy_hp: float = 1.0
    enemy_damage: float = 1.0
    enemy_speed: float = 1.0
    boss_hp: float = 1.0
    enemy_count: float = 1.0
    affix_add: float = 0.0
    shop_price: float = 1.0
    start_money: int = 0
    heal: float = 1.0
    names: list[str] = field(default_factory=list)

    @property
    def core_bonus(self) -> float:
        return 1.0 + CORE_BONUS_PER_LEVEL * self.level


@lru_cache(maxsize=1)
def ascension_levels() -> tuple[AscensionLevel, ...]:
    with open(os.path.join(settings.DATA_DIR, "ascension.json"), "r", encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    return tuple(AscensionLevel(int(d["level"]), d["name"], d["description"],
                                {k: float(v) for k, v in d["effects"].items()}) for d in raw)


def ascension_mods(level: int) -> AscensionMods:
    mods = AscensionMods(level=max(0, level))
    for lvl in ascension_levels():
        if lvl.level > level:
            continue
        mods.names.append(lvl.name)
        e = lvl.effects
        mods.enemy_hp += e.get("enemy_hp", 0.0)
        mods.enemy_damage += e.get("enemy_damage", 0.0)
        mods.enemy_speed += e.get("enemy_speed", 0.0)
        mods.boss_hp += e.get("boss_hp", 0.0)
        mods.enemy_count += e.get("enemy_count", 0.0)
        mods.affix_add += e.get("affix_add", 0.0)
        mods.shop_price += e.get("shop_price", 0.0)
        mods.start_money += int(e.get("start_money", 0))
        mods.heal += e.get("heal", 0.0)
    mods.heal = max(0.1, mods.heal)
    return mods
