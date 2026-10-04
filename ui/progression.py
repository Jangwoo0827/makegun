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
from systems.assets import ASSETS
from ui.menus import MenuState, dim, draw_backdrop
from weapons.evolution import all_evolutions
from weapons.synergy import all_synergies

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
            header = pygame.Rect(rect.x + 5, rect.y + 5, rect.w - 10, 50)
            pygame.draw.rect(surface, stage.floor, header, border_radius=6)
            tile = ASSETS.get("tiles", f"{stage.stage_id}_floor", (160, 160))
            if tile is not None and unlocked:  # preview the stage's floor
                clip = surface.get_clip()
                surface.set_clip(header)
                for tx in range(header.x, header.right, 160):
                    surface.blit(tile, (tx, header.y - 50))
                surface.set_clip(clip)
                shade = pygame.Surface(header.size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 90))
                surface.blit(shade, header.topleft)
            draw_text(surface, f"STAGE {stage.number}", (rect.centerx, rect.y + 18), 12, settings.UI_TEXT_DIM,
                      True, "center")
            draw_text(surface, stage.name, (rect.centerx, rect.y + 38), 20,
                      settings.UI_TEXT if unlocked else settings.UI_TEXT_DIM, True, "center")
            if not unlocked:
                draw_text(surface, "LOCKED", (rect.centerx, rect.centery + 10), 24, settings.UI_BAD, True, "center")
                draw_text(surface, f"Clear stage {stage.number - 1}", (rect.centerx, rect.centery + 38), 13,
                          settings.UI_TEXT_DIM, anchor="center")
                continue
            draw_text(surface, stage.subtitle, (rect.centerx, rect.y + 68), 11, settings.UI_TEXT_DIM, anchor="center")
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
    ("characters_unlocked", "Characters unlocked"), ("best_ascension_clear", "Highest ascension cleared"),
)
STATS_TABS: tuple[str, ...] = ("STATS", "ACHIEVEMENTS", "CODEX", "HISTORY")
CODEX_TABS: tuple[str, ...] = ("PARTS", "ENEMIES", "SYNERGIES")


