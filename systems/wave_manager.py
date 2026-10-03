"""Wave composition, difficulty scaling and wave lifecycle."""
from __future__ import annotations

import random
from enum import Enum, auto

import settings
from entities.enemy import WaveScaling
from game.ascension import AscensionMods
from game.stages import StageData
from systems.spawn_manager import SpawnManager


class WavePhase(Enum):
    COUNTDOWN = auto()
    ACTIVE = auto()
    CLEARED = auto()


def wave_scaling(wave: int) -> WaveScaling:
    n = wave - 1
    late = max(0, wave - settings.LATE_WAVE_START)
    return WaveScaling(hp=(1.0 + 0.14 * n + 0.004 * n * n) * settings.LATE_WAVE_HP_GROWTH ** late,
                       damage=(1.0 + settings.WAVE_DAMAGE_GROWTH * n) * settings.LATE_WAVE_DAMAGE_GROWTH ** late,
                       speed=min(1.45, 1.0 + 0.02 * n))


def is_boss_wave(wave: int) -> bool:
    return wave > 0 and wave % settings.BOSS_WAVE_INTERVAL == 0


def boss_for_wave(wave: int) -> str:
    """Bosses alternate: THE GUNNER on waves 10, 30, ... and THE BROODMOTHER on 20, 40, ..."""
    return "boss" if (wave // settings.BOSS_WAVE_INTERVAL) % 2 == 1 else "broodmother"


def stage_scaling(wave: int, stage: StageData | None) -> WaveScaling:
    sc = wave_scaling(wave)
    if stage is not None:
        sc.hp *= stage.hp_mult
        sc.damage *= stage.damage_mult
    return sc


def build_wave(wave: int, stage: StageData | None = None, count_mult: float = 1.0) -> list[str]:
    """Return the ordered list of enemy types for a wave.

    Later stages unlock enemy types earlier (pool_offset) and add a few extra enemies.
    """
    bosses = list(stage.bosses_for(wave)) if stage is not None else \
        ([boss_for_wave(wave)] if is_boss_wave(wave) else [])
    stage_index = stage.index if stage is not None else 0
    count = int((6 + int(wave * 2.2) + stage_index) * count_mult)
    if stage is not None and stage.mode == "bossrush":
        # each wave is a boss with a few escorts
        escorts = random.choices(["normal", "fast", "shooter", "charger"], k=int((2 + wave) * count_mult))
        return list(bosses) + escorts
    wave = wave + (stage.pool_offset if stage is not None else 0)  # pool/elite thresholds
    pool: list[tuple[str, float]] = [("normal", 10.0)]
    if wave >= 2:
        pool.append(("fast", 5.0 + wave * 0.3))
    if wave >= 3:
        pool.append(("shooter", 3.0 + wave * 0.25))
    if wave >= 5:
        pool.append(("tank", 2.0 + wave * 0.2))
    if wave >= 4:
        pool.append(("charger", 1.5 + wave * 0.15))
    if wave >= 6:
        pool.append(("bomber", 2.0 + wave * 0.15))
    if wave >= 7:
        pool.append(("splitter", 1.5 + wave * 0.12))
    if wave >= 8:
        pool.append(("sniper", 1.0 + wave * 0.1))
    if wave >= 9:
        pool.append(("healer", 0.8 + wave * 0.05))
    if wave >= 11:
        pool.append(("elite", 0.4 + wave * 0.03))
    if wave >= 12:
        pool.append(("summoner", 0.6 + wave * 0.05))
    types, weights = zip(*pool)
    enemies = random.choices(list(types), weights=list(weights), k=count)
    if wave % settings.ELITE_WAVE_INTERVAL == 0 and wave >= settings.ELITE_WAVE_INTERVAL * 2:
        for _ in range(1 + wave // 20):
            enemies.insert(random.randint(count // 3, count), "elite")
    elif wave == settings.ELITE_WAVE_INTERVAL:
        enemies.append("elite")  # first taste of an elite at wave 5
    if bosses:
        enemies = enemies[: count // 2]
        for i, boss in enumerate(bosses):
            enemies.insert(min(3 + i * 6, len(enemies)), boss)
    return enemies


class WaveManager:
    def __init__(self, spawner: SpawnManager, stage: StageData | None = None,
                 asc: AscensionMods | None = None) -> None:
        self.spawner = spawner
        self.stage = stage
        self.asc: AscensionMods = asc or AscensionMods()
        self.wave: int = 0
        self.phase: WavePhase = WavePhase.CLEARED
        self.countdown: float = 0.0
        self.total: int = 0
        self.killed: int = 0

    def start_next_wave(self) -> None:
        self.wave += 1
        queue = build_wave(self.wave, self.stage, self.asc.enemy_count)
        self.total = len(queue)
        self.killed = 0
        interval = max(0.18, settings.SPAWN_INTERVAL - self.wave * 0.012)
        scaling = stage_scaling(self.wave, self.stage)
        scaling.hp *= self.asc.enemy_hp
        scaling.damage *= self.asc.enemy_damage
        scaling.speed *= self.asc.enemy_speed
        self.spawner.start(queue, scaling, interval)
        # bosses scale with the stage more gently than regular enemies
        stage_hp = self.stage.hp_mult if self.stage is not None else 1.0
        self.spawner.boss_hp_mult = self.asc.boss_hp * stage_hp ** (settings.BOSS_STAGE_HP_EXPONENT - 1.0)
        if self.stage is not None:
            self.spawner.reward_mult = self.stage.reward_mult
            self.spawner.affix_chance = (self.stage.affix_chance + 0.01 * self.wave
                                         if self.stage.affix_chance > 0 else 0.0) + self.asc.affix_add
        self.phase = WavePhase.COUNTDOWN
        self.countdown = settings.WAVE_START_DELAY

    @property
    def is_boss_wave(self) -> bool:
        if self.stage is not None:
            return bool(self.stage.bosses_for(self.wave))
        return is_boss_wave(self.wave)

    @property
    def total_waves(self) -> int:
        return self.stage.waves if self.stage is not None else 0

    @property
    def is_final_wave(self) -> bool:
        return self.stage is not None and self.stage.waves > 0 and self.wave >= self.stage.waves

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.killed)

    @property
    def progress(self) -> float:
        return self.killed / self.total if self.total else 0.0

    def register_kill(self) -> None:
        self.killed += 1

    def register_extra(self, n: int = 1) -> None:
        """Summoned enemies count toward the wave total."""
        self.total += n

    def clear_reward(self) -> int:
        reward = settings.WAVE_CLEAR_BASE_REWARD + settings.WAVE_CLEAR_PER_WAVE * self.wave
        if self.is_boss_wave:
            reward *= 2
        if self.stage is not None:
            reward = int(reward * self.stage.reward_mult)
        return reward

    def update(self, dt: float, alive_count: int) -> bool:
        """Advance; returns True on the frame the wave is cleared."""
        if self.phase == WavePhase.COUNTDOWN:
            self.countdown -= dt
            if self.countdown <= 0:
                self.phase = WavePhase.ACTIVE
        elif self.phase == WavePhase.ACTIVE:
            if self.spawner.pending == 0 and alive_count == 0:
                self.phase = WavePhase.CLEARED
                return True
        return False
