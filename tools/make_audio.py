"""Generate all sound effects and music as WAV files (original, procedural - no third-party audio).

    python tools/make_audio.py

Writes assets/sounds/<effect>.wav and assets/music/<track>.wav. The game loads these automatically;
re-run after tweaking. Pure standard library (wave + array), deterministic output.
"""
from __future__ import annotations

import math
import os
import random
import sys
import wave
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUND_DIR = os.path.join(ROOT, "assets", "sounds")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")
SR = 22050
TAU = math.tau


# ---------------------------------------------------------------------------- primitives
def osc(kind: str, phase: float, duty: float = 0.5) -> float:
    p = phase % 1.0
    if kind == "sine":
        return math.sin(TAU * p)
    if kind == "square":
        return 1.0 if p < duty else -1.0
    if kind == "saw":
        return 2.0 * p - 1.0
    if kind == "tri":
        return 4.0 * abs(p - 0.5) - 1.0
    raise ValueError(kind)


def env(t: float, dur: float, attack: float = 0.005, decay_pow: float = 2.0) -> float:
    if t < attack:
        return t / attack
    x = (t - attack) / max(1e-6, dur - attack)
    return max(0.0, 1.0 - x) ** decay_pow


def tone(dur: float, f0: float, f1: float | None = None, kind: str = "square", vol: float = 0.5,
         duty: float = 0.5, attack: float = 0.004, decay_pow: float = 2.0, vibrato: float = 0.0) -> list[float]:
    """A pitch-sweeping oscillator note."""
    f1 = f0 if f1 is None else f1
    n = int(SR * dur)
    out, phase = [], 0.0
    for i in range(n):
        t = i / SR
        k = i / max(1, n - 1)
        f = f0 * (f1 / f0) ** k if f0 > 0 and f1 > 0 else f0 + (f1 - f0) * k
        if vibrato:
            f *= 1.0 + 0.01 * math.sin(TAU * vibrato * t)
        phase += f / SR
        out.append(osc(kind, phase, duty) * env(t, dur, attack, decay_pow) * vol)
    return out


def noise(dur: float, vol: float = 0.5, cutoff: float = 1.0, decay_pow: float = 2.0, attack: float = 0.002,
          seed: int = 1) -> list[float]:
    """Filtered white noise. cutoff 0..1 (one-pole low-pass amount)."""
    rnd = random.Random(seed)
    n = int(SR * dur)
    out, y = [], 0.0
    for i in range(n):
        y += (rnd.uniform(-1, 1) - y) * cutoff
        out.append(y * env(i / SR, dur, attack, decay_pow) * vol)
    return out


def mix(*tracks: list[float], offsets: tuple[float, ...] = ()) -> list[float]:
    offs = [int(o * SR) for o in offsets] + [0] * (len(tracks) - len(offsets))
    n = max(len(t) + o for t, o in zip(tracks, offs))
    out = [0.0] * n
    for t, o in zip(tracks, offs):
        for i, v in enumerate(t):
            out[i + o] += v
    return out


def lowpass(samples: list[float], amount: float) -> list[float]:
    out, y = [], 0.0
    for v in samples:
        y += (v - y) * amount
        out.append(y)
    return out


def write_wav(path: str, samples: list[float], gain: float = 1.0) -> None:
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = min(gain, 0.95 / peak) * 32767
    data = array("h", (int(max(-32767, min(32767, s * scale))) for s in samples))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


