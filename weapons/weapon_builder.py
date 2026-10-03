"""Builds Weapon objects from part ids and provides starter / blueprint presets."""
from __future__ import annotations

from dataclasses import dataclass

from weapons.weapon import Weapon
from weapons.weapon_data import PartLibrary
from weapons.weapon_parts import PART_ORDER, PartCategory


@dataclass(frozen=True)
class WeaponPreset:
    name: str
    description: str
    part_ids: dict[PartCategory, str]


def _preset(name: str, desc: str, r: str, b: str, m: str, t: str, a: str, mod: str = "no_modifier") -> WeaponPreset:
    return WeaponPreset(name, desc, {
        PartCategory.RECEIVER: r, PartCategory.BARREL: b, PartCategory.MAGAZINE: m,
        PartCategory.TRIGGER: t, PartCategory.AMMO: a, PartCategory.MODIFIER: mod,
    })


STARTER_PRESETS: tuple[WeaponPreset, ...] = (
    _preset("Sidearm", "Balanced pistol. Click to fire.",
            "pistol_receiver", "standard_barrel", "small_magazine", "single_trigger", "normal_ammo"),
    _preset("Sprayer", "Fast SMG. Hold to spray.",
            "smg_receiver", "short_barrel", "small_magazine", "auto_trigger", "normal_ammo"),
    _preset("Marksman", "Hard-hitting rifle for careful aim.",
            "rifle_receiver", "standard_barrel", "small_magazine", "single_trigger", "normal_ammo"),
    _preset("Scattergun", "Shotgun for close-range brawling.",
            "shotgun_receiver", "short_barrel", "small_magazine", "single_trigger", "normal_ammo"),
)

# Showcase builds from the design doc; shown in the editor once all parts are owned.
BLUEPRINTS: tuple[WeaponPreset, ...] = (
    _preset("Hyper SMG", "Low damage, extreme fire rate, huge magazine.",
            "smg_receiver", "short_barrel", "drum_magazine", "rapid_trigger", "normal_ammo"),
    _preset("Pierce Rifle", "High damage that punches through lines of enemies.",
            "rifle_receiver", "long_barrel", "extended_magazine", "single_trigger", "ap_ammo"),
    _preset("Boom Shotgun", "Explosive pellets. Group enemies, then fire.",
            "shotgun_receiver", "heavy_barrel", "drum_magazine", "rapid_trigger", "explosive_ammo"),
)


class WeaponBuilder:
    def __init__(self, library: PartLibrary) -> None:
        self.library = library

    def build(self, part_ids: dict[PartCategory, str], name: str | None = None) -> Weapon:
        parts = {}
        for category in PART_ORDER:
            pid = part_ids.get(category)
            parts[category] = self.library.get(pid) if pid else self.library.default_for(category)
        weapon = Weapon(name or "Custom", parts)
        if name is None:
            weapon.name = self.auto_name(weapon)
        return weapon

    def build_preset(self, preset: WeaponPreset) -> Weapon:
        return self.build(preset.part_ids, preset.name)

    def clone(self, weapon: Weapon) -> Weapon:
        copy = Weapon(weapon.name, weapon.parts, weapon.level)
        copy.evolution = weapon.evolution
        return copy

    @staticmethod
    def auto_name(weapon: Weapon) -> str:
        evo = weapon.active_evolution()
        if evo is not None:
            return evo.name
        receiver = weapon.part(PartCategory.RECEIVER).name.replace(" Receiver", "")
        ammo = weapon.part(PartCategory.AMMO).name
        trig = weapon.part(PartCategory.TRIGGER).name
        prefix = "" if ammo == "Normal" else ammo + " "
        return f"{prefix}{trig} {receiver}"
