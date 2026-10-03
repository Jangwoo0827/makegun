"""Shop inventory generation and purchase logic (no rendering here)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

import settings
from game.session import RunSession
from systems.upgrade_manager import Upgrade, UpgradeManager
from weapons.weapon_parts import Rarity

UPGRADE_PRICES: dict[Rarity, int] = {
    Rarity.COMMON: 90, Rarity.UNCOMMON: 140, Rarity.RARE: 220, Rarity.EPIC: 340, Rarity.LEGENDARY: 520,
}


class OfferKind(str, Enum):
    PART = "part"
    UPGRADE = "upgrade"
    HEALTH = "health"
    AMMO = "ammo"


@dataclass
class ShopOffer:
    kind: OfferKind
    title: str
    subtitle: str
    description: str
    price: int
    rarity: Rarity
    part_id: str | None = None
    upgrade: Upgrade | None = None
    sold: bool = False


class ShopManager:
    def __init__(self, session: RunSession) -> None:
        self.session = session
        self.offers: list[ShopOffer] = []
        self.stock_wave: int = -1
        self.rerolls: int = 0

    def ensure_stock(self, wave: int) -> None:
        if self.stock_wave != wave:
            self.rerolls = 0
            self.generate(wave)

    @property
    def reroll_cost(self) -> int:
        return self.session.price(settings.SHOP_REROLL_COST + settings.SHOP_REROLL_COST_STEP * self.rerolls)

    def upgrade_price(self, upgrade: Upgrade) -> int:
        owned = UpgradeManager.stack_counts(self.session.upgrades_taken).get(upgrade.upgrade_id, 0)
        return self.session.price(int(UPGRADE_PRICES[upgrade.rarity] * settings.SHOP_UPGRADE_PRICE_GROWTH ** owned))

    def generate(self, wave: int) -> None:
        s = self.session
        self.stock_wave = wave
        offers: list[ShopOffer] = []
        exclude = set(s.owned_parts)
        for _ in range(4):
            part = s.library.random_part(exclude, wave)
            if part is None:
                break
            exclude.add(part.part_id)
            price = s.price(max(60, int(part.price * (1.0 + wave * 0.02))))
            offers.append(ShopOffer(OfferKind.PART, part.name, part.category.label, part.description,
                                    price, part.rarity, part_id=part.part_id))
        for up in s.upgrade_manager.roll_choices(wave, 2, s.stats.luck, s.upgrades_taken):
            offers.append(ShopOffer(OfferKind.UPGRADE, up.name, "Upgrade", up.description,
                                    self.upgrade_price(up), up.rarity, upgrade=up))
        while len(offers) < settings.SHOP_OFFER_COUNT:
            if random.random() < 0.5:
                offers.append(ShopOffer(OfferKind.HEALTH, "MED KIT", "Consumable", "Restore 50% HP",
                                        s.price(settings.HEALTH_ITEM_PRICE), Rarity.COMMON))
            else:
                offers.append(ShopOffer(OfferKind.AMMO, "AMMO CRATE", "Consumable", "Refill all reserve ammo",
                                        s.price(settings.AMMO_ITEM_PRICE), Rarity.COMMON))
        self.offers = offers[: settings.SHOP_OFFER_COUNT]

    def reroll(self) -> bool:
        if not self.session.spend(self.reroll_cost):
            return False
        self.rerolls += 1
        self.generate(self.stock_wave)
        return True

    def _reprice_upgrades(self) -> None:
        """After buying an upgrade, other copies on the shelf get pricier or sell out at max stacks."""
        available = {u.upgrade_id for u in self.session.upgrade_manager.available(self.session.upgrades_taken)}
        for o in self.offers:
            if o.kind == OfferKind.UPGRADE and o.upgrade and not o.sold:
                if o.upgrade.upgrade_id not in available:
                    o.sold = True
                else:
                    o.price = self.upgrade_price(o.upgrade)

    def buy(self, offer: ShopOffer) -> bool:
        s = self.session
        if offer.sold or not s.spend(offer.price):
            return False
        if offer.kind == OfferKind.PART and offer.part_id:
            s.own_part(offer.part_id)
        elif offer.kind == OfferKind.UPGRADE and offer.upgrade:
            s.apply_upgrade(offer.upgrade)
            self._reprice_upgrades()
        elif offer.kind == OfferKind.HEALTH:
            s.player.heal(s.player.max_hp * 0.5)
        elif offer.kind == OfferKind.AMMO:
            for w in s.weapons:
                w.refill(1.0)
        offer.sold = True
        return True