# ---------------------------------------------------------------------------- effects
def make_effects() -> dict[str, list[float]]:
    fx: dict[str, list[float]] = {}
    fx["shoot"] = mix(tone(0.07, 1400, 380, "square", 0.35, duty=0.25), noise(0.05, 0.35, 0.6, seed=2))
    fx["hit"] = mix(tone(0.05, 520, 260, "tri", 0.4), noise(0.04, 0.3, 0.35, seed=3))
    fx["enemy_die"] = mix(noise(0.22, 0.6, 0.25, decay_pow=1.6, seed=4), tone(0.18, 320, 70, "square", 0.3, duty=0.3))
    boom_low = tone(0.5, 110, 32, "sine", 0.9, decay_pow=1.4)
    fx["explosion"] = mix(boom_low, noise(0.55, 0.8, 0.12, decay_pow=1.3, seed=5), noise(0.15, 0.4, 0.8, seed=6))
    fx["pickup"] = mix(tone(0.06, 880, None, "square", 0.25, duty=0.25),
                       tone(0.09, 1320, None, "square", 0.25, duty=0.25), offsets=(0, 0.05))
    fx["hurt"] = mix(tone(0.22, 260, 110, "saw", 0.45, decay_pow=1.5), noise(0.12, 0.3, 0.3, seed=7))
    fx["reload"] = mix(noise(0.03, 0.4, 0.9, seed=8), noise(0.04, 0.5, 0.7, seed=9), tone(0.04, 900, 1100, "square", 0.15),
                       offsets=(0, 0.12, 0.13))
    fx["click"] = tone(0.03, 1200, 900, "square", 0.25, duty=0.2)
    fx["buy"] = mix(*[tone(0.09, f, None, "square", 0.22, duty=0.25) for f in (660, 880, 1320)],
                    offsets=(0, 0.06, 0.12))
    fx["wave"] = mix(*[tone(0.16, f, None, "tri", 0.4, vibrato=6) for f in (392, 523, 659, 784)],
                     offsets=(0, 0.1, 0.2, 0.3))
    fx["boss"] = mix(tone(1.1, 55, 50, "saw", 0.6, decay_pow=1.0, attack=0.05),
                     tone(1.1, 82, 74, "square", 0.3, duty=0.3, decay_pow=1.0, attack=0.05),
                     noise(1.0, 0.25, 0.05, decay_pow=1.0, attack=0.2, seed=10))
    fx["dash"] = mix(noise(0.16, 0.5, 0.5, decay_pow=1.2, attack=0.02, seed=11), tone(0.12, 300, 900, "sine", 0.2))
    fx["evolve"] = mix(*[tone(0.35, f, f * 1.01, "tri", 0.3, vibrato=7) for f in (262, 330, 392, 523, 659)],
                       offsets=(0, 0.08, 0.16, 0.24, 0.32))
    fx["slash"] = mix(noise(0.12, 0.6, 0.9, decay_pow=1.5, attack=0.01, seed=12), tone(0.1, 2200, 600, "saw", 0.15))
    fx["zap"] = mix(tone(0.12, 1800, 400, "square", 0.25, duty=0.1), noise(0.1, 0.3, 1.0, seed=13))
    return fx


# ---------------------------------------------------------------------------- music
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def freq(name: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[name] - 9 + (octave - 4) * 12) / 12)


