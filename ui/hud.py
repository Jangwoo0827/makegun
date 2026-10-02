"""In-game heads-up display."""
from __future__ import annotations

import math

import pygame

import settings
from entities.enemy import Enemy
from entities.player import BUFF_DEFS, Player
from systems.wave_manager import WaveManager, WavePhase
from ui.buttons import draw_panel
from ui.fonts import draw_text
from weapons.weapon import WeaponStats


def draw_bar(surface: pygame.Surface, rect: pygame.Rect, ratio: float, color: tuple[int, int, int],
             bg: tuple[int, int, int] = (40, 20, 24)) -> None:
    pygame.draw.rect(surface, bg, rect, border_radius=4)
    fill = rect.copy()
    fill.width = int(rect.width * max(0.0, min(1.0, ratio)))
    if fill.width > 0:
        pygame.draw.rect(surface, color, fill, border_radius=4)
    pygame.draw.rect(surface, (0, 0, 0), rect, 2, border_radius=4)


def stat_lines(s: WeaponStats) -> list[tuple[str, str]]:
    """Compact human-readable weapon stats, shared by the HUD and editor."""
    lines = [
        ("DAMAGE", f"{s.damage:.1f}" + (f" x{s.bullet_count}" if s.bullet_count > 1 else "")),
        ("FIRE RATE", f"{s.fire_rate:.1f}/s"),
        ("MAGAZINE", f"{s.magazine_size}"),
        ("RELOAD", f"{s.reload_time:.2f}s"),
        ("BULLET SPD", f"{s.bullet_speed:.0f}"),
        ("SPREAD", f"{s.spread:.1f}°"),
        ("RANGE", f"{s.range:.0f}"),
        ("CRIT", f"{s.crit_chance * 100:.0f}% x{s.crit_damage:.2f}"),
        ("PIERCE", f"{s.pierce}"),
        ("EXPLOSION", f"{s.explosion_radius:.0f}" if s.explosion_radius else "-"),
        ("MODE", s.fire_mode.upper() + (f" x{s.burst_count}" if s.fire_mode == "burst" else "")),
        ("DPS", f"{s.dps:.0f}"),
    ]
    extras = []
    if s.burn:
        extras.append(f"BURN {s.burn * 300:.0f}%")
    if s.split:
        extras.append(f"SPLIT {s.split}")
    if s.ricochet:
        extras.append(f"BOUNCE {s.ricochet}")
    if s.chain:
        extras.append(f"CHAIN {s.chain}")
    if s.lifesteal:
        extras.append(f"LEECH {s.lifesteal * 100:.0f}%")
    if s.luck:
        extras.append(f"LUCK +{s.luck * 100:.0f}%")
    if s.move_speed_mult < 0.999:
        extras.append(f"MOVE {s.move_speed_mult * 100:.0f}%")
    if extras:
        lines.append(("EFFECTS", ", ".join(extras)))
    return lines


