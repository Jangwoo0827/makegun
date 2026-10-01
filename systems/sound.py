"""Sound effects. Loads assets/sounds/<name>.wav if present, otherwise synthesizes tones.

The game runs fine with no audio device: every call silently no-ops on failure.
"""
from __future__ import annotations

import os
import random
from array import array

import pygame

import settings

SAMPLE_RATE: int = 22050

# name: (start_freq, end_freq, duration, volume, noise_amount)
SYNTH_DEFS: dict[str, tuple[float, float, float, float, float]] = {
    "shoot": (900.0, 300.0, 0.06, 0.22, 0.25),
    "hit": (300.0, 180.0, 0.05, 0.25, 0.5),
    "enemy_die": (260.0, 60.0, 0.18, 0.3, 0.6),
    "explosion": (120.0, 30.0, 0.35, 0.45, 0.9),
    "pickup": (700.0, 1300.0, 0.08, 0.25, 0.0),
    "hurt": (200.0, 90.0, 0.2, 0.4, 0.4),
    "reload": (500.0, 650.0, 0.07, 0.2, 0.1),
    "click": (1000.0, 1000.0, 0.03, 0.2, 0.0),
    "buy": (600.0, 1200.0, 0.15, 0.3, 0.0),
    "wave": (300.0, 900.0, 0.4, 0.3, 0.0),
    "boss": (80.0, 60.0, 0.8, 0.5, 0.3),
}


class SoundManager:
    def __init__(self) -> None:
        self.enabled: bool = True
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._cooldowns: dict[str, int] = {}
        self.available: bool = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(24)
            self.available = True
        except pygame.error:
            self.available = False
            return
        for name, params in SYNTH_DEFS.items():
            path = os.path.join(settings.SOUND_DIR, f"{name}.wav")
            try:
                if os.path.exists(path):
                    self.sounds[name] = pygame.mixer.Sound(path)
                else:
                    self.sounds[name] = self._synth(*params)
            except (pygame.error, ValueError):
                continue

    def _synth(self, f0: float, f1: float, duration: float, volume: float, noise: float) -> pygame.mixer.Sound:
        n = int(SAMPLE_RATE * duration)
        buf = array("h")
        phase = 0.0
        channels = (pygame.mixer.get_init() or (SAMPLE_RATE, -16, 1))[2]
        for i in range(n):
            t = i / n
            freq = f0 + (f1 - f0) * t
            phase += freq / SAMPLE_RATE
            tone = 1.0 if (phase % 1.0) < 0.5 else -1.0
            sample = tone * (1 - noise) + random.uniform(-1, 1) * noise
            env = (1 - t) ** 2 * min(1.0, i / 40)
            v = int(sample * env * volume * 32767)
            for _ in range(channels):
                buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name: str, min_interval_ms: int = 30) -> None:
        if not (self.enabled and self.available):
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        now = pygame.time.get_ticks()
        if now - self._cooldowns.get(name, -10_000) < min_interval_ms:
            return
        self._cooldowns[name] = now
        try:
            sound.play()
        except pygame.error:
            pass

