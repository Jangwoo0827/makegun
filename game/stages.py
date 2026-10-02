"""Stage definitions (data/stages.json): a run is one stage with a fixed number of waves."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import settings

Color = tuple[int, int, int]


@dataclass(frozen=True)
class StageData:
    index: int
    stage_id: str
    name: str
    subtitle: str
    waves: int
    hp_mult: float
    damage_mult: float
    reward_mult: float
    pool_offset: int
    affix_chance: float
    bosses: dict[int, tuple[str, ...]]
    floor: Color
    grid: Color
    wall: Color
    wall_edge: Color
    obstacles: tuple[tuple[int, int, int, int], ...]

    def bosses_for(self, wave: int) -> tuple[str, ...]:
        return self.bosses.get(wave, ())

    @property
    def number(self) -> int:
        return self.index + 1


def _color(raw: list[int]) -> Color:
    return (int(raw[0]), int(raw[1]), int(raw[2]))


def load_stages(path: str | None = None) -> list[StageData]:
    path = path or os.path.join(settings.DATA_DIR, "stages.json")
    with open(path, "r", encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    stages: list[StageData] = []
    for i, d in enumerate(raw):
        stages.append(StageData(
            index=i, stage_id=d["id"], name=d["name"], subtitle=d.get("subtitle", ""),
            waves=int(d["waves"]), hp_mult=float(d["hp_mult"]), damage_mult=float(d["damage_mult"]),
            reward_mult=float(d.get("reward_mult", 1.0)), pool_offset=int(d.get("pool_offset", 0)),
            affix_chance=float(d.get("affix_chance", 0.0)),
            bosses={int(k): tuple(v) for k, v in d.get("bosses", {}).items()},
            floor=_color(d["floor"]), grid=_color(d["grid"]), wall=_color(d["wall"]),
            wall_edge=_color(d["wall_edge"]),
            obstacles=tuple(tuple(int(x) for x in o) for o in d["obstacles"]),  # type: ignore[misc]
        ))
    if not stages:
        raise ValueError("stages.json defines no stages")
    return stages
