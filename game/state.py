"""Game state base class and identifiers."""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from game.game import Game


class StateID(Enum):
    MAIN_MENU = auto()
    LOADOUT = auto()
    SETTINGS = auto()
    GAME = auto()
    WAVE_CLEAR = auto()
    INTERMISSION = auto()
    SHOP = auto()
    WEAPON_EDITOR = auto()
    PAUSE = auto()
    GAME_OVER = auto()
    STAGE_SELECT = auto()
    STAGE_CLEAR = auto()
    META = auto()
    STATS = auto()


class GameState:
    """Base class for every screen. The Game owns a stack of these."""

    state_id: StateID
    #: When True, the state below is drawn first (used for overlays like PAUSE).
    is_overlay: bool = False

    def __init__(self, game: "Game") -> None:
        self.game = game

    def on_enter(self) -> None:
        """Called when this state becomes the top of the stack."""

    def on_exit(self) -> None:
        """Called when this state is removed or covered."""

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass
