"""Weapon part definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PartCategory(str, Enum):
    RECEIVER = "receiver"
    BARREL = "barrel"
    MAGAZINE = "magazine"
    TRIGGER = "trigger"
    AMMO = "ammo"
    MODIFIER = "modifier"

    @property
    def label(self) -> str:
        return self.value.capitalize()


PART_ORDER: tuple[PartCategory, ...] = (
    PartCategory.RECEIVER,
    PartCategory.BARREL,
    PartCategory.MAGAZINE,
    PartCategory.TRIGGER,
    PartCategory.AMMO,
    PartCategory.MODIFIER,
)


class Rarity(str, Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

    @property
    def tier(self) -> int:
        return list(Rarity).index(self)


@dataclass(frozen=True)
class WeaponPart:
    """A single installable weapon component. Immutable data loaded from JSON."""

    part_id: str
    name: str
    category: PartCategory
    rarity: Rarity
    price: int
    description: str
    base: dict[str, float] = field(default_factory=dict)
    add: dict[str, float] = field(default_factory=dict)
    mult: dict[str, float] = field(default_factory=dict)
    props: dict[str, Any] = field(default_factory=dict)
    visual: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, part_id: str, category: PartCategory, raw: dict[str, Any]) -> "WeaponPart":
        return cls(
            part_id=part_id,
            name=str(raw.get("name", part_id)),
            category=category,
            rarity=Rarity(raw.get("rarity", "COMMON")),
            price=int(raw.get("price", 0)),
            description=str(raw.get("description", "")),
            base={k: float(v) for k, v in raw.get("base", {}).items()},
            add={k: float(v) for k, v in raw.get("add", {}).items()},
            mult={k: float(v) for k, v in raw.get("mult", {}).items()},
            props=dict(raw.get("props", {})),
            visual=dict(raw.get("visual", {})),
        )
