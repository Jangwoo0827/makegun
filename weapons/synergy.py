"""Part synergies (data/synergies.json): bonus stats when specific parts are combined."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

import settings


@dataclass(frozen=True)
class Synergy:
    synergy_id: str
    name: str
    description: str
    requires: tuple[frozenset[str], ...]  # need one part id from each set
    add: dict[str, float]
    mult: dict[str, float]

    def matches(self, part_ids: set[str]) -> bool:
        return all(part_ids & group for group in self.requires)

    def missing(self, part_ids: set[str]) -> int:
        return sum(1 for group in self.requires if not part_ids & group)


@lru_cache(maxsize=1)
def all_synergies() -> tuple[Synergy, ...]:
    path = os.path.join(settings.DATA_DIR, "synergies.json")
    with open(path, "r", encoding="utf-8") as f:
        raw: dict = json.load(f)
    out: list[Synergy] = []
    for sid, d in raw.items():
        if sid.startswith("_"):
            continue
        out.append(Synergy(sid, d["name"], d["description"],
                           tuple(frozenset(group) for group in d["requires"]),
                           {k: float(v) for k, v in d.get("add", {}).items()},
                           {k: float(v) for k, v in d.get("mult", {}).items()}))
    return tuple(out)


def active_synergies(part_ids: Iterable[str]) -> list[Synergy]:
    ids = set(part_ids)
    return [s for s in all_synergies() if s.matches(ids)]


def near_synergies(part_ids: Iterable[str]) -> list[Synergy]:
    """Synergies one part away from activating (for editor hints)."""
    ids = set(part_ids)
    return [s for s in all_synergies() if s.missing(ids) == 1]
