"""Progression screens: stage select, stage clear, permanent upgrades (meta), stats & achievements."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from game.state import StateID
from ui.buttons import Button, draw_panel, wrap_text
from ui.fonts import draw_text
from ui.menus import MenuState, dim, draw_backdrop

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT


class StageSelectState(MenuState):
    state_id = StateID.STAGE_SELECT
    CARD_W, CARD_H = 228, 400

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        n = len(game.stages)
        gap = 14
        x0 = W // 2 - (n * self.CARD_W + (n - 1) * gap) // 2
        for i, stage in enumerate(game.stages):
            unlocked = i <= game.profile.unlocked_stage
            self.buttons.add(Button((x0 + i * (self.CARD_W + gap), 130, self.CARD_W, self.CARD_H), "",
                                    lambda i=i: game.start_new_run(i), enabled=unlocked,
                                    accent=stage.wall_edge))
        self.buttons.add(Button((W // 2 - 110, H - 80, 220, 52), "BACK", game.pop, hotkey=pygame.K_ESCAPE))

    def _boss_names(self, ids: tuple[str, ...]) -> str:
        return " + ".join(self.game.enemy_db[b].name.replace("THE ", "") for b in ids if b in self.game.enemy_db)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, self.time)
        draw_text(surface, "SELECT STAGE", (W // 2, 60), 44, settings.UI_ACCENT, True, "center")
        draw_text(surface, "Clear every wave of a stage to unlock the next, harder one.", (W // 2, 100), 16,
                  settings.UI_TEXT_DIM, anchor="center")
        self.buttons.draw(surface)
        profile = self.game.profile
        for i, stage in enumerate(self.game.stages):
            rect = self.buttons.buttons[i].rect
            unlocked = i <= profile.unlocked_stage
            pygame.draw.rect(surface, stage.floor, rect.inflate(-10, -10).clip(
                pygame.Rect(rect.x, rect.y + 5, rect.w, 60)), border_radius=6)
            draw_text(surface, f"STAGE {stage.number}", (rect.centerx, rect.y + 22), 14, settings.UI_TEXT_DIM,
                      True, "center")
            draw_text(surface, stage.name, (rect.centerx, rect.y + 46), 22,
                      settings.UI_TEXT if unlocked else settings.UI_TEXT_DIM, True, "center")
            if not unlocked:
                draw_text(surface, "LOCKED", (rect.centerx, rect.centery), 26, settings.UI_BAD, True, "center")
                draw_text(surface, f"Clear stage {stage.number - 1}", (rect.centerx, rect.centery + 30), 14,
                          settings.UI_TEXT_DIM, anchor="center")
                continue
            y = rect.y + 84
            for line in wrap_text(stage.subtitle, 13, rect.w - 24)[:3]:
                draw_text(surface, line, (rect.centerx, y), 13, settings.UI_TEXT_DIM, anchor="center")
                y += 18
            rows = [("WAVES", str(stage.waves)), ("ENEMY HP", f"x{stage.hp_mult:.1f}"),
                    ("ENEMY DMG", f"x{stage.damage_mult:.1f}"), ("REWARDS", f"x{stage.reward_mult:.1f}"),
                    ("ELITES", f"{stage.affix_chance * 100:.0f}%+" if stage.affix_chance else "-")]
            y = rect.y + 160
            for k, v in rows:
                draw_text(surface, k, (rect.x + 16, y), 14, settings.UI_TEXT_DIM)
                draw_text(surface, v, (rect.right - 16, y), 14, settings.UI_TEXT, True, "topright")
                y += 24
            draw_text(surface, "BOSSES", (rect.x + 16, y + 6), 13, settings.UI_BAD, True)
            y += 26
            for wave in sorted(stage.bosses):
                for line in wrap_text(f"W{wave}: {self._boss_names(stage.bosses[wave])}", 12, rect.w - 32)[:2]:
                    draw_text(surface, line, (rect.x + 16, y), 12, settings.UI_TEXT)
                    y += 16
            best = profile.stage_best.get(stage.stage_id, 0)
            cleared = profile.stat("stages_cleared") >= stage.number
            status = "CLEARED" if cleared else (f"BEST: WAVE {best}" if best else "NEW")
            draw_text(surface, status, (rect.centerx, rect.bottom - 22), 15,
                      settings.UI_GOOD if cleared else settings.UI_ACCENT, True, "center")


class StageClearState(MenuState):
    state_id = StateID.STAGE_CLEAR
    is_overlay = True

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        s = game.require_session()
        nxt = s.stage.index + 1
        if nxt < len(game.stages):
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
        final = s is not None and s.stage.index == len(self.game.stages) - 1
        draw_text(surface, "YOU ARE THE GUN DESIGNER" if final else "STAGE CLEAR!", (W // 2, 140), 60,
                  settings.UI_GOOD, True, "center")
        if s is None:
            return
        draw_text(surface, s.stage.name, (W // 2, 200), 26, settings.UI_ACCENT, True, "center")
        panel = pygame.Rect(W // 2 - 240, 250, 480, 250)
        draw_panel(surface, panel)
        rows = [("KILLS", str(s.kills)), ("BOSSES DEFEATED", str(s.boss_kills)),
                ("MONEY EARNED", f"${s.money_earned}"), ("FINAL WEAPON", s.player.weapon.name),
                ("CORES EARNED", f"+{res.cores if res else 0}")]
        for i, (k, v) in enumerate(rows):
            draw_text(surface, k, (panel.x + 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT_DIM, True)
            draw_text(surface, v, (panel.right - 30, panel.y + 25 + i * 42), 20, settings.UI_TEXT, True, "topright")
        if not final:
            draw_text(surface, f"Unlocked: STAGE {s.stage.number + 1}", (W // 2, 515), 16, settings.UI_GOOD,
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
