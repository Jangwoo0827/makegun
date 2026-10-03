"""Progression screens: stage select, stage clear, permanent upgrades (meta), stats & achievements."""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pygame

import settings
from game.state import StateID
from ui.buttons import Button, draw_panel, wrap_text
from ui.fonts import draw_text
from game.ascension import MAX_ASCENSION, ascension_levels, ascension_mods
from ui.menus import MenuState, dim, draw_backdrop

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT


class StageSelectState(MenuState):
    state_id = StateID.STAGE_SELECT
    CARD_W, CARD_H = 290, 232

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._build()

    def _build(self) -> None:
        game = self.game
        self.buttons.clear()
        gap = 14
        cols = 4
        x0 = W // 2 - (cols * self.CARD_W + (cols - 1) * gap) // 2
        for i, stage in enumerate(game.stages):
            col, row = i % cols, i // cols
            unlocked = i <= game.profile.unlocked_stage
            self.buttons.add(Button((x0 + col * (self.CARD_W + gap), 92 + row * (self.CARD_H + 12),
                                     self.CARD_W, self.CARD_H), "", lambda i=i: game.start_new_run(i),
                                    enabled=unlocked, accent=stage.wall_edge))
        prof = game.profile
        y = 590
        # ascension picker
        self.buttons.add(Button((40, y, 44, 50), "<", lambda: self._asc(-1), font_size=22,
                                enabled=prof.selected_ascension > 0))
        self.buttons.add(Button((290, y, 44, 50), ">", lambda: self._asc(1), font_size=22,
                                enabled=prof.selected_ascension < prof.ascension_unlocked))
        # modes
        modes_ok = prof.modes_unlocked
        endless = game.modes.get("endless")
        rush = game.modes.get("bossrush")
        best_e = int(prof.stat("endless_best"))
        best_r = prof.stat("best_bossrush_time")
        if endless is not None:
            self.buttons.add(Button((372, y, 230, 50), "ENDLESS", lambda: game.start_new_run(stage_id="endless"),
                                    enabled=modes_ok, font_size=18, accent=endless.wall_edge,
                                    subtext=f"best wave {best_e}" if modes_ok else "clear THE CORE"))
        if rush is not None:
            self.buttons.add(Button((614, y, 230, 50), "BOSS RUSH", lambda: game.start_new_run(stage_id="bossrush"),
                                    enabled=modes_ok, font_size=18, accent=rush.wall_edge,
                                    subtext=(f"best {best_r // 60:.0f}:{best_r % 60:04.1f}" if best_r else "no clear yet")
                                    if modes_ok else "clear THE CORE"))
        self.buttons.add(Button((W - 260, y, 220, 50), "BACK", game.pop, hotkey=pygame.K_ESCAPE))

    def _asc(self, delta: int) -> None:
        prof = self.game.profile
        prof.selected_ascension = max(0, min(prof.ascension_unlocked, prof.selected_ascension + delta))
        prof.save()
        self._build()

    def _boss_names(self, ids: tuple[str, ...]) -> str:
        return " + ".join(self.game.enemy_db[b].name.replace("THE ", "") for b in ids if b in self.game.enemy_db)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "SELECT STAGE", (W // 2, 40), 40, settings.UI_ACCENT, True, "center")
        draw_text(surface, "Clear every wave of a stage to unlock the next, harder one.", (W // 2, 74), 15,
                  settings.UI_TEXT_DIM, anchor="center")
        self.buttons.draw(surface)
        profile = self.game.profile
        for i, stage in enumerate(self.game.stages):
            rect = self.buttons.buttons[i].rect
            unlocked = i <= profile.unlocked_stage
            pygame.draw.rect(surface, stage.floor, (rect.x + 5, rect.y + 5, rect.w - 10, 50), border_radius=6)
            draw_text(surface, f"STAGE {stage.number}", (rect.centerx, rect.y + 18), 12, settings.UI_TEXT_DIM,
                      True, "center")
            draw_text(surface, stage.name, (rect.centerx, rect.y + 38), 20,
                      settings.UI_TEXT if unlocked else settings.UI_TEXT_DIM, True, "center")
            if not unlocked:
                draw_text(surface, "LOCKED", (rect.centerx, rect.centery + 10), 24, settings.UI_BAD, True, "center")
                draw_text(surface, f"Clear stage {stage.number - 1}", (rect.centerx, rect.centery + 38), 13,
                          settings.UI_TEXT_DIM, anchor="center")
                continue
            draw_text(surface, stage.subtitle, (rect.centerx, rect.y + 68), 12, settings.UI_TEXT_DIM, anchor="center")
            rows = [("WAVES", str(stage.waves)), ("ENEMY HP / DMG", f"x{stage.hp_mult:g} / x{stage.damage_mult:g}"),
                    ("ELITES", f"{stage.affix_chance * 100:.0f}%+" if stage.affix_chance else "-")]
            y = rect.y + 90
            for k, v in rows:
                draw_text(surface, k, (rect.x + 14, y), 13, settings.UI_TEXT_DIM)
                draw_text(surface, v, (rect.right - 14, y), 13, settings.UI_TEXT, True, "topright")
                y += 20
            for wave in sorted(stage.bosses):
                for line in wrap_text(f"W{wave}: {self._boss_names(stage.bosses[wave])}", 12, rect.w - 28)[:1]:
                    draw_text(surface, line, (rect.x + 14, y + 4), 12, (255, 140, 140))
                    y += 16
            best = profile.stage_best.get(stage.stage_id, 0)
            cleared = profile.stat("stages_cleared") >= stage.number
            status = "CLEARED" if cleared else (f"BEST: WAVE {best}" if best else "NEW")
            draw_text(surface, status, (rect.centerx, rect.bottom - 16), 14,
                      settings.UI_GOOD if cleared else settings.UI_ACCENT, True, "center")
        # ascension box
        asc = profile.selected_ascension
        box = pygame.Rect(90, 590, 194, 50)
        draw_panel(surface, box, border=(255, 120, 120) if asc else settings.UI_BORDER)
        if profile.ascension_unlocked == 0:
            draw_text(surface, "ASCENSION", (box.centerx, box.y + 16), 15, settings.UI_TEXT_DIM, True, "center")
            draw_text(surface, "clear the final stage", (box.centerx, box.y + 35), 11, settings.UI_TEXT_DIM,
                      anchor="center")
        else:
            draw_text(surface, f"ASCENSION {asc}", (box.centerx, box.y + 16), 17,
                      (255, 120, 120) if asc else settings.UI_TEXT, True, "center")
            sub = f"cores x{ascension_mods(asc).core_bonus:.2f}" if asc else "normal difficulty"
            draw_text(surface, sub, (box.centerx, box.y + 35), 11, settings.UI_TEXT_DIM, anchor="center")
        if asc:
            names = ascension_levels()[asc - 1].description
            draw_text(surface, f"A{asc}: {names}  (+ all lower levels)", (W // 2, 662), 13, (255, 140, 140),
                      anchor="center")


class StageClearState(MenuState):
    state_id = StateID.STAGE_CLEAR
    is_overlay = True

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        s = game.require_session()
        nxt = s.stage.index + 1
        if s.stage.mode == "normal" and nxt < len(game.stages):
            self.buttons.add(Button((W // 2 - 270, 540, 250, 56), f"NEXT: {game.stages[nxt].name}",
                                    lambda: game.start_new_run(nxt), hotkey=pygame.K_RETURN, font_size=18))
            self.buttons.add(Button((W // 2 + 20, 540, 250, 56), "MAIN MENU", game.end_run, hotkey=pygame.K_ESCAPE))
        else:
            self.buttons.add(Button((W // 2 - 125, 540, 250, 56), "MAIN MENU", game.end_run, hotkey=pygame.K_RETURN))

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)

    def draw(self, surface: pygame.Surface) -> None:
        dim(surface, 200)
        s = self.game.session
        res = self.game.last_result
        mode = s.stage.mode if s is not None else "normal"
        final = s is not None and mode == "normal" and s.stage.index == len(self.game.stages) - 1
        title = "BOSS RUSH CLEAR!" if mode == "bossrush" else ("YOU ARE THE GUN DESIGNER" if final else "STAGE CLEAR!")
        draw_text(surface, title, (W // 2, 140), 56, settings.UI_GOOD, True, "center")
        if s is None:
            return
        draw_text(surface, s.stage.name, (W // 2, 200), 26, settings.UI_ACCENT, True, "center")
        panel = pygame.Rect(W // 2 - 240, 250, 480, 250)
        draw_panel(surface, panel)
        first = ("TIME", f"{s.run_time // 60:.0f}:{s.run_time % 60:04.1f}") if mode == "bossrush" else \
            ("KILLS", str(s.kills))
        asc = f"  (A{s.ascension.level})" if s.ascension.level else ""
        rows = [first, ("BOSSES DEFEATED", str(s.boss_kills)),
                ("MONEY EARNED", f"${s.money_earned}"), ("FINAL WEAPON", s.player.weapon.name),
                ("CORES EARNED", f"+{res.cores if res else 0}{asc}")]
        for i, (k, v) in enumerate(rows):
            draw_text(surface, k, (panel.x + 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT_DIM, True)
            draw_text(surface, v, (panel.right - 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT, True, "topright")
        if mode == "normal" and not final:
            draw_text(surface, f"Unlocked: STAGE {s.stage.number + 1}", (W // 2, 515), 16, settings.UI_GOOD,
                      True, "center")
        elif final and s.ascension.level < MAX_ASCENSION:
            draw_text(surface, f"Unlocked: ASCENSION {s.ascension.level + 1}", (W // 2, 515), 16, (255, 120, 120),
                      True, "center")
        self.buttons.draw(surface)


class MetaState(MenuState):
    """Spend Cores on permanent upgrades that apply to every future run."""
    state_id = StateID.META
    CARD_W, CARD_H = 228, 200

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._build()

    def _build(self) -> None:
        self.buttons.clear()
        profile = self.game.profile
        cols = 5
        x0 = W // 2 - (cols * self.CARD_W + (cols - 1) * 14) // 2
        for i, meta in enumerate(profile.meta_catalog):
            col, row = i % cols, i // cols
            cost = profile.meta_next_cost(meta)
            self.buttons.add(Button((x0 + col * (self.CARD_W + 14), 140 + row * (self.CARD_H + 14),
                                     self.CARD_W, self.CARD_H), "", lambda m=meta: self._buy(m),
                                    enabled=cost is not None and profile.cores >= cost))
        self.buttons.add(Button((W // 2 - 110, H - 80, 220, 52), "BACK", self.game.pop, hotkey=pygame.K_ESCAPE))

    def _buy(self, meta: object) -> None:
        if self.game.profile.buy_meta(meta):  # type: ignore[arg-type]
            self.game.sound.play("buy")
        self._build()

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        profile = self.game.profile
        draw_text(surface, "PERMANENT UPGRADES", (W // 2, 56), 40, settings.UI_ACCENT, True, "center")
        draw_text(surface, f"CORES: {profile.cores}", (W // 2, 102), 24, (150, 220, 255), True, "center")
        self.buttons.draw(surface)
        for i, meta in enumerate(profile.meta_catalog):
            rect = self.buttons.buttons[i].rect
            lvl = profile.meta_level(meta.meta_id)
            draw_text(surface, meta.name, (rect.centerx, rect.y + 22), 20, settings.UI_TEXT, True, "center")
            for j, line in enumerate(wrap_text(meta.description, 13, rect.w - 24)[:3]):
                draw_text(surface, line, (rect.centerx, rect.y + 52 + j * 18), 13, settings.UI_TEXT_DIM,
                          anchor="center")
            pip_w = 16
            px = rect.centerx - (meta.max_level * (pip_w + 4)) // 2
            for k in range(meta.max_level):
                pip = pygame.Rect(px + k * (pip_w + 4), rect.y + 122, pip_w, 12)
                pygame.draw.rect(surface, (150, 220, 255) if k < lvl else (50, 56, 70), pip, border_radius=3)
            cost = profile.meta_next_cost(meta)
            text, color = ("MAXED", settings.UI_GOOD) if cost is None else \
                (f"{cost} cores", (150, 220, 255) if profile.cores >= cost else settings.UI_BAD)
            draw_text(surface, text, (rect.centerx, rect.bottom - 30), 18, color, True, "center")
        draw_text(surface, "Earn cores by finishing runs (more for later stages, bosses and stage clears) "
                           "and from achievements.", (W // 2, H - 110), 14, settings.UI_TEXT_DIM, anchor="center")


STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("runs", "Runs finished"), ("stages_cleared", "Stages cleared"), ("total_kills", "Enemies killed"),
    ("total_boss_kills", "Bosses defeated"), ("total_affix_kills", "Elites killed"),
    ("total_dashes", "Dashes"), ("best_grenade_kills", "Best grenade multi-kill"),
)


class StatsState(MenuState):
    state_id = StateID.STATS

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.buttons.add(Button((W // 2 - 110, H - 70, 220, 50), "BACK", game.pop, hotkey=pygame.K_ESCAPE))

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        profile = self.game.profile
        draw_text(surface, "STATS & ACHIEVEMENTS", (W // 2, 48), 40, settings.UI_ACCENT, True, "center")
        left = pygame.Rect(30, 90, 380, 540)
        draw_panel(surface, left)
        draw_text(surface, "LIFETIME", (left.x + 16, left.y + 12), 18, settings.UI_ACCENT, True)
        y = left.y + 48
        for key, label in STAT_LABELS:
            draw_text(surface, label, (left.x + 16, y), 16, settings.UI_TEXT_DIM)
            draw_text(surface, f"{int(profile.stat(key)):,}", (left.right - 16, y), 16, settings.UI_TEXT, True,
                      "topright")
            y += 30
        y += 14
        draw_text(surface, "BEST WAVE PER STAGE", (left.x + 16, y), 16, settings.UI_ACCENT, True)
        y += 30
        for stage in self.game.stages:
            best = profile.stage_best.get(stage.stage_id, 0)
            draw_text(surface, stage.name, (left.x + 16, y), 15, settings.UI_TEXT_DIM)
            draw_text(surface, f"{best}/{stage.waves}" if best else "-", (left.right - 16, y), 15,
                      settings.UI_TEXT, True, "topright")
            y += 26

        right = pygame.Rect(430, 90, W - 460, 540)
        draw_panel(surface, right)
        cat = profile.achievement_catalog
        draw_text(surface, f"ACHIEVEMENTS  {len(profile.achievements)}/{len(cat)}", (right.x + 16, right.y + 12),
                  18, settings.UI_ACCENT, True)
        col_w = (right.w - 32) // 2
        for i, a in enumerate(cat):
            col, row = i // 9, i % 9
            x = right.x + 16 + col * col_w
            yy = right.y + 50 + row * 54
            done = a.ach_id in profile.achievements
            pygame.draw.rect(surface, settings.UI_GOOD if done else (50, 56, 70), (x, yy + 4, 14, 14), border_radius=3)
            draw_text(surface, a.name, (x + 24, yy), 16, settings.UI_TEXT if done else settings.UI_TEXT_DIM, True)
            draw_text(surface, f"{a.description}  (+{a.reward})", (x + 24, yy + 22), 12, settings.UI_TEXT_DIM)
        self.buttons.draw(surface)


class PatchNotesState(MenuState):
    """What's new (data/patch_notes.json)."""
    state_id = StateID.PATCH_NOTES

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        path = os.path.join(settings.DATA_DIR, "patch_notes.json")
        with open(path, "r", encoding="utf-8") as fh:
            self.notes: list[dict] = json.load(fh)
        self.buttons.add(Button((W // 2 - 110, H - 70, 220, 50), "BACK", game.pop, hotkey=pygame.K_ESCAPE))

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "PATCH NOTES", (W // 2, 50), 40, settings.UI_ACCENT, True, "center")
        panel = pygame.Rect(140, 90, W - 280, 530)
        draw_panel(surface, panel)
        y = panel.y + 18
        for entry in self.notes:
            if y > panel.bottom - 40:
                break
            current = entry["version"] == settings.VERSION
            draw_text(surface, f"v{entry['version']}", (panel.x + 24, y), 22,
                      settings.UI_ACCENT if current else settings.UI_TEXT, True)
            draw_text(surface, entry.get("date", ""), (panel.right - 24, y + 4), 14, settings.UI_TEXT_DIM,
                      anchor="topright")
            y += 34
            for note in entry["notes"]:
                for j, line in enumerate(wrap_text(note, 15, panel.w - 80)):
                    if y > panel.bottom - 24:
                        break
                    draw_text(surface, ("-  " if j == 0 else "   ") + line, (panel.x + 36, y), 15,
                              settings.UI_TEXT if current else settings.UI_TEXT_DIM)
                    y += 22
            y += 14
        self.buttons.draw(surface)
