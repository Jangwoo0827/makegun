"""Top-level Game object: owns the window, shared resources and the state stack."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Callable

import pygame

import settings
from entities.enemy import EnemyData, load_enemy_data
from game.play_state import PlayState
from game.session import RunSession, default_starter
from game.state import GameState, StateID
from systems.shop_manager import ShopManager
from systems.sound import SoundManager
from systems.upgrade_manager import UpgradeManager
from ui.menus import (GameOverState, IntermissionState, LoadoutState, MainMenuState, PauseState,
                      SettingsState)
from ui.shop import ShopState
from ui.wave_clear import WaveClearState
from ui.weapon_editor import WeaponEditorState
from weapons.weapon_builder import STARTER_PRESETS, WeaponPreset
from weapons.weapon_data import PartLibrary


@dataclass
class Options:
    sound: bool = True
    screen_shake: bool = True
    damage_numbers: bool = True
    starter_index: int = 0

    @classmethod
    def load(cls) -> "Options":
        try:
            with open(settings.SAVE_FILE, "r", encoding="utf-8") as f:
                raw: dict[str, Any] = json.load(f)
            return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        try:
            with open(settings.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except OSError:
            pass


class Game:
    def __init__(self, headless: bool = False) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption(settings.TITLE)
        self.screen: pygame.Surface = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running: bool = True

        self.options: Options = Options.load()
        self.library: PartLibrary = PartLibrary()
        self.enemy_db: dict[str, EnemyData] = load_enemy_data()
        self.upgrades: UpgradeManager = UpgradeManager()
        self.sound: SoundManager = SoundManager()
        self.sound.enabled = self.options.sound

        self.session: RunSession | None = None
        self.play_state: PlayState | None = None
        self.shop: ShopManager | None = None
        self.stack: list[GameState] = []
        self._factories: dict[StateID, Callable[[], GameState]] = {
            StateID.MAIN_MENU: lambda: MainMenuState(self),
            StateID.LOADOUT: lambda: LoadoutState(self),
            StateID.SETTINGS: lambda: SettingsState(self),
            StateID.GAME: self._get_play_state,
            StateID.WAVE_CLEAR: lambda: WaveClearState(self),
            StateID.INTERMISSION: lambda: IntermissionState(self),
            StateID.SHOP: lambda: ShopState(self),
            StateID.WEAPON_EDITOR: lambda: WeaponEditorState(self),
            StateID.PAUSE: lambda: PauseState(self),
            StateID.GAME_OVER: lambda: GameOverState(self),
        }
        self.change(StateID.MAIN_MENU)

    # ---------------------------------------------------------------- session
    def require_session(self) -> RunSession:
        if self.session is None:
            raise RuntimeError("No active run session")
        return self.session

    def starter_preset(self) -> WeaponPreset:
        idx = self.options.starter_index
        return STARTER_PRESETS[idx] if 0 <= idx < len(STARTER_PRESETS) else default_starter()

    def start_new_run(self) -> None:
        self.session = RunSession(self.library, self.upgrades, self.starter_preset())
        self.shop = None
        self.play_state = PlayState(self)
        self.change(StateID.GAME)

    def end_run(self) -> None:
        self.session = None
        self.play_state = None
        self.shop = None
        self.change(StateID.MAIN_MENU)

    def _get_play_state(self) -> GameState:
        if self.play_state is None:
            self.play_state = PlayState(self)
        return self.play_state

    # ------------------------------------------------------------ state stack
    @property
    def top(self) -> GameState | None:
        return self.stack[-1] if self.stack else None

    def push(self, state_id: StateID) -> None:
        if self.top is not None:
            self.top.on_exit()
        state = self._factories[state_id]()
        self.stack.append(state)
        state.on_enter()

    def pop(self) -> None:
        if self.stack:
            self.stack.pop().on_exit()
        if self.top is not None:
            self.top.on_enter()

    def replace(self, state_id: StateID) -> None:
        if self.stack:
            self.stack.pop().on_exit()
        state = self._factories[state_id]()
        self.stack.append(state)
        state.on_enter()

    def pop_to(self, state_id: StateID) -> None:
        """Pop states until `state_id` is on top."""
        while self.stack and self.stack[-1].state_id != state_id:
            self.stack.pop().on_exit()
        if self.top is not None:
            self.top.on_enter()

    def change(self, state_id: StateID) -> None:
        while self.stack:
            self.stack.pop().on_exit()
        self.push(state_id)

    def quit(self) -> None:
        self.running = False

    # -------------------------------------------------------------- main loop
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
                return
            if self.top is not None:
                self.top.handle_event(event)

    def update(self, dt: float) -> None:
        if self.top is not None:
            self.top.update(dt)

    def draw(self) -> None:
        self.screen.fill(settings.BG_COLOR)
        # Draw from the deepest non-overlay state upward.
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].is_overlay:
            start -= 1
        for state in self.stack[max(0, start):]:
            state.draw(self.screen)

    def step(self, dt: float) -> None:
        self.handle_events()
        self.update(dt)
        self.draw()
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(settings.FPS) / 1000.0, settings.MAX_DT)
            self.step(dt)
        self.options.save()
        pygame.quit()