def chord_tones(root: str, minor: bool) -> list[float]:
    r = NOTE[root]
    ints = (0, 3, 7) if minor else (0, 4, 7)
    names = list(NOTE)
    return [freq(names[(r + i) % 12], 4 + (r + i) // 12) for i in ints]


def drum_kick() -> list[float]:
    return tone(0.18, 140, 40, "sine", 0.9, decay_pow=1.8)


def drum_snare(seed: int) -> list[float]:
    return mix(noise(0.14, 0.55, 0.7, decay_pow=1.8, seed=seed), tone(0.08, 220, 180, "tri", 0.25))


def drum_hat(seed: int) -> list[float]:
    return noise(0.04, 0.22, 1.0, decay_pow=2.5, seed=seed)


def render_track(bpm: float, bars: int, progression: list[tuple[str, bool]], bass_oct: int, lead: list[int],
                 drums: str, arp_kind: str, lead_kind: str, intensity: float, seed: int) -> list[float]:
    """Loopable track: drums + bass + arpeggio + lead. `lead` = scale degrees per 8th note (-1 = rest)."""
    beat = 60.0 / bpm
    eighth = beat / 2
    total = int(SR * beat * 4 * bars)
    out = [0.0] * total
    rnd = random.Random(seed)

    def add(samples: list[float], at: float) -> None:
        start = int(at * SR)
        for i, v in enumerate(samples):
            j = (start + i) % total  # wrap so the loop seams cleanly
            out[j] += v

    for bar in range(bars):
        root, minor = progression[bar % len(progression)]
        tones_ = chord_tones(root, minor)
        bar_t = bar * beat * 4
        # drums
        for step in range(8):
            t = bar_t + step * eighth
            if drums == "calm":
                if step in (0, 5):
                    add(drum_kick(), t)
                if step == 4:
                    add([v * 0.6 for v in drum_snare(rnd.randrange(999))], t)
                if step % 2 == 1:
                    add([v * 0.6 for v in drum_hat(rnd.randrange(999))], t)
            else:
                if step in (0, 3, 4, 6) if drums == "boss" else step in (0, 4, 5):
                    add(drum_kick(), t)
                if step in (2, 6):
                    add(drum_snare(rnd.randrange(999)), t)
                add(drum_hat(rnd.randrange(999)), t)
                add(drum_hat(rnd.randrange(999)), t + eighth / 2)
        # bass: root on 8ths (driving) or quarters (calm)
        bf = tones_[0] / 2 ** (4 - bass_oct)
        step_len = eighth if drums != "calm" else beat
        for k in range(int(beat * 4 / step_len)):
            f = bf * (2 if (drums == "boss" and k % 2) else 1)
            add(tone(step_len * 0.9, f, None, "square", 0.32 * intensity, duty=0.4, decay_pow=0.8), bar_t + k * step_len)
        # arpeggio: 16ths over the chord
        sixteenth = beat / 4
        for k in range(16):
            f = tones_[k % 3] * (2 if k % 6 >= 3 else 1)
            add(tone(sixteenth * 0.8, f, None, arp_kind, 0.10 * intensity, duty=0.25, decay_pow=2.5), bar_t + k * sixteenth)
        # lead melody from a minor pentatonic over the root
        scale = [0, 3, 5, 7, 10, 12, 15]
        for k in range(8):
            deg = lead[(bar * 8 + k) % len(lead)]
            if deg < 0:
                continue
            semis = NOTE[root] + scale[deg % len(scale)]
            f = freq(list(NOTE)[semis % 12], 5 + semis // 12)
            add(tone(eighth * 0.95, f, None, lead_kind, 0.16 * intensity, duty=0.5, decay_pow=1.2, vibrato=5),
                bar_t + k * eighth)
    return lowpass(out, 0.55)


def make_music() -> dict[str, list[float]]:
    a_min = [("A", True), ("F", False), ("C", False), ("G", False)]
    d_min = [("D", True), ("A#", False), ("F", False), ("C", False)]
    e_min = [("E", True), ("C", False), ("D", False), ("B", True)]
    return {
        "menu": render_track(92, 8, a_min, 2, [0, -1, 2, -1, 3, 2, -1, -1, 4, -1, 3, 2, 0, -1, -1, -1],
                             "calm", "tri", "tri", 0.8, 21),
        "battle": render_track(138, 8, d_min, 2, [0, 2, 3, 2, 4, 3, 2, 0, 5, 4, 3, 2, 3, -1, 0, -1],
                               "battle", "square", "square", 1.0, 22),
        "boss": render_track(152, 8, e_min, 1, [5, 4, 5, 3, 4, 2, 3, 0, 6, 5, 4, 5, 3, 2, 1, 0],
                             "boss", "saw", "square", 1.1, 23),
    }


def main() -> int:
    only = set(sys.argv[1:])
    for name, samples in make_effects().items():
        if not only or name in only:
            write_wav(os.path.join(SOUND_DIR, f"{name}.wav"), samples)
            print("sfx  ", name)
    if not only or "music" in only:
        for name, samples in make_music().items():
            write_wav(os.path.join(MUSIC_DIR, f"{name}.wav"), samples, gain=0.8)
            print("music", name, f"{len(samples) / SR:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
