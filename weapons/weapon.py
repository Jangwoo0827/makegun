"""Weapon: a combination of parts. Owns stat calculation and firing state."""
from __future__ import annotations

from dataclasses import dataclass

import settings
from entities.player_stats import PlayerStats
from weapons.weapon_parts import PART_ORDER, PartCategory, WeaponPart

# Default value of every numeric stat before the receiver's base is applied.
STAT_DEFAULTS: dict[str, float] = {
    "damage": 10.0, "fire_rate": 4.0, "magazine_size": 12.0, "reload_time": 1.4,
    "bullet_speed": 800.0, "bullet_count": 1.0, "spread": 4.0, "range": 600.0,
    "crit_chance": 0.0, "crit_damage": 0.0, "pierce": 0.0, "explosion_radius": 0.0,
    "knockback": 60.0, "lifesteal": 0.0, "chain": 0.0, "luck": 0.0, "split": 0.0,
    "ricochet": 0.0, "burn": 0.0, "move_speed_mult": 1.0, "slow": 0.0, "homing": 0.0,
}

BURST_INTERVAL: float = 0.07
CHARGE_MAX_MULT: float = 3.0
CHARGE_MIN_MULT: float = 0.6
EMERGENCY_RELOAD_MULT: float = 2.0  # when totally dry: slow reload of half a magazine


@dataclass
class WeaponStats:
    damage: float
    fire_rate: float
    magazine_size: int
    reload_time: float
    bullet_speed: float
    bullet_count: int
    spread: float
    range: float
    crit_chance: float
    crit_damage: float
    pierce: int
    explosion_radius: float
    knockback: float
    lifesteal: float
    chain: int
    luck: float
    split: int
    ricochet: int
    burn: float
    move_speed_mult: float
    slow: float
    homing: float
    fire_mode: str
    burst_count: int
    charge_time: float
    ammo_type: str

    @property
    def dps(self) -> float:
        """Approximate sustained DPS including reload downtime and average crits."""
        shot_damage = self.damage * self.bullet_count * (1 + self.crit_chance * (self.crit_damage - 1))
        if self.fire_mode == "charge":
            shot_damage *= CHARGE_MAX_MULT
            shots_per_sec = 1.0 / max(self.charge_time, 1.0 / self.fire_rate)
        else:
            shots_per_sec = self.fire_rate
        mag_time = self.magazine_size / max(shots_per_sec, 0.01)
        return shot_damage * shots_per_sec * mag_time / (mag_time + self.reload_time)


@dataclass
class ShotEvent:
    """One trigger pull worth of projectiles (bullet_count bullets)."""
    damage_mult: float = 1.0
    extra_pierce: int = 0


