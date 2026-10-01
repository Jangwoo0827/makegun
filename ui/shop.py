"""SHOP state: buy parts, upgrades, consumables, weapon levels and slots."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from game.state import GameState, StateID
from systems.shop_manager import OfferKind, ShopManager, ShopOffer
from ui.buttons import Button, ButtonGroup, draw_panel, wrap_text
from ui.fonts import draw_text
from ui.hud import stat_lines
from ui.menus import draw_backdrop
from weapons.gun_renderer import draw_gun

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
CARD_W, CARD_H = 250, 250


class ShopState(GameState):
    state_id = StateID.SHOP

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.session = game.require_session()
        if game.shop is None or game.shop.session is not self.session:
            game.shop = ShopManager(self.session)
        self.shop: ShopManager = game.shop
        self.shop.ensure_stock(self.session.wave_reached)
        self.weapon_index: int = self.session.player.current
        self.buttons = ButtonGroup()
        self.message: str = ""
        self.message_time: float = 0.0
        self._build()

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)

    # ---------------------------------------------------------------- layout
    def _build(self) -> None:
        s = self.session
        self.buttons.clear()
        for i, offer in enumerate(self.shop.offers):
            col, row = i % 3, i // 3
            rect = (30 + col * (CARD_W + 16), 90 + row * (CARD_H + 16), CARD_W, CARD_H)
            label = "SOLD" if offer.sold else ""
            self.buttons.add(Button(rect, label, lambda o=offer: self._buy(o), font_size=28,
                                    accent=settings.RARITY_COLORS[offer.rarity.value],
                                    enabled=not offer.sold and s.can_afford(offer.price)))
        rx = 860
        weapon = s.weapons[self.weapon_index]
        cost = s.weapon_upgrade_cost(weapon)
        for i in range(len(s.weapons)):
            self.buttons.add(Button((rx + i * 66, 300, 60, 30), f"#{i + 1}", lambda i=i: self._pick_weapon(i),
                                    font_size=14, selected=i == self.weapon_index))
        self.buttons.add(Button((rx, 340, 390, 50), f"UPGRADE WEAPON  Lv.{weapon.level}->{weapon.level + 1}",
                                self._upgrade_weapon, font_size=16, subtext=f"${cost}  (+12% damage)",
                                enabled=s.can_afford(cost)))
        slot_price = s.next_slot_price()
        self.buttons.add(Button((rx, 400, 390, 50), "NEW WEAPON SLOT" if slot_price else "ALL SLOTS OWNED",
                                self._buy_slot, font_size=16,
                                subtext=f"${slot_price}  (copy of current gun)" if slot_price else "",
                                enabled=slot_price is not None and s.can_afford(slot_price)))
        self.buttons.add(Button((rx, 460, 390, 50), "REROLL STOCK", self._reroll, font_size=16,
                                subtext=f"${settings.SHOP_REROLL_COST}",
                                enabled=s.can_afford(settings.SHOP_REROLL_COST)))
        self.buttons.add(Button((rx, H - 70, 185, 50), "EDITOR", lambda: self.game.replace(StateID.WEAPON_EDITOR),
                                hotkey=pygame.K_e))
        self.buttons.add(Button((rx + 205, H - 70, 185, 50), "BACK", self.game.pop, hotkey=pygame.K_ESCAPE))

    # --------------------------------------------------------------- actions
    def _notify(self, text: str) -> None:
        self.message, self.message_time = text, 2.5

    def _buy(self, offer: ShopOffer) -> None:
        if self.shop.buy(offer):
            self.game.sound.play("buy")
            extra = " - equip it in the EDITOR" if offer.kind == OfferKind.PART else ""
            self._notify(f"Bought {offer.title}{extra}")
        self._build()

    def _pick_weapon(self, index: int) -> None:
        self.weapon_index = index
        self._build()

    def _upgrade_weapon(self) -> None:
        weapon = self.session.weapons[self.weapon_index]
        if self.session.upgrade_weapon(weapon):
            self.game.sound.play("buy")
            self._notify(f"{weapon.name} upgraded to Lv.{weapon.level}")
        self._build()

    def _buy_slot(self) -> None:
        if self.session.unlock_slot():
            self.game.sound.play("buy")
            self.weapon_index = len(self.session.weapons) - 1
            self._notify("New weapon slot unlocked! Customize it in the EDITOR.")
        self._build()

    def _reroll(self) -> None:
        if self.shop.reroll():
            self.game.sound.play("click")
        self._build()

    # ---------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        self.buttons.handle_event(event)

    def update(self, dt: float) -> None:
        self.message_time = max(0.0, self.message_time - dt)

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        s = self.session
        draw_backdrop(surface, 0.0)
        draw_text(surface, "SHOP", (30, 24), 40, settings.UI_ACCENT, True)
        draw_text(surface, f"$ {s.money}", (W - 30, 24), 32, settings.MONEY_COLOR, True, "topright")
        draw_text(surface, f"HP {int(s.player.hp)}/{int(s.player.max_hp)}", (W - 260, 34), 18, settings.HP_COLOR,
                  True, "topright")
        self.buttons.draw(surface)
        for i, offer in enumerate(self.shop.offers):
            if offer.sold:
                continue
            rect = self.buttons.buttons[i].rect
            color = settings.RARITY_COLORS[offer.rarity.value]
            pygame.draw.rect(surface, color, (rect.x, rect.y, rect.w, 6), border_top_left_radius=6,
                             border_top_right_radius=6)
            draw_text(surface, f"{offer.subtitle.upper()}  -  {offer.rarity.value}", (rect.x + 14, rect.y + 16),
                      13, color, True)
            draw_text(surface, offer.title, (rect.x + 14, rect.y + 38), 20, settings.UI_TEXT, True)
            if offer.kind == OfferKind.PART and offer.part_id:
                preview = dict(s.weapons[self.weapon_index].parts)
                part = s.library.get(offer.part_id)
                preview[part.category] = part
                draw_gun(surface, preview, (rect.x + 70, rect.y + 88), 0.0, 1.6)
                desc_y = rect.y + 136
            else:
                desc_y = rect.y + 80
            for j, line in enumerate(wrap_text(offer.description, 14, rect.w - 28)[:4]):
                draw_text(surface, line, (rect.x + 14, desc_y + j * 19), 14, settings.UI_TEXT_DIM)
            price_color = settings.MONEY_COLOR if s.can_afford(offer.price) else settings.UI_BAD
            draw_text(surface, f"${offer.price}", (rect.right - 14, rect.bottom - 14), 22, price_color, True,
                      "bottomright")

        # Right column: current weapon summary
        panel = pygame.Rect(860, 90, 390, 196)
        draw_panel(surface, panel)
        weapon = s.weapons[self.weapon_index]
        draw_text(surface, weapon.name, (panel.x + 14, panel.y + 10), 18, settings.UI_TEXT, True)
        draw_gun(surface, weapon.parts, (panel.x + 80, panel.y + 70), 0.0, 2.2)
        for j, (k, v) in enumerate(stat_lines(weapon.stats)[:6]):
            draw_text(surface, k, (panel.x + 200, panel.y + 40 + j * 24), 13, settings.UI_TEXT_DIM)
            draw_text(surface, v, (panel.right - 14, panel.y + 40 + j * 24), 13, settings.UI_TEXT, True, "topright")
        draw_text(surface, "Select weapon:", (860, 280), 12, settings.UI_TEXT_DIM)
        if self.message_time > 0:
            draw_text(surface, self.message, (30, H - 40), 18, settings.UI_GOOD, True)