def _fmt_time(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


class StatsState(MenuState):
    """Stats, achievements, codex and run history, one full-width tab each."""
    state_id = StateID.STATS
    PANEL = pygame.Rect(30, 120, W - 60, 520)

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.tab: str = STATS_TABS[0]
        self.codex_tab: str = CODEX_TABS[0]
        self._build()

    def _build(self) -> None:
        self.buttons.clear()
        tw = 200
        x0 = W // 2 - (len(STATS_TABS) * (tw + 10) - 10) // 2
        for i, name in enumerate(STATS_TABS):
            self.buttons.add(Button((x0 + i * (tw + 10), 66, tw, 42), name, lambda n=name: self._tab(n),
                                    font_size=16, selected=self.tab == name))
        if self.tab == "CODEX":
            for i, name in enumerate(CODEX_TABS):
                self.buttons.add(Button((self.PANEL.x + 16 + i * 150, self.PANEL.y + 12, 140, 32), name,
                                        lambda n=name: self._codex(n), font_size=13,
                                        selected=self.codex_tab == name, accent=(150, 220, 255)))
        self.buttons.add(Button((W // 2 - 110, H - 66, 220, 48), "BACK", self.game.pop, hotkey=pygame.K_ESCAPE))

    def _tab(self, name: str) -> None:
        self.tab = name
        self._build()

    def _codex(self, name: str) -> None:
        self.codex_tab = name
        self._build()

    # ------------------------------------------------------------------ tabs
    def _draw_stats(self, surface: pygame.Surface, p: pygame.Rect) -> None:
        prof = self.game.profile
        draw_text(surface, "LIFETIME", (p.x + 20, p.y + 16), 18, settings.UI_ACCENT, True)
        y = p.y + 50
        for key, label in STAT_LABELS:
            draw_text(surface, label, (p.x + 20, y), 16, settings.UI_TEXT_DIM)
            draw_text(surface, f"{int(prof.stat(key)):,}", (p.x + 560, y), 16, settings.UI_TEXT, True, "topright")
            y += 30
        y += 10
        draw_text(surface, "MODES", (p.x + 20, y), 18, settings.UI_ACCENT, True)
        y += 34
        best_t = prof.stat("best_bossrush_time")
        for label, value in (("Endless best wave", str(int(prof.stat("endless_best"))) or "-"),
                             ("Boss Rush clears", str(int(prof.stat("bossrush_clears")))),
                             ("Boss Rush best time", _fmt_time(best_t) if best_t else "-")):
            draw_text(surface, label, (p.x + 20, y), 16, settings.UI_TEXT_DIM)
            draw_text(surface, value, (p.x + 560, y), 16, settings.UI_TEXT, True, "topright")
            y += 30
        x = p.x + 640
        draw_text(surface, "BEST WAVE PER STAGE", (x, p.y + 16), 18, settings.UI_ACCENT, True)
        y = p.y + 50
        for stage in self.game.stages:
            best = prof.stage_best.get(stage.stage_id, 0)
            cleared = prof.stat("stages_cleared") >= stage.number
            draw_text(surface, f"{stage.number}. {stage.name}", (x, y), 16, settings.UI_TEXT_DIM)
            draw_text(surface, (f"{best}/{stage.waves}" if best else "-") + ("  CLEAR" if cleared else ""),
                      (p.right - 24, y), 16, settings.UI_GOOD if cleared else settings.UI_TEXT, True, "topright")
            y += 30

    def _draw_achievements(self, surface: pygame.Surface, p: pygame.Rect) -> None:
        prof = self.game.profile
        cat = prof.achievement_catalog
        draw_text(surface, f"{len(prof.achievements)}/{len(cat)} UNLOCKED", (p.x + 20, p.y + 14), 18,
                  settings.UI_ACCENT, True)
        cols, rows = 3, (len(cat) + 2) // 3
        col_w = (p.w - 40) // cols
        row_h = min(56, (p.h - 56) // max(1, rows))
        for i, a in enumerate(cat):
            col, row = i // rows, i % rows
            x = p.x + 20 + col * col_w
            y = p.y + 48 + row * row_h
            done = a.ach_id in prof.achievements
            pygame.draw.rect(surface, settings.UI_GOOD if done else (50, 56, 70), (x, y + 3, 12, 12), border_radius=3)
            draw_text(surface, a.name, (x + 20, y), 15, settings.UI_TEXT if done else settings.UI_TEXT_DIM, True)
            draw_text(surface, f"{a.description} (+{a.reward})", (x + 20, y + 20), 12, settings.UI_TEXT_DIM)

    def _draw_codex(self, surface: pygame.Surface, p: pygame.Rect) -> None:
        prof = self.game.profile
        top = p.y + 58
        if self.codex_tab == "PARTS":
            parts = list(self.game.library.parts.values())
            found = prof.discovered["parts"]
            draw_text(surface, f"{sum(1 for x in parts if x.part_id in found)}/{len(parts)} found",
                      (p.right - 20, p.y + 18), 15, settings.UI_TEXT_DIM, True, "topright")
            cols = 10
            tw, th = (p.w - 40) // cols, 56
            for i, part in enumerate(parts):
                x = p.x + 20 + (i % cols) * tw
                y = top + (i // cols) * (th + 3)
                rect = pygame.Rect(x + 2, y, tw - 4, th)
                known = part.part_id in found
                color = settings.RARITY_COLORS[part.rarity.value]
                pygame.draw.rect(surface, settings.UI_PANEL_LIGHT if known else (24, 26, 34), rect, border_radius=5)
                pygame.draw.rect(surface, color if known else (50, 54, 66), rect, 1, border_radius=5)
                if known:
                    if not ASSETS.blit_part_icon(surface, part.part_id, (rect.centerx, rect.y + 21), (60, 28)):
                        draw_text(surface, part.category.label[:4].upper(), (rect.centerx, rect.y + 22), 12, color,
                                  True, "center")
                    short = part.name.replace(" Receiver", "").replace(" Barrel", "").replace(" Magazine", "")
                    draw_text(surface, short[:15], (rect.centerx, rect.bottom - 10), 11, settings.UI_TEXT,
                              anchor="center")
                else:
                    draw_text(surface, "???", (rect.centerx, rect.centery), 16, (70, 74, 88), True, "center")
        elif self.codex_tab == "ENEMIES":
            db = self.game.enemy_db
            found = prof.discovered["enemies"]
            draw_text(surface, f"{sum(1 for k in db if k in found)}/{len(db)} found", (p.right - 20, p.y + 18), 15,
                      settings.UI_TEXT_DIM, True, "topright")
            cols = 6
            tw, th = (p.w - 40) // cols, 140
            for i, (key, data) in enumerate(db.items()):
                x = p.x + 20 + (i % cols) * tw
                y = top + (i // cols) * (th + 6)
                rect = pygame.Rect(x + 3, y, tw - 6, th)
                known = key in found
                boss = data.behavior == "boss"
                pygame.draw.rect(surface, settings.UI_PANEL_LIGHT if known else (24, 26, 34), rect, border_radius=6)
                pygame.draw.rect(surface, (255, 90, 90) if boss and known else (60, 64, 78), rect, 1, border_radius=6)
                if not known:
                    draw_text(surface, "???", rect.center, 22, (70, 74, 88), True, "center")
                    continue
                if not ASSETS.blit_centered(surface, "enemies", key, (rect.centerx, rect.y + 50), (64, 64)):
                    pygame.draw.circle(surface, data.color, (rect.centerx, rect.y + 50), 24)
                draw_text(surface, data.name, (rect.centerx, rect.y + 96), 13, settings.UI_TEXT, True, "center")
                draw_text(surface, f"HP {int(data.hp)}  DMG {int(data.damage)}", (rect.centerx, rect.y + 116), 11,
                          settings.UI_TEXT_DIM, anchor="center")
        else:
            syns = list(all_synergies())
            found = prof.discovered["synergies"]
            evo_found = prof.discovered["evolutions"]
            evos = all_evolutions()
            draw_text(surface, f"{sum(1 for s in syns if s.name in found)}/{len(syns)} synergies   "
                               f"{len(evo_found)}/{len(evos)} evolutions", (p.right - 20, p.y + 18), 15,
                      settings.UI_TEXT_DIM, True, "topright")
            col_w = (p.w - 40) // 2
            row_h = min(54, (p.h - 70) // max(1, (len(syns) + 1) // 2))
            for i, syn in enumerate(syns):
                col, row = i % 2, i // 2
                x = p.x + 20 + col * col_w
                y = top + row * row_h
                known = syn.name in found
                evo = evos.get(syn.synergy_id)
                evolved = evo is not None and evo.name in evo_found
                name = syn.name if known else "???"
                draw_text(surface, name, (x, y), 15, (255, 170, 255) if known else (80, 84, 98), True)
                if known:
                    draw_text(surface, syn.description, (x + 14, y + 20), 12, settings.UI_TEXT_DIM)
                if evo is not None:
                    label = f"-> {evo.name}" if evolved else "-> ???"
                    draw_text(surface, label, (x + col_w - 20, y + 2), 12,
                              settings.RARITY_COLORS["LEGENDARY"] if evolved else (80, 84, 98), True, "topright")

    def _draw_history(self, surface: pygame.Surface, p: pygame.Rect) -> None:
        hist = self.game.profile.history
        if not hist:
            draw_text(surface, "No runs yet - go play!", p.center, 20, settings.UI_TEXT_DIM, True, "center")
            return
        cols = [("DATE", 20), ("STAGE", 190), ("RESULT", 400), ("WAVE", 530), ("KILLS", 620), ("TIME", 710),
                ("CHARACTER", 800), ("WEAPON", 940), ("CORES", p.w - 40)]
        for label, cx in cols:
            anchor = "topright" if label == "CORES" else "topleft"
            draw_text(surface, label, (p.x + cx, p.y + 14), 13, settings.UI_ACCENT, True, anchor)
        for i, h in enumerate(hist[:17]):
            y = p.y + 42 + i * 27
            if i % 2 == 0:
                pygame.draw.rect(surface, (30, 34, 46), (p.x + 10, y - 4, p.w - 20, 25), border_radius=4)
            stage = h.get("stage", "?") + (f" A{h['ascension']}" if h.get("ascension") else "")
            result = "CLEAR" if h.get("victory") else "DIED"
            waves = h.get("waves") or 0
            wave = f"{h.get('wave', 0)}/{waves}" if waves else str(h.get("wave", 0))
            vals = [h.get("date", ""), stage, result, wave, str(h.get("kills", 0)), _fmt_time(h.get("time", 0)),
                    str(h.get("character", "")).upper(), str(h.get("weapon", ""))[:22], f"+{h.get('cores', 0)}"]
            for (label, cx), v in zip(cols, vals):
                color = (settings.UI_GOOD if v == "CLEAR" else settings.UI_BAD) if label == "RESULT" else settings.UI_TEXT
                anchor = "topright" if label == "CORES" else "topleft"
                draw_text(surface, v, (p.x + cx, y), 13, color, label == "RESULT", anchor)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "STATS & RECORDS", (W // 2, 34), 34, settings.UI_ACCENT, True, "center")
        draw_panel(surface, self.PANEL)
        {"STATS": self._draw_stats, "ACHIEVEMENTS": self._draw_achievements,
         "CODEX": self._draw_codex, "HISTORY": self._draw_history}[self.tab](surface, self.PANEL)
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
