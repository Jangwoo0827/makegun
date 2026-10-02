"""RunSession: everything that persists across waves within a single run."""
from __future__ import annotations

import pygame

import settings
from entities.player import Player
from entities.player_stats import PlayerStats
from game.stages import StageData
from systems.upgrade_manager import Upgrade, UpgradeManager
from weapons.weapon import Weapon
from weapons.weapon_builder import STARTER_PRESETS, WeaponBuilder, WeaponPreset
from weapons.weapon_data import PartLibrary
from weapons.weapon_parts import PartCategory


class RunSession:
    def __init__(self, library: PartLibrary, upgrades: UpgradeManager, starter: WeaponPreset,
                 stage: StageData) -> None:
        self.library = library
        self.stage: StageData = stage
        self.builder = WeaponBuilder(library)
        self.upgrade_manager = upgrades
        self.money: int = settings.STARTING_MONEY
        self.owned_parts: set[str] = library.starter_ids() | set(starter.part_ids.values())
        self.stats: PlayerStats = PlayerStats()
        self.slots_unlocked: int = 1
        first = self.builder.build_preset(starter)
        self.player: Player = Player(pygame.Vector2(settings.ARENA_WIDTH / 2, settings.ARENA_HEIGHT / 2),
                                     self.stats, [first])
        self.upgrades_taken: list[Upgrade] = []
        self.kills: int = 0
        self.wave_reached: int = 0
        self.money_earned: int = 0
        self.pending_upgrades: list[Upgrade] = []
        self.last_wave_reward: int = 0
        #: number of waves already completed when the run was (re)started from a save
        self.resume_wave: int = 0
        self.boss_kills: int = 0
        #: per-run counters used by achievements (see data/achievements.json)
        self.run_stats: dict[str, float] = {}
        self.run_recorded: bool = False

    def apply_meta(self, effects: dict[str, float], money: int, parts: int) -> None:
        """Permanent profile bonuses applied at the start of a run."""
        if effects:
            self.stats.apply_effects(effects)
        self.money += money
        for _ in range(parts):
            part = self.library.random_part(self.owned_parts, 3)
            if part is not None:
                self.owned_parts.add(part.part_id)
        self.player.hp = self.stats.max_hp
        self.player.refresh_weapons()

    def bump(self, key: str, value: float) -> None:
        """Track the max of a per-run stat."""
        if value > self.run_stats.get(key, 0.0):
            self.run_stats[key] = value

    @property
    def weapons(self) -> list[Weapon]:
        return self.player.weapons

    # ---------------------------------------------------------------- money
    def earn(self, amount: int) -> None:
        self.money += amount
        self.money_earned += amount

    def can_afford(self, cost: int) -> bool:
        return self.money >= cost

    def spend(self, cost: int) -> bool:
        if self.money < cost:
            return False
        self.money -= cost
        return True

    # ---------------------------------------------------------------- parts
    def own_part(self, part_id: str) -> bool:
        """Returns True if the part is new."""
        if part_id in self.owned_parts:
            return False
        self.owned_parts.add(part_id)
        return True

    def owned_in(self, category: PartCategory) -> list[str]:
        return [p.part_id for p in self.library.by_category[category] if p.part_id in self.owned_parts]

    # ---------------------------------------------------------------- slots
    def next_slot_price(self) -> int | None:
        if self.slots_unlocked >= settings.MAX_WEAPON_SLOTS:
            return None
        return settings.SLOT_PRICES[self.slots_unlocked]

    def unlock_slot(self) -> bool:
        price = self.next_slot_price()
        if price is None or not self.spend(price):
            return False
        self.slots_unlocked += 1
        new_weapon = self.builder.clone(self.player.weapon)
        new_weapon.level = 1
        new_weapon.name = self.builder.auto_name(new_weapon)
        self.player.weapons.append(new_weapon)
        self.player.refresh_weapons()
        new_weapon.refill(1.0)
        return True

    # ------------------------------------------------------------- upgrades
    def apply_upgrade(self, upgrade: Upgrade) -> None:
        old_max = self.stats.max_hp
        self.upgrade_manager.apply(upgrade, self.stats)
        if self.stats.max_hp > old_max:
            self.player.heal(self.stats.max_hp - old_max)
        self.upgrades_taken.append(upgrade)
        self.player.refresh_weapons()

    def weapon_upgrade_cost(self, weapon: Weapon) -> int:
        return int(settings.WEAPON_UPGRADE_BASE_COST * (1.45 ** (weapon.level - 1)))

    def upgrade_weapon(self, weapon: Weapon) -> bool:
        if weapon.level >= settings.WEAPON_MAX_LEVEL or not self.spend(self.weapon_upgrade_cost(weapon)):
            return False
        weapon.level += 1
        self.player.refresh_weapons()
        return True


def default_starter() -> WeaponPreset:
    return STARTER_PRESETS[0]
