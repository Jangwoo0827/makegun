"""WAVE CLEAR screen: shows the reward and offers 3 roguelite upgrades."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from game.state import GameState, StateID
from systems.upgrade_manager import Upgrade
from ui.buttons import Button, ButtonGroup, wrap_text
from ui.fonts import draw_text
from systems.tutorial import HINTS, draw_hint
from ui.menus import dim

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
CARD_W, CARD_H = 250, 280


class WaveClearState(GameState):
    state_id = StateID.WAVE_CLEAR
    is_overlay = True

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.session = game.require_session()
        self.choices: list[Upgrade] = list(self.session.pending_upgrades)
        self.buttons = ButtonGroup()
        total = len(self.choices) * CARD_W + (len(self.choices) - 1) * 30
        x0 = W // 2 - total // 2
        keys = (pygame.K_1, pygame.K_2, pygame.K_3)
        for i, up in enumerate(self.choices):
            color = settings.RARITY_COLORS[up.rarity.value]
            self.buttons.add(Button((x0 + i * (CARD_W + 30), 300, CARD_W, CARD_H), "",
                                    lambda u=up: self._pick(u), accent=color, hotkey=keys[i]))
        if not self.choices:
            self.buttons.add(Button((W // 2 - 120, 400, 240, 56), "CONTINUE",
                                    lambda: game.replace(StateID.INTERMISSION), hotkey=pygame.K_RETURN))
        self.time: float = 0.0

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)

    def on_exit(self) -> None:
        self.game.profile.hints_seen.add("wave_clear")

    def _pick(self, upgrade: Upgrade) -> None:
        self.session.apply_upgrade(upgrade)
        self.session.pending_upgrades = []
        self.game.sound.play("buy")
        self.game.replace(StateID.INTERMISSION)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.buttons.handle_event(event)

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        dim(surface, 190)
        scale = min(1.0, self.time * 4)
        draw_text(surface, "WAVE CLEAR!", (W // 2, 110), int(30 + 40 * scale), settings.UI_GOOD, True, "center")
        draw_text(surface, f"Reward: ${self.session.last_wave_reward}", (W // 2, 180), 28, settings.MONEY_COLOR,
                  True, "center")
        draw_text(surface, "CHOOSE UPGRADE", (W // 2, 250), 22, settings.UI_TEXT, True, "center")
        if "wave_clear" not in self.game.profile.hints_seen:
            draw_hint(surface, HINTS["wave_clear"])
        self.buttons.draw(surface)
        for i, up in enumerate(self.choices):
            rect = self.buttons.buttons[i].rect
            color = settings.RARITY_COLORS[up.rarity.value]
            pygame.draw.rect(surface, color, (rect.x, rect.y, rect.w, 8), border_top_left_radius=6,
                             border_top_right_radius=6)
            draw_text(surface, up.rarity.value, (rect.centerx, rect.y + 28), 14, color, True, "center")
            draw_text(surface, up.name, (rect.centerx, rect.y + 70), 24, settings.UI_TEXT, True, "center")
            for j, line in enumerate(wrap_text(up.description, 18, rect.w - 30)):
                draw_text(surface, line, (rect.centerx, rect.y + 130 + j * 26), 18, settings.UI_TEXT_DIM,
                          anchor="center")
            draw_text(surface, f"[{i + 1}]", (rect.centerx, rect.bottom - 30), 16, settings.UI_TEXT_DIM, True, "center")
