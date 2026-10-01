"""Wave composition, difficulty scaling and wave lifecycle."""
from __future__ import annotations

import random
from enum import Enum, auto

import settings
from entities.enemy import WaveScaling
from systems.spawn_manager import SpawnManager


class WavePhase(Enum):
    COUNTDOWN = auto()
    ACTIVE = auto()
    CLEARED = auto()


def wave_scaling(wave: int) -> WaveScaling:
    n = wave - 1
    return WaveScaling(hp=1.0 + 0.14 * n + 0.004 * n * n, damage=1.0 + 0.07 * n,
                       speed=min(1.45, 1.0 + 0.02 * n))


def is_boss_wave(wave: int) -> bool:
    return wave > 0 and wave % settings.BOSS_WAVE_INTERVAL == 0


def boss_for_wave(wave: int) -> str:
    """Bosses alternate: THE GUNNER on waves 10, 30, ... and THE BROODMOTHER on 20, 40, ..."""
    return "boss" if (wave // settings.BOSS_WAVE_INTERVAL) % 2 == 1 else "broodmother"


def build_wave(wave: int) -> list[str]:
    """Return the ordered list of enemy types for a wave."""
    count = 6 + int(wave * 2.2)
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
    if is_boss_wave(wave):
        enemies = enemies[: count // 2]
        enemies.insert(min(3, len(enemies)), boss_for_wave(wave))
    return enemies


class WaveManager:
    def __init__(self, spawner: SpawnManager) -> None:
        self.spawner = spawner
        self.wave: int = 0
        self.phase: WavePhase = WavePhase.CLEARED
        self.countdown: float = 0.0
        self.total: int = 0
        self.killed: int = 0

    def start_next_wave(self) -> None:
        self.wave += 1
        queue = build_wave(self.wave)
        self.total = len(queue)
        self.killed = 0
        interval = max(0.18, settings.SPAWN_INTERVAL - self.wave * 0.012)
        self.spawner.start(queue, wave_scaling(self.wave), interval)
        self.phase = WavePhase.COUNTDOWN
        self.countdown = settings.WAVE_START_DELAY

    @property
    def is_boss_wave(self) -> bool:
        return is_boss_wave(self.wave)

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