class HUD:
    def draw(self, surface: pygame.Surface, player: Player, money: int, waves: WaveManager,
             boss: Enemy | None) -> None:
        w, h = surface.get_size()
        # --- HP & money (top-left)
        panel = pygame.Rect(14, 14, 300, 70)
        draw_panel(surface, panel, alpha=200)
        draw_text(surface, "HP", (28, 24), 16, settings.UI_TEXT_DIM, bold=True)
        draw_bar(surface, pygame.Rect(60, 24, 240, 18), player.hp / player.max_hp, settings.HP_COLOR)
        draw_text(surface, f"{math.ceil(player.hp)} / {int(player.max_hp)}", (180, 33), 14,
                  (255, 255, 255), bold=True, anchor="center")
        draw_text(surface, f"$ {money}", (28, 52), 22, settings.MONEY_COLOR, bold=True)
        bx = 170
        for name, t in player.buffs.items():
            draw_text(surface, f"{BUFF_DEFS[name][0].split()[0]} {t:.0f}s", (bx, 56), 13, (255, 140, 255), bold=True)
            bx += 70

        # --- Wave (top-center)
        wave_rect = pygame.Rect(w // 2 - 170, 10, 340, 58)
        draw_panel(surface, wave_rect, alpha=200)
        total = f"/{waves.total_waves}" if waves.total_waves else ""
        stage = f"{waves.stage.name}  " if waves.stage is not None else ""
        label = f"{stage}WAVE {waves.wave}{total}" + ("  [BOSS]" if waves.is_boss_wave else "")
        draw_text(surface, label, (w // 2, 26), 22, settings.UI_ACCENT, bold=True, anchor="center")
        draw_text(surface, f"ENEMIES LEFT: {waves.remaining}", (w // 2, 46), 14, settings.UI_TEXT, anchor="center")
        draw_bar(surface, pygame.Rect(w // 2 - 130, 58, 260, 5), waves.progress, settings.UI_ACCENT, (40, 40, 50))

        if waves.phase == WavePhase.COUNTDOWN:
            draw_text(surface, f"WAVE {waves.wave}", (w // 2, h // 2 - 120), 64, settings.UI_ACCENT, True, "center")
            if waves.is_final_wave:
                sub = "FINAL WAVE - SURVIVE TO CLEAR THE STAGE"
            elif waves.is_boss_wave:
                sub = "BOSS INCOMING"
            else:
                sub = f"Starting in {max(0.0, waves.countdown):.1f}"
            draw_text(surface, sub, (w // 2, h // 2 - 70), 22, settings.UI_TEXT, True, "center")

        # --- Boss bar
        if boss is not None:
            br = pygame.Rect(w // 2 - 320, 78, 640, 22)
            draw_bar(surface, br, boss.hp / boss.max_hp, (230, 40, 40), (50, 10, 10))
            phase = getattr(boss, "phase", 1)
            draw_text(surface, f"{boss.data.name}" + ("  - ENRAGED" if phase == 2 else ""),
                      (w // 2, br.centery), 15, (255, 255, 255), True, "center")

        # --- Weapon (bottom-right)
        weapon = player.weapon
        wr = pygame.Rect(w - 330, h - 120, 316, 106)
        draw_panel(surface, wr, alpha=210)
        draw_text(surface, weapon.name, (wr.x + 14, wr.y + 10), 18, settings.UI_TEXT, bold=True)
        draw_text(surface, f"Lv.{weapon.level}", (wr.right - 14, wr.y + 12), 15, settings.UI_ACCENT, True, "topright")
        ammo_color = settings.UI_BAD if weapon.ammo == 0 else (255, 255, 255)
        draw_text(surface, f"{weapon.ammo}", (wr.x + 14, wr.y + 36), 34, ammo_color, bold=True)
        draw_text(surface, f"/ {weapon.reserve}", (wr.x + 90, wr.y + 50), 18, settings.UI_TEXT_DIM, bold=True)
        if weapon.reloading:
            draw_bar(surface, pygame.Rect(wr.x + 14, wr.y + 82, 180, 10), weapon.reload_progress,
                     (120, 200, 255), (30, 40, 60))
            label = "SCAVENGING" if weapon.emergency else "RELOADING"
            draw_text(surface, label, (wr.x + 200, wr.y + 78), 14, (120, 200, 255), bold=True)
        elif weapon.ammo <= weapon.stats.magazine_size * 0.25:
            draw_text(surface, "[R] RELOAD", (wr.x + 14, wr.y + 80), 14, settings.UI_ACCENT, bold=True)
        for i in range(settings.MAX_WEAPON_SLOTS):
            sr = pygame.Rect(wr.right - 30 * (settings.MAX_WEAPON_SLOTS - i) - 8, wr.y + 40, 24, 24)
            if i < len(player.weapons):
                active = i == player.current
                pygame.draw.rect(surface, settings.UI_ACCENT if active else settings.UI_PANEL_LIGHT, sr, border_radius=4)
                draw_text(surface, str(i + 1), sr.center, 14, (0, 0, 0) if active else settings.UI_TEXT, True, "center")
            else:
                pygame.draw.rect(surface, (40, 42, 50), sr, 1, border_radius=4)

        # --- Weapon stats (bottom-left, compact)
        s = weapon.stats
        lines = [("DMG", f"{s.damage:.0f}" + (f"x{s.bullet_count}" if s.bullet_count > 1 else "")),
                 ("RATE", f"{s.fire_rate:.1f}"), ("DPS", f"{s.dps:.0f}"), ("PIERCE", str(s.pierce)),
                 ("CRIT", f"{s.crit_chance * 100:.0f}%"), ("MODE", s.fire_mode.upper())]
        if s.synergies:
            draw_text(surface, "SYNERGY: " + ", ".join(s.synergies), (16, h - 84), 14, (255, 170, 255), bold=True)
        sr = pygame.Rect(14, h - 62, 430, 48)
        draw_panel(surface, sr, alpha=180)
        x = sr.x + 12
        for k, v in lines:
            draw_text(surface, k, (x, sr.y + 7), 12, settings.UI_TEXT_DIM, bold=True)
            draw_text(surface, v, (x, sr.y + 23), 16, settings.UI_TEXT, bold=True)
            x += 70

    @staticmethod
    def draw_skills(surface: pygame.Surface, player: Player) -> None:
        """Dash / grenade cooldown icons above the weapon panel."""
        w, h = surface.get_size()
        skills = [("DASH", "SPACE", player.dash_cooldown, player.dash_cooldown_max, (120, 200, 255)),
                  ("NADE", "Q/RMB", player.grenade_cooldown, player.grenade_cooldown_max, (255, 140, 80))]
        for i, (name, key, cd, cd_max, color) in enumerate(skills):
            rect = pygame.Rect(w - 330 + i * 86, h - 186, 78, 58)
            ready = cd <= 0
            draw_panel(surface, rect, border=color if ready else settings.UI_BORDER, alpha=210)
            if not ready:
                frac = cd / max(0.01, cd_max)
                shade = pygame.Surface((rect.w - 4, int((rect.h - 4) * frac)), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 150))
                surface.blit(shade, (rect.x + 2, rect.bottom - 2 - shade.get_height()))
            draw_text(surface, name, (rect.centerx, rect.y + 16), 16, color if ready else settings.UI_TEXT_DIM,
                      True, "center")
            sub = key if ready else f"{cd:.1f}s"
            draw_text(surface, sub, (rect.centerx, rect.y + 40), 12, settings.UI_TEXT, anchor="center")

    @staticmethod
    def draw_crosshair(surface: pygame.Surface, pos: tuple[int, int], spread: float, charge: float) -> None:
        x, y = pos
        gap = 6 + spread * 0.8
        color = (255, 255, 255)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surface, color, (x + dx * gap, y + dy * gap), (x + dx * (gap + 8), y + dy * (gap + 8)), 2)
        pygame.draw.circle(surface, color, pos, 2)
        if charge > 0:
            rect = pygame.Rect(0, 0, 34, 34)
            rect.center = pos
            pygame.draw.arc(surface, (200, 120, 255) if charge < 1 else (255, 255, 255), rect,
                            math.pi / 2, math.pi / 2 + math.tau * charge, 3)
