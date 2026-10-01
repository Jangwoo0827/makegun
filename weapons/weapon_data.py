"""Loads weapon part data from JSON into a queryable library."""
from __future__ import annotations

import json
import os
import random

from settings import DATA_DIR, RARITY_WEIGHTS
from weapons.weapon_parts import PART_ORDER, PartCategory, Rarity, WeaponPart


class PartLibrary:
    """All weapon parts known to the game, indexed by id and category."""

    def __init__(self, path: str | None = None) -> None:
        self.path: str = path or os.path.join(DATA_DIR, "weapons.json")
        self.parts: dict[str, WeaponPart] = {}
        self.by_category: dict[PartCategory, list[WeaponPart]] = {c: [] for c in PART_ORDER}
        self._load()

    def _load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            raw: dict[str, dict[str, dict]] = json.load(f)
        for category in PART_ORDER:
            for part_id, part_raw in raw.get(category.value, {}).items():
                part = WeaponPart.from_dict(part_id, category, part_raw)
                self.parts[part_id] = part
                self.by_category[category].append(part)
        for parts in self.by_category.values():
            parts.sort(key=lambda p: (p.rarity.tier, p.price))
        for category, parts in self.by_category.items():
            if not parts:
                raise ValueError(f"weapons.json has no parts for category '{category.value}'")

    def get(self, part_id: str) -> WeaponPart:
        return self.parts[part_id]

    def default_for(self, category: PartCategory) -> WeaponPart:
        return self.by_category[category][0]

    def starter_ids(self) -> set[str]:
        """Parts every run begins with: all free COMMON parts."""
        return {p.part_id for p in self.parts.values() if p.rarity == Rarity.COMMON and p.price == 0}

    def random_part(self, exclude: set[str], wave: int, rarity_bonus: float = 0.0) -> WeaponPart | None:
        """Pick a random part not in `exclude`, weighted toward higher rarity on later waves."""
        candidates = [p for p in self.parts.values() if p.part_id not in exclude]
        if not candidates:
            return None
        weights = [rarity_weight(p.rarity, wave, rarity_bonus) for p in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]


def rarity_weight(rarity: Rarity, wave: int, bonus: float = 0.0) -> float:
    """Base rarity weight, shifted toward rare tiers as waves progress."""
    base = RARITY_WEIGHTS[rarity.value]
    shift = 1.0 + (wave * 0.08 + bonus) * rarity.tier
    return base * shift
