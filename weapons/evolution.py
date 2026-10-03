"""Weapon evolutions (data/evolutions.json): a maxed-out synergy weapon can evolve into a named legend."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

import settings
from weapons.synergy import active_synergies


@dataclass(frozen=True)
class Evolution:
    synergy_id: str  # the synergy that must be active
    name: str
    add: dict[str, float]
    mult: dict[str, float]


@lru_cache(maxsize=1)
def all_evolutions() -> dict[str, Evolution]:
    with open(os.path.join(settings.DATA_DIR, "evolutions.json"), "r", encoding="utf-8") as f:
        raw: dict = json.load(f)
    return {sid: Evolution(sid, d["name"], {k: float(v) for k, v in d.get("add", {}).items()},
                           {k: float(v) for k, v in d.get("mult", {}).items()})
            for sid, d in raw.items()}


def available_evolution(part_ids: Iterable[str]) -> Evolution | None:
    """The evolution unlocked by the weapon's first active synergy that has one."""
    evos = all_evolutions()
    for syn in active_synergies(part_ids):
        if syn.synergy_id in evos:
            return evos[syn.synergy_id]
    return None
