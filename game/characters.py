"""Playable characters (data/characters.json), unlocked with cores."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

import settings

Color = tuple[int, int, int]
DEFAULT_CHARACTER: str = "gunner"


@dataclass(frozen=True)
class Character:
    char_id: str
    name: str
    description: str
    cost: int
    color: Color
    effects: dict[str, float]
    start_attachment: str | None = None


@lru_cache(maxsize=1)
def all_characters() -> tuple[Character, ...]:
    with open(os.path.join(settings.DATA_DIR, "characters.json"), "r", encoding="utf-8") as f:
        raw: dict = json.load(f)
    return tuple(Character(cid, d["name"], d["description"], int(d.get("cost", 0)),
                           (int(d["color"][0]), int(d["color"][1]), int(d["color"][2])),
                           {k: float(v) for k, v in d.get("effects", {}).items()},
                           d.get("start_attachment"))
                 for cid, d in raw.items())


def get_character(char_id: str) -> Character:
    for c in all_characters():
        if c.char_id == char_id:
            return c
    return all_characters()[0]