class Weapon:
    def __init__(self, name: str, parts: dict[PartCategory, WeaponPart], level: int = 1) -> None:
        missing = [c for c in PART_ORDER if c not in parts]
        if missing:
            raise ValueError(f"Weapon '{name}' missing parts: {[c.value for c in missing]}")
        self.name: str = name
        self.parts: dict[PartCategory, WeaponPart] = dict(parts)
        self.level: int = level
        self.stats: WeaponStats = self.compute_stats(None)
        self.ammo: int = self.stats.magazine_size
        self.reserve: int = self.stats.magazine_size * settings.RESERVE_MAGAZINES
        self.reload_timer: float = 0.0
        self.cooldown: float = 0.0
        self.burst_left: int = 0
        self.burst_timer: float = 0.0
        self.charge: float = 0.0
        self.emergency: bool = False
        self._trigger_was_down: bool = False

    # ------------------------------------------------------------------ stats
    def set_part(self, part: WeaponPart) -> None:
        self.parts[part.category] = part
        self.refresh(None)

    def part(self, category: PartCategory) -> WeaponPart:
        return self.parts[category]

    def compute_stats(self, player: PlayerStats | None) -> WeaponStats:
        """base(receiver) -> +add(all parts) -> *mult(all parts) -> *level -> *player."""
        values = dict(STAT_DEFAULTS)
        values.update(self.parts[PartCategory.RECEIVER].base)
        props: dict[str, object] = {"fire_mode": "auto", "burst_count": 1, "charge_time": 0.0,
                                    "ammo_type": "normal"}
        for category in PART_ORDER:
            part = self.parts[category]
            for key, v in part.add.items():
                values[key] = values.get(key, 0.0) + v
            props.update(part.props)
        for category in PART_ORDER:
            for key, v in self.parts[category].mult.items():
                values[key] = values.get(key, 0.0) * v

        values["damage"] *= 1.0 + (self.level - 1) * settings.WEAPON_UPGRADE_DAMAGE_PER_LEVEL
        crit_base = 0.0
        crit_mult_base = 1.0
        if player is not None:
            values["damage"] *= player.damage_multiplier
            values["fire_rate"] *= player.fire_rate_multiplier
            values["magazine_size"] *= player.magazine_multiplier
            values["reload_time"] *= player.reload_multiplier
            values["bullet_speed"] *= player.bullet_speed_multiplier
            values["range"] *= player.bullet_speed_multiplier
            values["bullet_count"] += player.bullet_count_bonus
            values["pierce"] += player.pierce_bonus
            values["lifesteal"] += player.lifesteal
            values["luck"] += player.luck
            values["spread"] *= player.spread_multiplier
            values["knockback"] *= player.knockback_multiplier
            values["burn"] += player.burn_bonus
            values["chain"] += player.chain_bonus
            values["ricochet"] += player.ricochet_bonus
            values["homing"] += player.homing_bonus
            values["slow"] += player.slow_bonus
            if values["explosion_radius"] > 0:
                values["explosion_radius"] += player.explosion_bonus
            crit_base = player.crit_chance
            crit_mult_base = player.crit_damage
        else:
            crit_base = settings.PLAYER_CRIT_CHANCE
            crit_mult_base = settings.PLAYER_CRIT_DAMAGE

        return WeaponStats(
            damage=max(1.0, values["damage"]),
            fire_rate=max(0.3, values["fire_rate"]),
            magazine_size=max(1, int(round(values["magazine_size"]))),
            reload_time=max(0.15, values["reload_time"]),
            bullet_speed=max(150.0, values["bullet_speed"]),
            bullet_count=max(1, int(round(values["bullet_count"]))),
            spread=max(0.0, values["spread"]),
            range=max(120.0, values["range"]),
            crit_chance=min(1.0, crit_base + values["crit_chance"]),
            crit_damage=crit_mult_base + values["crit_damage"],
            pierce=max(0, int(round(values["pierce"]))),
            explosion_radius=max(0.0, values["explosion_radius"]),
            knockback=values["knockback"],
            lifesteal=values["lifesteal"],
            chain=int(round(values["chain"])),
            luck=values["luck"],
            split=int(round(values["split"])),
            ricochet=int(round(values["ricochet"])),
            burn=values["burn"],
            move_speed_mult=max(0.4, values["move_speed_mult"]),
            slow=min(0.8, values["slow"]),
            homing=values["homing"],
            fire_mode=str(props["fire_mode"]),
            burst_count=max(1, int(props["burst_count"])),  # type: ignore[arg-type]
            charge_time=float(props["charge_time"]),  # type: ignore[arg-type]
            ammo_type=str(props["ammo_type"]),
        )

    def refresh(self, player: PlayerStats | None) -> None:
        old_mag = self.stats.magazine_size
        self.stats = self.compute_stats(player)
        if self.stats.magazine_size != old_mag:
            self.ammo = min(self.ammo, self.stats.magazine_size)

    @property
    def reserve_max(self) -> int:
        return self.stats.magazine_size * settings.RESERVE_MAGAZINES

    def refill(self, fraction: float = 1.0) -> None:
        self.reserve = min(self.reserve_max, self.reserve + int(self.reserve_max * fraction) + 1)
        if fraction >= 1.0:
            self.ammo = self.stats.magazine_size

    # ----------------------------------------------------------------- firing
    @property
    def reloading(self) -> bool:
        return self.reload_timer > 0.0

    @property
    def reload_progress(self) -> float:
        if not self.reloading:
            return 1.0
        total = self.stats.reload_time * (EMERGENCY_RELOAD_MULT if self.emergency else 1.0)
        return 1.0 - self.reload_timer / total

    @property
    def charge_ratio(self) -> float:
        if self.stats.charge_time <= 0:
            return 0.0
        return min(1.0, self.charge / self.stats.charge_time)

    def start_reload(self) -> bool:
        if self.reloading or self.ammo >= self.stats.magazine_size:
            return False
        if self.reserve <= 0:
            if self.ammo > 0:
                return False
            self.emergency = True  # never soft-lock the player with an empty gun
            self.reload_timer = self.stats.reload_time * EMERGENCY_RELOAD_MULT
        else:
            self.emergency = False
            self.reload_timer = self.stats.reload_time
        self.burst_left = 0
        self.charge = 0.0
        return True

    def cancel_actions(self) -> None:
        """Called when the weapon is holstered."""
        self.burst_left = 0
        self.charge = 0.0
        self._trigger_was_down = False
        if self.reloading:
            self.reload_timer = 0.0

    def _finish_reload(self) -> None:
        if self.emergency:
            self.emergency = False
            self.ammo = max(1, self.stats.magazine_size // 2)
            return
        need = self.stats.magazine_size - self.ammo
        take = min(need, self.reserve)
        self.ammo += take
        self.reserve -= take

    def _consume(self) -> bool:
        if self.ammo <= 0:
            return False
        self.ammo -= 1
        return True

    def update(self, dt: float, trigger_down: bool) -> list[ShotEvent]:
        """Advance timers and return the shots fired this frame."""
        shots: list[ShotEvent] = []
        pressed = trigger_down and not self._trigger_was_down
        released = (not trigger_down) and self._trigger_was_down
        self._trigger_was_down = trigger_down
        self.cooldown = max(0.0, self.cooldown - dt)

        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0.0:
                self.reload_timer = 0.0
                self._finish_reload()
            return shots

        s = self.stats
        mode = s.fire_mode
        interval = 1.0 / s.fire_rate

        if mode == "burst":
            if self.burst_left > 0:
                self.burst_timer -= dt
                if self.burst_timer <= 0.0:
                    if self._consume():
                        shots.append(ShotEvent())
                        self.burst_left -= 1
                        self.burst_timer = BURST_INTERVAL
                    else:
                        self.burst_left = 0
            elif trigger_down and self.cooldown <= 0.0 and self.ammo > 0:
                self.burst_left = s.burst_count
                self.burst_timer = 0.0
                self.cooldown = interval * s.burst_count
                if self._consume():
                    shots.append(ShotEvent())
                    self.burst_left -= 1
                    self.burst_timer = BURST_INTERVAL
        elif mode == "charge":
            if trigger_down and self.ammo > 0 and self.cooldown <= 0.0:
                self.charge = min(s.charge_time, self.charge + dt)
            if released and self.charge > 0.0:
                ratio = self.charge_ratio
                self.charge = 0.0
                if self._consume():
                    mult = CHARGE_MIN_MULT + (CHARGE_MAX_MULT - CHARGE_MIN_MULT) * ratio
                    shots.append(ShotEvent(damage_mult=mult, extra_pierce=2 if ratio >= 1.0 else 0))
                    self.cooldown = interval
        elif mode == "single":
            if pressed and self.cooldown <= 0.0 and self._consume():
                shots.append(ShotEvent())
                self.cooldown = interval
        else:  # auto
            if trigger_down and self.cooldown <= 0.0 and self._consume():
                shots.append(ShotEvent())
                self.cooldown = interval

        if self.ammo <= 0 and self.burst_left == 0 and self.cooldown <= interval:
            self.start_reload()
        return shots

    def describe_parts(self) -> str:
        return " / ".join(self.parts[c].name for c in PART_ORDER)
