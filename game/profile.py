"""Persistent player profile: meta currency (Cores), permanent upgrades, lifetime stats,
achievements, stage progress and weapon presets. Saved to profile.json; survives death."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import settings
from game.ascension import MAX_ASCENSION
from systems import storage

PRESET_SLOTS: int = 4
CODEX_KINDS: tuple[str, ...] = ("parts", "enemies", "synergies", "evolutions")
HISTORY_SIZE: int = 20
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
        self.unlocked_characters: set[str] = {"gunner"}
        self.ascension_unlocked: int = 0   # highest ascension level the player may pick
        self.selected_ascension: int = 0
        #: codex: things the player has ever found ("parts", "enemies", "synergies", "evolutions")
        self.discovered: dict[str, set[str]] = {k: set() for k in CODEX_KINDS}
        #: most recent runs first, at most HISTORY_SIZE entries
        self.history: list[dict[str, Any]] = []
        self.tutorial_done: bool = False
        self.hints_seen: set[str] = set()
        self._dirty: bool = False
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
        self.unlocked_characters = set(d.get("unlocked_characters", ["gunner"])) | {"gunner"}
        self.ascension_unlocked = int(d.get("ascension_unlocked", 0))
        self.selected_ascension = min(int(d.get("selected_ascension", 0)), self.ascension_unlocked)
        raw_disc = d.get("discovered", {})
        self.discovered = {k: set(raw_disc.get(k, [])) for k in CODEX_KINDS}
        self.history = list(d.get("history", []))[:HISTORY_SIZE]
        self.tutorial_done = bool(d.get("tutorial_done", False))
        self.hints_seen = set(d.get("hints_seen", []))
        if "tutorial_done" not in d and self.stat("runs") > 0:  # returning players skip the tutorial
            self.tutorial_done = True
            self.hints_seen = {"intermission", "editor", "shop", "wave_clear"}
        presets = list(d.get("presets", []))[:PRESET_SLOTS]
        self.presets = presets + [None] * (PRESET_SLOTS - len(presets))

    def save(self) -> None:
        data = {"version": PROFILE_VERSION, "cores": self.cores, "meta_levels": self.meta_levels,
                "stats": self.stats, "achievements": sorted(self.achievements),
                "unlocked_stage": self.unlocked_stage, "stage_best": self.stage_best, "presets": self.presets,
                "unlocked_characters": sorted(self.unlocked_characters),
                "ascension_unlocked": self.ascension_unlocked, "selected_ascension": self.selected_ascension,
                "discovered": {k: sorted(v) for k, v in self.discovered.items()}, "history": self.history,
                "tutorial_done": self.tutorial_done, "hints_seen": sorted(self.hints_seen)}
        self._dirty = False
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
    # ------------------------------------------------------------------ codex
    def discover(self, kind: str, item: str) -> bool:
        """Mark something as found. Returns True the first time."""
        bucket = self.discovered.setdefault(kind, set())
        if item in bucket:
            return False
        bucket.add(item)
        self._dirty = True
        return True

    def reset_tutorial(self) -> None:
        self.tutorial_done = False
        self.hints_seen.clear()
        self.save()

    def save_if_dirty(self) -> None:
        if self._dirty:
            self.save()

    def add_history(self, entry: dict[str, Any]) -> None:
        self.history.insert(0, entry)
        del self.history[HISTORY_SIZE:]

    def record_run_end(self, stage_index: int, stage_id: str, wave_reached: int, waves_cleared: int,
                       kills: int, bosses: int, victory: bool, stage_count: int, mode: str = "normal",
                       ascension: int = 0, core_bonus: float = 1.0, run_time: float = 0.0) -> int:
        """Bank a finished run. Returns Cores earned (before achievement rewards)."""
        cores = waves_cleared * 2 + bosses * 15 + kills // 25
        cores = int(cores * (1.0 + 0.5 * stage_index))
        if mode == "endless":
            self.max_stat("endless_best", wave_reached)
        elif mode == "bossrush":
            if victory:
                cores += 150
                self.add_stat("bossrush_clears")
                best = self.stat("best_bossrush_time")
                if best <= 0 or run_time < best:
                    self.stats["best_bossrush_time"] = run_time
        elif victory:
            cores += 50 * (stage_index + 1)
            self.max_stat("stages_cleared", stage_index + 1)
            self.unlocked_stage = max(self.unlocked_stage, min(stage_count - 1, stage_index + 1))
            if stage_index == stage_count - 1:  # final stage: next ascension level
                self.max_stat("best_ascension_clear", ascension)
                self.ascension_unlocked = max(self.ascension_unlocked, min(MAX_ASCENSION, ascension + 1))
        cores = int(cores * core_bonus)
        self.stage_best[stage_id] = max(self.stage_best.get(stage_id, 0), wave_reached)
        self.add_stat("runs")
        self.cores += cores
        self.save()
        return cores

    # ------------------------------------------------------------- characters
    def buy_character(self, char_id: str, cost: int) -> bool:
        if char_id in self.unlocked_characters or self.cores < cost:
            return False
        self.cores -= cost
        self.unlocked_characters.add(char_id)
        self.max_stat("characters_unlocked", len(self.unlocked_characters))
        self.save()
        return True

    @property
    def modes_unlocked(self) -> bool:
        """ENDLESS / BOSS RUSH open up after clearing THE CORE (stage 5)."""
        return self.stat("stages_cleared") >= 5

    # ---------------------------------------------------------------- presets
    def save_preset(self, slot: int, name: str, part_ids: dict[str, str]) -> None:
        if 0 <= slot < PRESET_SLOTS:
            self.presets[slot] = {"name": name, "parts": dict(part_ids)}
            self.save()

    def preset(self, slot: int) -> dict[str, Any] | None:
        return self.presets[slot] if 0 <= slot < PRESET_SLOTS else None
