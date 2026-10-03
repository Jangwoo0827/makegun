"""Persistent player profile: meta currency (Cores), permanent upgrades, lifetime stats,
achievements, stage progress and weapon presets. Saved to profile.json; survives death."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import settings
from systems import storage

PRESET_SLOTS: int = 4
PROFILE_VERSION: int = 1


@dataclass(frozen=True)
class MetaUpgrade:
    meta_id: str
    name: str
    description: str
    max_level: int
    base_cost: int
    cost_growth: float
    effects: dict[str, float]
    start_money: int = 0
    start_parts: int = 0

    def cost(self, level: int) -> int:
        return int(self.base_cost * self.cost_growth ** level)


@dataclass(frozen=True)
class Achievement:
    ach_id: str
    name: str
    description: str
    stat: str
    goal: float
    reward: int


def _load_json(name: str) -> dict[str, Any]:
    with open(os.path.join(settings.DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def load_meta_upgrades() -> list[MetaUpgrade]:
    return [MetaUpgrade(k, d["name"], d["description"], int(d["max_level"]), int(d["base_cost"]),
                        float(d["cost_growth"]), {e: float(v) for e, v in d.get("effects", {}).items()},
                        int(d.get("start_money", 0)), int(d.get("start_parts", 0)))
            for k, d in _load_json("meta_upgrades.json").items()]


def load_achievements() -> list[Achievement]:
    return [Achievement(k, d["name"], d["description"], d["stat"], float(d["goal"]), int(d.get("reward", 0)))
            for k, d in _load_json("achievements.json").items()]


@dataclass
class RunResult:
    cores: int
    victory: bool
    new_achievements: list[Achievement] = field(default_factory=list)


class Profile:
    def __init__(self, path: str = settings.PROFILE_FILE) -> None:
        self.path = path
        self.meta_catalog: list[MetaUpgrade] = load_meta_upgrades()
        self.achievement_catalog: list[Achievement] = load_achievements()
        self.cores: int = 0
        self.meta_levels: dict[str, int] = {}
        self.stats: dict[str, float] = {}
        self.achievements: set[str] = set()
        self.unlocked_stage: int = 0          # highest stage index the player may start
        self.stage_best: dict[str, int] = {}  # stage_id -> best wave reached
        self.presets: list[dict[str, Any] | None] = [None] * PRESET_SLOTS
        self.load()

    # ------------------------------------------------------------- persistence
    def load(self) -> None:
        d = storage.read_json(self.path)
        if not isinstance(d, dict):
            return
        self.cores = int(d.get("cores", 0))
        self.meta_levels = {k: int(v) for k, v in d.get("meta_levels", {}).items()}
        self.stats = {k: float(v) for k, v in d.get("stats", {}).items()}
        self.achievements = set(d.get("achievements", []))
        self.unlocked_stage = int(d.get("unlocked_stage", 0))
        self.stage_best = {k: int(v) for k, v in d.get("stage_best", {}).items()}
        presets = list(d.get("presets", []))[:PRESET_SLOTS]
        self.presets = presets + [None] * (PRESET_SLOTS - len(presets))

    def save(self) -> None:
        data = {"version": PROFILE_VERSION, "cores": self.cores, "meta_levels": self.meta_levels,
                "stats": self.stats, "achievements": sorted(self.achievements),
                "unlocked_stage": self.unlocked_stage, "stage_best": self.stage_best, "presets": self.presets}
        storage.write_json(self.path, data)

    # ------------------------------------------------------------------- meta
    def meta_level(self, meta_id: str) -> int:
        return self.meta_levels.get(meta_id, 0)

    def meta_next_cost(self, meta: MetaUpgrade) -> int | None:
        level = self.meta_level(meta.meta_id)
        return None if level >= meta.max_level else meta.cost(level)

    def buy_meta(self, meta: MetaUpgrade) -> bool:
        cost = self.meta_next_cost(meta)
        if cost is None or self.cores < cost:
            return False
        self.cores -= cost
        self.meta_levels[meta.meta_id] = self.meta_level(meta.meta_id) + 1
        self.save()
        return True

    def meta_bonuses(self) -> tuple[dict[str, float], int, int]:
        """(PlayerStats effects, extra start money, extra start parts) from all meta levels."""
        effects: dict[str, float] = {}
        money = parts = 0
        for meta in self.meta_catalog:
            lvl = self.meta_level(meta.meta_id)
            if lvl <= 0:
                continue
            for k, v in meta.effects.items():
                effects[k] = effects.get(k, 0.0) + v * lvl
            money += meta.start_money * lvl
            parts += meta.start_parts * lvl
        return effects, money, parts

    # ------------------------------------------------------------ stats/achv
    def stat(self, key: str) -> float:
        return self.stats.get(key, 0.0)

    def add_stat(self, key: str, amount: float = 1.0) -> None:
        self.stats[key] = self.stat(key) + amount

    def max_stat(self, key: str, value: float) -> None:
        if value > self.stat(key):
            self.stats[key] = value

    def check_achievements(self, run_stats: dict[str, float] | None = None) -> list[Achievement]:
        """Unlock anything newly earned; grants Cores. Returns the newly unlocked list."""
        merged = dict(self.stats)
        for k, v in (run_stats or {}).items():
            merged[k] = max(merged.get(k, 0.0), v)
        new: list[Achievement] = []
        for a in self.achievement_catalog:
            if a.ach_id not in self.achievements and merged.get(a.stat, 0.0) >= a.goal:
                self.achievements.add(a.ach_id)
                self.cores += a.reward
                new.append(a)
        if new:
            self.save()
        return new

    # ----------------------------------------------------------------- stages
    def record_run_end(self, stage_index: int, stage_id: str, wave_reached: int, waves_cleared: int,
                       kills: int, bosses: int, victory: bool, stage_count: int) -> int:
        """Bank a finished run. Returns Cores earned (before achievement rewards)."""
        cores = waves_cleared * 2 + bosses * 15 + kills // 25
        cores = int(cores * (1.0 + 0.5 * stage_index))
        if victory:
            cores += 50 * (stage_index + 1)
            self.max_stat("stages_cleared", stage_index + 1)
            self.unlocked_stage = max(self.unlocked_stage, min(stage_count - 1, stage_index + 1))
        self.stage_best[stage_id] = max(self.stage_best.get(stage_id, 0), wave_reached)
        self.add_stat("runs")
        self.cores += cores
        self.save()
        return cores

    # ---------------------------------------------------------------- presets
    def save_preset(self, slot: int, name: str, part_ids: dict[str, str]) -> None:
        if 0 <= slot < PRESET_SLOTS:
            self.presets[slot] = {"name": name, "parts": dict(part_ids)}
            self.save()

    def preset(self, slot: int) -> dict[str, Any] | None:
        return self.presets[slot] if 0 <= slot < PRESET_SLOTS else None
