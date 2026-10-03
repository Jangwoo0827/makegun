"""Top-level Game object: owns the window, shared resources and the state stack."""
from __future__ import annotations

import asyncio
import os
import traceback
from dataclasses import asdict, dataclass
from typing import Any, Callable

import pygame

import settings
from entities.enemy import EnemyData, load_enemy_data
from game.play_state import PlayState
from game.profile import Profile, RunResult
from game.stages import StageData, load_stages
from game.session import RunSession, default_starter
from game.state import GameState, StateID
from systems import storage
from systems.save_manager import SaveManager
from systems.shop_manager import ShopManager
from systems.sound import SoundManager
from systems.upgrade_manager import UpgradeManager
from ui.menus import (GameOverState, IntermissionState, LoadoutState, MainMenuState, PauseState,
                      SettingsState)
from ui.progression import MetaState, StageClearState, StageSelectState, StatsState
from ui.shop import ShopState
from ui.fonts import draw_text
from ui.touch_controls import TouchControls
from ui.buttons import draw_panel
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
        raw = storage.read_json(settings.SAVE_FILE)
        if not isinstance(raw, dict):
            return cls()
        try:
            return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})
        except TypeError:
            return cls()

    def save(self) -> None:
        storage.write_json(settings.SAVE_FILE, asdict(self))


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

        self.touch: TouchControls = TouchControls()
        self.saves: SaveManager = SaveManager()
        self.profile: Profile = Profile()
        self.stages: list[StageData] = load_stages()
        self.last_result: RunResult | None = None
        #: [title, subtitle, seconds left]
        self.toasts: list[list] = []
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
            StateID.STAGE_SELECT: lambda: StageSelectState(self),
            StateID.STAGE_CLEAR: lambda: StageClearState(self),
            StateID.META: lambda: MetaState(self),
            StateID.STATS: lambda: StatsState(self),
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

    def start_new_run(self, stage_index: int | None = None) -> None:
        if stage_index is None:  # "try again" replays the last stage
            stage_index = self.session.stage.index if self.session is not None else 0
        stage = self.stages[max(0, min(stage_index, len(self.stages) - 1))]
        self.saves.delete()
        self.session = RunSession(self.library, self.upgrades, self.starter_preset(), stage)
        self.session.apply_meta(*self.profile.meta_bonuses())
        self.last_result = None
        self.shop = None
        self.play_state = PlayState(self)
        self.change(StateID.GAME)

    def continue_run(self) -> bool:
        """Load the saved run. Returns False if there is no valid save."""
        loaded = self.saves.load(self.library, self.upgrades, self.stages)
        if loaded is None:
            return False
        self.session, phase = loaded
        self.shop = None
        self.play_state = PlayState(self, start_wave=(phase == "wave"))
        while self.stack:
            self.stack.pop().on_exit()
        if phase == "wave":
            self.push(StateID.GAME)
        else:
            # Put GAME underneath without triggering its "start next wave" on_enter.
            self.stack.append(self.play_state)
            self.push(StateID.WAVE_CLEAR if self.session.pending_upgrades else StateID.INTERMISSION)
        return True

    def save_run(self) -> None:
        """Save the current run from wherever the player is."""
        if (self.session is None or self.play_state is None or not self.session.player.alive
                or self.session.run_recorded):
            return
        ps = self.play_state
        if ps.awaiting_next_wave:
            phase = "wave_clear" if self.session.pending_upgrades else "intermission"
            self.saves.save(self.session, phase, ps.waves.wave)
        else:  # mid-wave: keep progress, restart this wave on continue
            self.saves.save(self.session, "wave", max(0, ps.waves.wave - 1))

    def finish_run(self, victory: bool) -> RunResult | None:
        """Bank a finished run into the profile exactly once (death or stage clear)."""
        s = self.session
        if s is None or s.run_recorded:
            return self.last_result
        s.run_recorded = True
        waves_cleared = s.stage.waves if victory else max(0, s.wave_reached - 1)
        cores = self.profile.record_run_end(s.stage.index, s.stage.stage_id, s.wave_reached, waves_cleared,
                                            s.kills, s.boss_kills, victory, len(self.stages))
        new = self.profile.check_achievements(s.run_stats)
        for a in new:
            self.toast(f"ACHIEVEMENT: {a.name}", f"{a.description}  (+{a.reward} cores)")
        self.saves.delete()
        self.last_result = RunResult(cores, victory, new)
        return self.last_result

    def _report_crash(self) -> None:
        """Print the traceback, show it on screen, and fall back to the main menu."""
        text = traceback.format_exc()
        print(text)
        lines = text.strip().splitlines()[-2:]
        self.toasts.append(["ERROR - back to menu", lines[-1][:60] if lines else "", 8.0])
        self.session = None
        self.play_state = None
        self.shop = None
        try:
            self.change(StateID.MAIN_MENU)
        except Exception:
            self.running = False

    def toast(self, title: str, subtitle: str = "") -> None:
        self.toasts.append([title, subtitle, 4.0])
        self.sound.play("buy")

    def _draw_toasts(self) -> None:
        y = 112  # below the boss bar
        for title, sub, t in self.toasts[:4]:
            rect = pygame.Rect(settings.SCREEN_WIDTH - 420, y, 400, 54)
            draw_panel(self.screen, rect, border=settings.UI_ACCENT, alpha=int(230 * min(1.0, t)))
            draw_text(self.screen, title, (rect.x + 14, rect.y + 8), 16, settings.UI_ACCENT, True)
            draw_text(self.screen, sub, (rect.x + 14, rect.y + 30), 13, settings.UI_TEXT)
            y += 62

    def save_and_quit_to_menu(self) -> None:
        self.save_run()
        self.session = None
        self.play_state = None
        self.shop = None
        self.change(StateID.MAIN_MENU)

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
        self.save_run()  # closing the window mid-run keeps progress
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
        for t in self.toasts:
            t[2] -= dt
        self.toasts = [t for t in self.toasts if t[2] > 0]

    def draw(self) -> None:
        self.screen.fill(settings.BG_COLOR)
        # Draw from the deepest non-overlay state upward.
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].is_overlay:
            start -= 1
        for state in self.stack[max(0, start):]:
            state.draw(self.screen)
        self._draw_toasts()

    def step(self, dt: float) -> None:
        self.handle_events()
        self.update(dt)
        self.draw()
        pygame.display.flip()

    async def run(self) -> None:
        """Main loop. Async so the browser build (pygbag) can yield to the page every frame."""
        while self.running:
            dt = min(self.clock.tick(settings.FPS) / 1000.0, settings.MAX_DT)
            try:
                self.step(dt)
            except Exception:  # never die silently (the browser would just freeze on the last frame)
                self._report_crash()
            await asyncio.sleep(0)
        self.options.save()
        pygame.quit()
