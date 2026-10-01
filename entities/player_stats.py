"""Run-wide player stats. Upgrades and buffs modify these values."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace

import settings


@dataclass
class PlayerStats:
    max_hp: float = settings.PLAYER_MAX_HP
    move_speed: float = settings.PLAYER_MOVE_SPEED
    damage_multiplier: float = settings.PLAYER_DAMAGE_MULTIPLIER
    fire_rate_multiplier: float = settings.PLAYER_FIRE_RATE_MULTIPLIER
    crit_chance: float = settings.PLAYER_CRIT_CHANCE
    crit_damage: float = settings.PLAYER_CRIT_DAMAGE
    magazine_multiplier: float = 1.0
    reload_multiplier: float = 1.0
    bullet_speed_multiplier: float = 1.0
    move_speed_multiplier: float = 1.0
    bullet_count_bonus: int = 0
    pierce_bonus: int = 0
    lifesteal: float = 0.0
    luck: float = 0.0
    regen: float = 0.0

    def apply_effects(self, effects: dict[str, float]) -> None:
        """Additively apply an upgrade's effect dict. Unknown keys raise KeyError."""
        valid = {f.name for f in fields(self)}
        for key, value in effects.items():
            if key not in valid:
                raise KeyError(f"Unknown player stat '{key}'")
            current = getattr(self, key)
            new_value = current + value
            if isinstance(current, int) and not isinstance(current, bool):
                new_value = int(round(new_value))
            setattr(self, key, new_value)
        self.max_hp = max(10.0, self.max_hp)
        self.reload_multiplier = max(0.2, self.reload_multiplier)

    def copy(self) -> "PlayerStats":
        return replace(self)
