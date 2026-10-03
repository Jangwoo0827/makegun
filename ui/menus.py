"""Menu-style states: main menu, loadout, settings, pause, intermission, game over."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

import settings
from game.state import GameState, StateID
from ui.buttons import Button, ButtonGroup, draw_panel
from ui.fonts import draw_text
from ui.hud import stat_lines
from weapons.gun_renderer import draw_gun
from weapons.weapon_builder import STARTER_PRESETS, WeaponBuilder

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT


def draw_backdrop(surface: pygame.Surface, t: float) -> None:
    surface.fill(settings.BG_COLOR)
    g = settings.GRID_SIZE
    off = (t * 20) % g
    for x in range(-g, W + g, g):
        pygame.draw.line(surface, settings.GRID_COLOR, (x + off, 0), (x + off, H))
    for y in range(-g, H + g, g):
        pygame.draw.line(surface, settings.GRID_COLOR, (0, y + off), (W, y + off))


def dim(surface: pygame.Surface, alpha: int = 170) -> None:
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    surface.blit(overlay, (0, 0))


class MenuState(GameState):
    """Shared helpers for button-driven screens."""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.buttons = ButtonGroup()
        self.time: float = 0.0

    def click(self) -> None:
        self.game.sound.play("click")

    def handle_event(self, event: pygame.event.Event) -> None:
        self.buttons.handle_event(event, self.click)

    def update(self, dt: float) -> None:
        self.time += dt


class MainMenuState(MenuState):
    state_id = StateID.MAIN_MENU

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.confirm_new: bool = False
        self._build()

    def _build(self) -> None:
        game = self.game
        self.buttons.clear()
        save = game.saves.peek()
        x, y = W // 2 - 140, 250
        items: list[tuple[str, object, str]] = []
        if save is not None:
            wave = int(save.get("resume_wave", 0))
            stage = game.stages[min(int(save.get("stage", 0)), len(game.stages) - 1)]
            where = f"Wave {wave + 1}" if save.get("phase") == "wave" else f"After wave {wave}"
            items.append(("CONTINUE", self._continue, f"{stage.name} {where}  -  ${save.get('money', 0)}"))
            new_label = "CLICK AGAIN TO OVERWRITE" if self.confirm_new else "NEW RUN"
            items.append((new_label, self._new_run, "replaces your save" if self.confirm_new else ""))
        else:
            items.append(("PLAY", self._new_run, ""))
        items += [("UPGRADES", lambda: game.push(StateID.META), f"{game.profile.cores} cores"),
                  ("STATS", lambda: game.push(StateID.STATS),
                   f"{len(game.profile.achievements)}/{len(game.profile.achievement_catalog)} achievements"),
                  ("LOADOUT", lambda: game.push(StateID.LOADOUT), ""),
                  ("SETTINGS", lambda: game.push(StateID.SETTINGS), "")]
        if not settings.WEB:  # a browser tab can't be quit from inside the game
            items.append(("QUIT", game.quit, ""))
        for i, (label, cb, sub) in enumerate(items):
            self.buttons.add(Button((x, y + i * 58, 280, 50), label, cb, font_size=20 if sub else 22,  # type: ignore[arg-type]
                                    subtext=sub, selected=(label == "CONTINUE")))

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)
        self.confirm_new = False
        self._build()

    def _continue(self) -> None:
        if not self.game.continue_run():
            self.game.saves.delete()  # corrupt/outdated save
            self._build()

    def _new_run(self) -> None:
        if self.game.saves.has_save() and not self.confirm_new:
            self.confirm_new = True
            self._build()
            return
        self.game.push(StateID.STAGE_SELECT)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if self.game.saves.has_save():
                self._continue()
            else:
                self._new_run()
            return
        super().handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        bob = math.sin(self.time * 2) * 6
        draw_text(surface, "GUN DESIGNER", (W // 2, 80 + bob), 70, settings.UI_ACCENT, True, "center")
        draw_text(surface, "build the gun  -  survive the waves", (W // 2, 134), 20, settings.UI_TEXT_DIM,
                  anchor="center")
        preset = self.game.starter_preset()
        lib = self.game.library
        parts = {c: lib.get(pid) for c, pid in preset.part_ids.items()}
        draw_gun(surface, parts, (W // 2 - 38, 190), -0.12 + math.sin(self.time) * 0.05, 1.8)
        self.buttons.draw(surface)
        draw_text(surface, f"Starter: {preset.name}", (W // 2, H - 58), 16, settings.UI_TEXT_DIM, anchor="center")
        draw_text(surface, "WASD move | Mouse aim | LMB fire | SPACE dash | Q/RMB grenade | R reload | 1/2/3 switch | ESC pause",
                  (W // 2, H - 30), 15, settings.UI_TEXT_DIM, anchor="center")


class LoadoutState(MenuState):
    state_id = StateID.LOADOUT

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        builder = WeaponBuilder(game.library)
        self.previews = [builder.build_preset(p) for p in STARTER_PRESETS]
        self._build()

    def _build(self) -> None:
        self.buttons.clear()
        for i, preset in enumerate(STARTER_PRESETS):
            rect = (80 + i * 285, 150, 265, 330)
            self.buttons.add(Button(rect, "", lambda i=i: self._select(i),
                                    selected=i == self.game.options.starter_index))
        self.buttons.add(Button((W // 2 - 110, 600, 220, 54), "BACK", self.game.pop, hotkey=pygame.K_ESCAPE))

    def _select(self, index: int) -> None:
        self.game.options.starter_index = index
        self.game.options.save()
        self._build()

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "LOADOUT", (W // 2, 70), 48, settings.UI_ACCENT, True, "center")
        draw_text(surface, "Choose your starting weapon. Its parts are unlocked for the run.", (W // 2, 115), 17,
                  settings.UI_TEXT_DIM, anchor="center")
        self.buttons.draw(surface)
        for i, preset in enumerate(STARTER_PRESETS):
            rect = self.buttons.buttons[i].rect
            built = self.previews[i]
            draw_text(surface, preset.name, (rect.centerx, rect.y + 24), 24, settings.UI_TEXT, True, "center")
            draw_gun(surface, built.parts, (rect.centerx - 40, rect.y + 90), 0.0, 2.0)
            draw_text(surface, preset.description, (rect.centerx, rect.y + 150), 13, settings.UI_TEXT_DIM,
                      anchor="center")
            for j, (k, v) in enumerate(stat_lines(built.stats)[:6]):
                draw_text(surface, k, (rect.x + 20, rect.y + 180 + j * 22), 14, settings.UI_TEXT_DIM)
                draw_text(surface, v, (rect.right - 20, rect.y + 180 + j * 22), 14, settings.UI_TEXT, True, "topright")


class SettingsState(MenuState):
    state_id = StateID.SETTINGS

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._build()

    def _build(self) -> None:
        o = self.game.options
        self.buttons.clear()
        rows = [("SOUND", o.sound, "sound"), ("SCREEN SHAKE", o.screen_shake, "screen_shake"),
                ("DAMAGE NUMBERS", o.damage_numbers, "damage_numbers")]
        for i, (label, value, attr) in enumerate(rows):
            self.buttons.add(Button((W // 2 - 180, 200 + i * 80, 360, 60), f"{label}: {'ON' if value else 'OFF'}",
                                    lambda a=attr: self._toggle(a), selected=value))
        self.buttons.add(Button((W // 2 - 110, 560, 220, 54), "BACK", self.game.pop, hotkey=pygame.K_ESCAPE))

    def _toggle(self, attr: str) -> None:
        o = self.game.options
        setattr(o, attr, not getattr(o, attr))
        self.game.sound.enabled = o.sound
        o.save()
        self._build()

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "SETTINGS", (W // 2, 110), 48, settings.UI_ACCENT, True, "center")
        self.buttons.draw(surface)


class PauseState(MenuState):
    state_id = StateID.PAUSE
    is_overlay = True

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        items = [("RESUME", game.pop), ("SETTINGS", lambda: game.push(StateID.SETTINGS)),
                 ("SAVE & QUIT", game.save_and_quit_to_menu)]
        for i, (label, cb) in enumerate(items):
            self.buttons.add(Button((W // 2 - 130, 300 + i * 70, 260, 54), label, cb))

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.pop()
            return
        super().handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        dim(surface)
        draw_text(surface, "PAUSED", (W // 2, 210), 56, settings.UI_ACCENT, True, "center")
        self.buttons.draw(surface)
        draw_text(surface, "Save & Quit keeps your money, parts and upgrades. The current wave restarts on CONTINUE.",
                  (W // 2, 530), 15, settings.UI_TEXT_DIM, anchor="center")


class IntermissionState(MenuState):
    """Hub between waves: continue, shop or workshop."""
    state_id = StateID.INTERMISSION

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        items = [("NEXT WAVE", self._continue, pygame.K_SPACE), ("SHOP", lambda: game.push(StateID.SHOP), pygame.K_s),
                 ("WEAPON EDITOR", lambda: game.push(StateID.WEAPON_EDITOR), pygame.K_e),
                 ("SAVE & MAIN MENU", game.save_and_quit_to_menu, pygame.K_ESCAPE)]
        for i, (label, cb, key) in enumerate(items):
            self.buttons.add(Button((W // 2 - 160, 310 + i * 72, 320, 58), label, cb,
                                    font_size=24 if i < 3 else 18, hotkey=key))

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)
        self.game.save_run()  # autosave after upgrades / shop / editor changes

    def _continue(self) -> None:
        self.game.pop_to(StateID.GAME)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        s = self.game.require_session()
        draw_text(surface, f"{s.stage.name}  -  WAVE {s.wave_reached}/{s.stage.waves} COMPLETE", (W // 2, 110), 40,
                  settings.UI_ACCENT, True, "center")
        draw_text(surface, f"$ {s.money}", (W // 2, 170), 30, settings.MONEY_COLOR, True, "center")
        p = s.player
        draw_text(surface, f"HP {int(p.hp)} / {int(p.max_hp)}    KILLS {s.kills}    PARTS {len(s.owned_parts)}"
                           f"/{len(s.library.parts)}", (W // 2, 215), 18, settings.UI_TEXT, anchor="center")
        nxt = s.wave_reached + 1
        if s.stage.bosses_for(nxt):
            draw_text(surface, f"WARNING: Wave {nxt} is a BOSS wave", (W // 2, 265), 20, settings.UI_BAD, True, "center")
        elif nxt == s.stage.waves:
            draw_text(surface, f"Wave {nxt} is the FINAL wave", (W // 2, 265), 20, settings.UI_ACCENT, True, "center")
        self.buttons.draw(surface)
        draw_text(surface, "[SPACE] next wave   [S] shop   [E] editor   [ESC] save & main menu", (W // 2, H - 40), 15,
                  settings.UI_TEXT_DIM, anchor="center")


class GameOverState(MenuState):
    state_id = StateID.GAME_OVER
    is_overlay = True

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.buttons.add(Button((W // 2 - 270, 520, 250, 56), "TRY AGAIN", game.start_new_run, hotkey=pygame.K_RETURN))
        self.buttons.add(Button((W // 2 + 20, 520, 250, 56), "MAIN MENU", game.end_run, hotkey=pygame.K_ESCAPE))

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)
        self.game.finish_run(victory=False)  # banks cores; death ends the run (deletes the save)

    def draw(self, surface: pygame.Surface) -> None:
        dim(surface, 200)
        s = self.game.session
        draw_text(surface, "GAME OVER", (W // 2, 160), 72, settings.UI_BAD, True, "center")
        if s is not None:
            res = self.game.last_result
            rows = [("STAGE", f"{s.stage.name}  wave {s.wave_reached}/{s.stage.waves}"), ("KILLS", str(s.kills)),
                    ("MONEY EARNED", f"${s.money_earned}"), ("FINAL WEAPON", s.player.weapon.name),
                    ("CORES EARNED", f"+{res.cores if res else 0}")]
            panel = pygame.Rect(W // 2 - 240, 240, 480, 240)
            draw_panel(surface, panel)
            for i, (k, v) in enumerate(rows):
                draw_text(surface, k, (panel.x + 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT_DIM, True)
                draw_text(surface, v, (panel.right - 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT, True, "topright")
        self.buttons.draw(surface)
